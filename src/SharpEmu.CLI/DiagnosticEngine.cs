// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Text.Json;
using System.Text;
using SharpEmu.Logging;

namespace SharpEmu.CLI;

/// <summary>
/// Crash Export Pipeline - "Black Box" for SharpEmu
/// Ensures diagnostic data is flushed to disk even on crash.
/// </summary>
public sealed class DiagnosticEngine : IDisposable
{
    private static readonly SharpEmuLogger Log = SharpEmuLog.For("SharpEmu.Diagnostics");
    
    private readonly string _diagnosticsBasePath;
    private readonly string _sessionId;
    private readonly string _sessionDir;
    private readonly string _liveDir;
    private readonly string _crashDir;
    private readonly Timer? _watchdogTimer;
    private readonly object _syncLock = new();
    private readonly CancellationTokenSource _cts = new();
    
    private SessionState _currentState = new();
    private bool _disposed;
    private DateTime _sessionStart;
    private long _totalImports;
    private string _lastNid = string.Empty;
    private int _activeThreads;
    private string _lastApi = string.Empty;
    private List<string> _importLog = new();
    private List<string> _threadLog = new();
    private List<string> _memoryLog = new();
    private List<string> _gpuLog = new();
    private List<string> _errorLog = new();

    public string DiagnosticsBasePath => _diagnosticsBasePath;
    public string SessionId => _sessionId;
    public string SessionDirectory => _sessionDir;
    public string LiveDirectory => _liveDir;
    public string CrashDirectory => _crashDir;

    /// <summary>
    /// Creates a new DiagnosticEngine instance with fixed directory structure.
    /// </summary>
    /// <param name="gameName">Game identifier (e.g., PPSA02929 or eboot.bin filename)</param>
    /// <param name="baseDirectory">Optional base directory (defaults to ./SharpEmu/diagnostics)</param>
    public DiagnosticEngine(string gameName, string? baseDirectory = null)
    {
        _sessionStart = DateTime.UtcNow;
        _sessionId = $"{gameName}-{_sessionStart:yyyyMMdd_HHmmss}";
        
        // Fixed directory structure:
        // SharpEmu/
        // └── diagnostics/
        //     ├── sessions/
        //     ├── crash/
        //     └── live/
        
        // Use current directory for diagnostics
        var baseCandidate = baseDirectory ?? Path.Combine(
            Directory.GetCurrentDirectory(), 
            "diagnostics");
            
        _diagnosticsBasePath = baseCandidate;
        
        _liveDir = Path.Combine(_diagnosticsBasePath, "live");
        _crashDir = Path.Combine(_diagnosticsBasePath, "crash");
        var sessionsDir = Path.Combine(_diagnosticsBasePath, "sessions");
        _sessionDir = Path.Combine(sessionsDir, _sessionId);
        
        // Ensure all directories exist
        EnsureDirectory(_diagnosticsBasePath);
        EnsureDirectory(_liveDir);
        EnsureDirectory(_crashDir);
        EnsureDirectory(sessionsDir);
        EnsureDirectory(_sessionDir);
        
        Log.Info($"DiagnosticEngine initialized: {_sessionDir}");
        
        // Start watchdog timer if enabled
        var watchdogSeconds = GetEnvInt("SHARPEMU_WATCHDOG", 0);
        if (watchdogSeconds > 0)
        {
            _watchdogTimer = new Timer(
                WatchdogCallback, 
                null, 
                TimeSpan.FromSeconds(watchdogSeconds),
                TimeSpan.FromSeconds(watchdogSeconds));
            
            Log.Info($"Watchdog enabled: every {watchdogSeconds}s");
        }
        
        // Write initial session state
        WriteLiveSession();
        
        // Register for process exit (best-effort)
        AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
    }

    #region Public API

    /// <summary>
    /// Records an import call event.
    /// </summary>
    public void RecordImport(string nid, string? library = null, ulong returnAddress = 0)
    {
        lock (_syncLock)
        {
            Interlocked.Increment(ref _totalImports);
            _lastNid = nid;
            _lastApi = library is not null ? $"{library}:{nid}" : nid;
            
            if (GetEnvBool("SHARPEMU_TRACE_IMPORTS"))
            {
                var entry = $"[{DateTime.UtcNow:HH:mm:ss.fff}] IMPORT #{_totalImports}: {nid} (lib={library}) ret=0x{returnAddress:X16}";
                _importLog.Add(entry);
                
                // Keep log bounded
                if (_importLog.Count > 10000)
                {
                    _importLog.RemoveAt(0);
                }
            }
        }
    }

    /// <summary>
    /// Records thread state change.
    /// </summary>
    public void RecordThread(int threadId, string state, string? name = null)
    {
        lock (_syncLock)
        {
            if (GetEnvBool("SHARPEMU_TRACE_THREADS"))
            {
                var entry = $"[{DateTime.UtcNow:HH:mm:ss.fff}] THREAD t={threadId} {state}{(name is not null ? $" ({name})" : "")}";
                _threadLog.Add(entry);
                
                if (_threadLog.Count > 5000)
                {
                    _threadLog.RemoveAt(0);
                }
            }
        }
    }

    /// <summary>
    /// Updates active thread count.
    /// </summary>
    public void UpdateThreadCount(int count)
    {
        lock (_syncLock)
        {
            _activeThreads = count;
        }
    }

    /// <summary>
    /// Records memory operation.
    /// </summary>
    public void RecordMemory(string operation, ulong address, ulong size, string? result = null)
    {
        lock (_syncLock)
        {
            if (GetEnvBool("SHARPEMU_TRACE_MEMORY"))
            {
                var entry = $"[{DateTime.UtcNow:HH:mm:ss.fff}] MEM {operation} addr=0x{address:X16} size=0x{size:X}{(result is not null ? $" -> {result}" : "")}";
                _memoryLog.Add(entry);
                
                if (_memoryLog.Count > 5000)
                {
                    _memoryLog.RemoveAt(0);
                }
            }
        }
    }

    /// <summary>
    /// Records GPU/Vulkan operation.
    /// </summary>
    public void RecordGpu(string operation, string? details = null)
    {
        lock (_syncLock)
        {
            if (GetEnvBool("SHARPEMU_TRACE_GPU"))
            {
                var entry = $"[{DateTime.UtcNow:HH:mm:ss.fff}] GPU {operation}{(details is not null ? $" ({details})" : "")}";
                _gpuLog.Add(entry);
                
                if (_gpuLog.Count > 5000)
                {
                    _gpuLog.RemoveAt(0);
                }
            }
        }
    }
    
    /// <summary>
    /// Records a GPU timeline event (from HeadlessVideoPresenter).
    /// These events track the lifecycle of GPU operations.
    /// </summary>
    public void RecordGpuTimelineEvent(double timestamp, string eventType, string description)
    {
        lock (_syncLock)
        {
            var entry = $"[{timestamp:F3}s] [TIMELINE] {eventType}: {description}";
            _gpuLog.Add(entry);
            
            // Also update current state
            _currentState.LastApi = $"GPU:{eventType}";
            
            Log.Debug($"GPU Timeline: {eventType} - {description}");
        }
    }
    
    /// <summary>
    /// Imports GPU diagnostics report from HeadlessVideoPresenter.
    /// Call this when session ends or on crash.
    /// </summary>
    public void ImportGpuReport(object gpuReport)
    {
        lock (_syncLock)
        {
            try
            {
                // Convert report to JSON and store
                var json = JsonSerializer.Serialize(gpuReport, new JsonSerializerOptions { WriteIndented = true });
                var reportPath = Path.Combine(_sessionDir, "gpu_report.json");
                File.WriteAllText(reportPath, json, Encoding.UTF8);
                
                RecordGpu("ImportGpuReport", $"GPU report saved to {reportPath}");
                Log.Info($"GPU report imported: {reportPath}");
            }
            catch (Exception ex)
            {
                RecordError("GpuReportImport", $"Failed to import GPU report: {ex.Message}");
            }
        }
    }
    
    /// <summary>
    /// Records AGC frame summary for diagnostics.
    /// </summary>
    public void RecordAgcFrameSummary(int frameNumber, long drawCount, long submitCount, int resourceCount, long memoryMB)
    {
        lock (_syncLock)
        {
            if (frameNumber % 100 == 0) // Log every 100 frames to avoid spam
            {
                var entry = $"[AGC] Frame #{frameNumber}: Draws={drawCount} Submits={submitCount} Resources={resourceCount} Memory={memoryMB}MB";
                _gpuLog.Add(entry);
                
                Log.Debug(entry);
            }
        }
    }

    /// <summary>
    /// Records an error or crash event.
    /// </summary>
    public void RecordError(string errorType, string message, string? stackTrace = null)
    {
        lock (_syncLock)
        {
            var entry = $"[{DateTime.UtcNow:HH:mm:ss.fff}] ERROR [{errorType}] {message}";
            _errorLog.Add(entry);
            
            if (stackTrace is not null)
            {
                _errorLog.Add($"  StackTrace: {stackTrace}");
            }
            
            if (_errorLog.Count > 1000)
            {
                _errorLog.RemoveAt(0);
            }
            
            // Immediately flush on error
            if (GetEnvBool("SHARPEMU_DEBUG_PACKAGE"))
            {
                try
                {
                    GenerateCrashReport(errorType, message);
                }
                catch
                {
                    // Best-effort - don't let crash reporting crash
                }
            }
        }
    }

    /// <summary>
    /// Flushes all collected diagnostics to disk.
    /// Call this in finally blocks!
    /// </summary>
    public void Flush()
    {
        lock (_syncLock)
        {
            try
            {
                WriteLiveSession();
                WriteImportLog();
                WriteThreadLog();
                WriteMemoryLog();
                WriteGpuLog();
                WriteErrorLog();
                
                Log.Debug("DiagnosticEngine.Flush() completed");
            }
            catch (Exception ex)
            {
                Log.Error($"Flush failed: {ex.Message}");
            }
        }
    }

    /// <summary>
    /// Generates complete diagnostic package (ZIP with all logs).
    /// Call this before exit!
    /// </summary>
    public void GeneratePackage()
    {
        lock (_syncLock)
        {
            try
            {
                // Final flush
                Flush();
                
                // Generate session summary JSON
                var summary = CreateSessionSummary(true);
                var summaryPath = Path.Combine(_sessionDir, "session_summary.json");
                File.WriteAllText(summaryPath, JsonSerializer.Serialize(summary, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
                
                // Copy to crash dir as well
                var crashCopyPath = Path.Combine(_crashDir, $"{_sessionId}_summary.json");
                File.Copy(summaryPath, crashCopyPath, overwrite: true);
                
                Log.Info($"Diagnostic package generated: {_sessionDir}");
                Log.Info($"Crash report also at: {crashCopyPath}");
            }
            catch (Exception ex)
            {
                Log.Error($"GeneratePackage failed: {ex.Message}");
            }
        }
    }

    #endregion

    #region Private Implementation

    private void WatchdogCallback(object? state)
    {
        if (_cts.IsCancellationRequested)
        {
            return;
        }
        
        try
        {
            WriteLiveSession();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[DIAGNOSTICS] Watchdog error: {ex.Message}");
        }
    }

    private void WriteLiveSession()
    {
        var sessionData = CreateSessionSummary(false);
        var json = JsonSerializer.Serialize(sessionData, new JsonSerializerOptions { WriteIndented = true });
        var livePath = Path.Combine(_liveDir, "session.json");
        
        // Atomic write: write to temp then rename
        var tempPath = livePath + ".tmp";
        File.WriteAllText(tempPath, json, Encoding.UTF8);
        
        try
        {
            File.Move(tempPath, livePath, overwrite: true);
        }
        catch
        {
            // Fallback if rename fails
            File.Copy(tempPath, livePath, overwrite: true);
            try { File.Delete(tempPath); } catch { }
        }
    }

    private SessionState CreateSessionSummary(bool includeLogs)
    {
        var elapsed = DateTime.UtcNow - _sessionStart;
        
        return new SessionState
        {
            SessionId = _sessionId,
            Timestamp = _sessionStart.ToString("o"),
            UptimeSeconds = elapsed.TotalSeconds,
            TotalImports = Interlocked.Read(ref _totalImports),
            LastNid = _lastNid,
            LastApi = _lastApi,
            ActiveThreads = _activeThreads,
            ImportLogCount = _importLog.Count,
            ThreadLogCount = _threadLog.Count,
            MemoryLogCount = _memoryLog.Count,
            GpuLogCount = _gpuLog.Count,
            ErrorLogCount = _errorLog.Count,
            IncludeLogs = includeLogs,
            Imports = includeLogs ? _importLog.ToArray() : Array.Empty<string>(),
            Threads = includeLogs ? _threadLog.ToArray() : Array.Empty<string>(),
            MemoryOps = includeLogs ? _memoryLog.ToArray() : Array.Empty<string>(),
            GpuOps = includeLogs ? _gpuLog.ToArray() : Array.Empty<string>(),
            Errors = includeLogs ? _errorLog.ToArray() : Array.Empty<string>()
        };
    }

    private void WriteImportLog()
    {
        if (_importLog.Count == 0) return;
        var path = Path.Combine(_sessionDir, "imports.log");
        File.WriteAllLines(path, _importLog, Encoding.UTF8);
    }

    private void WriteThreadLog()
    {
        if (_threadLog.Count == 0) return;
        var path = Path.Combine(_sessionDir, "threads.log");
        File.WriteAllLines(path, _threadLog, Encoding.UTF8);
    }

    private void WriteMemoryLog()
    {
        if (_memoryLog.Count == 0) return;
        var path = Path.Combine(_sessionDir, "memory.log");
        File.WriteAllLines(path, _memoryLog, Encoding.UTF8);
    }

    private void WriteGpuLog()
    {
        if (_gpuLog.Count == 0) return;
        var path = Path.Combine(_sessionDir, "gpu.log");
        File.WriteAllLines(path, _gpuLog, Encoding.UTF8);
    }

    private void WriteErrorLog()
    {
        if (_errorLog.Count == 0) return;
        var path = Path.Combine(_sessionDir, "errors.log");
        File.WriteAllLines(path, _errorLog, Encoding.UTF8);
    }

    private void GenerateCrashReport(string errorType, string message)
    {
        var timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        var crashFile = Path.Combine(_crashDir, $"{_sessionId}_{timestamp}_{errorType}.json");
        
        var crashReport = new
        {
            CrashTime = DateTime.UtcNow.ToString("o"),
            ErrorType = errorType,
            Message = message,
            Session = CreateSessionSummary(true)
        };
        
        File.WriteAllText(crashFile, 
            JsonSerializer.Serialize(crashReport, new JsonSerializerOptions { WriteIndented = true }), 
            Encoding.UTF8);
        
        Console.Error.WriteLine($"[DIAGNOSTICS] Crash report written: {crashFile}");
    }

    private static void EnsureDirectory(string path)
    {
        if (!Directory.Exists(path))
        {
            Directory.CreateDirectory(path);
        }
    }

    private static bool GetEnvBool(string name, bool defaultValue = false)
    {
        var val = Environment.GetEnvironmentVariable(name);
        if (string.IsNullOrWhiteSpace(val)) return defaultValue;
        return val.Equals("1", StringComparison.OrdinalIgnoreCase) ||
               val.Equals("true", StringComparison.OrdinalIgnoreCase);
    }

    private static int GetEnvInt(string name, int defaultValue = 0)
    {
        var val = Environment.GetEnvironmentVariable(name);
        if (string.IsNullOrWhiteSpace(val)) return defaultValue;
        return int.TryParse(val, out var result) ? result : defaultValue;
    }

    private void OnProcessExit(object? sender, EventArgs e)
    {
        try
        {
            Console.Error.WriteLine("[DIAGNOSTICS] ProcessExit - flushing...");
            GeneratePackage();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[DIAGNOSTICS] ProcessExit failed: {ex.Message}");
        }
    }

    private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception ex)
        {
            RecordError("UnhandledException", ex.Message, ex.StackTrace);
        }
        
        try
        {
            Console.Error.WriteLine("[DIAGNOSTICS] UnhandledException - generating crash report...");
            GeneratePackage();
        }
        catch
        {
            // Best effort
        }
    }

    #endregion

    #region IDisposable

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        
        _watchdogTimer?.Dispose();
        _cts.Cancel();
        _cts.Dispose();
        
        // Final flush
        try
        {
            GeneratePackage();
        }
        catch
        {
            // Best effort on dispose
        }
    }

    #endregion

    #region Data Classes

    private sealed class SessionState
    {
        public string SessionId { get; set; } = string.Empty;
        public string Timestamp { get; set; } = string.Empty;
        public double UptimeSeconds { get; set; }
        public long TotalImports { get; set; }
        public string LastNid { get; set; } = string.Empty;
        public string LastApi { get; set; } = string.Empty;
        public int ActiveThreads { get; set; }
        public int ImportLogCount { get; set; }
        public int ThreadLogCount { get; set; }
        public int MemoryLogCount { get; set; }
        public int GpuLogCount { get; set; }
        public int ErrorLogCount { get; set; }
        public bool IncludeLogs { get; set; }
        public string[] Imports { get; set; } = Array.Empty<string>();
        public string[] Threads { get; set; } = Array.Empty<string>();
        public string[] MemoryOps { get; set; } = Array.Empty<string>();
        public string[] GpuOps { get; set; } = Array.Empty<string>();
        public string[] Errors { get; set; } = Array.Empty<string>();
        
        // GPU-specific state
        public bool IsHeadlessMode { get; set; }
        public string GpuBackend { get; set; } = "Unknown";
        public long TotalFrames { get; set; }
        public long TotalDrawCalls { get; set; }
        public string GpuResolution { get; set; } = "N/A";
        public double GpuSessionElapsed { get; set; }
    }

    #endregion
}
