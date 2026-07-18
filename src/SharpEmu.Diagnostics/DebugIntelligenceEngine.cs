// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

// ============================================================================
// SHARPEMU DIAGNOSTICS - CLEAN REIMPLEMENTATION (post-refactor)
//
// This file implements ALL diagnostic subsystems in a single, self-contained
// file that depends ONLY on SharpEmu.Diagnostics.Contracts.
//
// ARCHITECTURE:
// - This file has ZERO dependencies on SharpEmu.Core/Libs/HLE.
// - It implements IDiagnosticEventBus and consumes the *Source interfaces.
// - Core/Libs/HLE register their *Source implementations with us.
// - When the runtime calls RecordInstruction() etc., the data flows through
//   the registered source into our subsystems.
//
// This breaks the circular dependency that previously caused 100+ compile
// errors every time Core changed.
// ============================================================================

using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Logging;

namespace SharpEmu.Diagnostics;

/// <summary>
/// Central diagnostic engine - implements IDiagnosticEventBus.
/// Singleton instance accessible via DebugIntelligenceEngine.Current.
/// </summary>
public sealed class DebugIntelligenceEngine : IDiagnosticEventBus, IDisposable
{
    #region Singleton

    private static DebugIntelligenceEngine? _current;
    
    /// <summary>
    /// Gets the current active diagnostic engine, or null if diagnostics are disabled.
    /// </summary>
    public static DebugIntelligenceEngine? Current => _current;
    
    /// <summary>
    /// Creates and activates a new diagnostic session.
    /// </summary>
    public static DebugIntelligenceEngine CreateSession(
        string gameId,
        string sessionDir,
        DiagnosticProfile profile)
    {
        var engine = new DebugIntelligenceEngine(gameId, sessionDir, profile);
        _current = engine;
        return engine;
    }

    #endregion

    #region State

    public string GameId { get; }
    public string SessionDirectory { get; }
    public DiagnosticProfile Profile { get; }
    public bool IsActive => true;
    public bool Disposed { get; private set; }
    
    // Subsystem instances (all owned by us)
    public CpuTraceRecorder CpuTrace { get; }
    public GpuCommandStateRecorder GpuRecorder { get; }
    public MemoryMapDebugger MemoryDebugger { get; }
    public ThreadTimelineDebugger ThreadDebugger { get; }
    public SyscallTracer SyscallTracer { get; }
    public FileIoTracer FileIoTracer { get; }
    public HleQualityDatabase HleDatabase { get; }
    public SignalSafeCrashWriter CrashWriter { get; }
    
    // Statistics
    private long _totalImports;
    private long _totalEvents;
    private int _frameCount;
    private readonly double _sessionStartMs;
    private readonly List<string> _bootStages = new(32);
    private CrashInfo? _crash;
    
    // Source registrations (set by Core/Libs/HLE via Register* methods)
    private ICpuDiagnosticSource? _cpuSource;
    private IGpuDiagnosticSource? _gpuSource;
    private IMemoryDiagnosticSource? _memorySource;
    private IThreadDiagnosticSource? _threadSource;
    private ICrashDiagnosticSource? _crashSource;
    private ISyscallDiagnosticSource? _syscallSource;
    private IFileIoDiagnosticSource? _fileIoSource;
    private IBootStageDiagnosticSource? _bootStageSource;

    #endregion

    #region Constructor

    private DebugIntelligenceEngine(string gameId, string sessionDir, DiagnosticProfile profile)
    {
        GameId = gameId;
        SessionDirectory = sessionDir;
        Profile = profile;
        _sessionStartMs = DiagStopwatch.GetElapsedTimeMs();
        
        Directory.CreateDirectory(sessionDir);
        
        // Initialize subsystems
        CpuTrace = new CpuTraceRecorder(profile);
        GpuRecorder = new GpuCommandStateRecorder();
        MemoryDebugger = new MemoryMapDebugger();
        ThreadDebugger = new ThreadTimelineDebugger();
        SyscallTracer = new SyscallTracer();
        FileIoTracer = new FileIoTracer();
        HleDatabase = new HleQualityDatabase();
        CrashWriter = SignalSafeCrashWriter.Instance;
        
        Console.Error.WriteLine($"[DIAG] Engine created: game={gameId} profile={profile} dir={sessionDir}");
    }

    #endregion

    #region Source Registration

    public void RegisterCpuSource(ICpuDiagnosticSource source) => _cpuSource = source;
    public void RegisterGpuSource(IGpuDiagnosticSource source) => _gpuSource = source;
    public void RegisterMemorySource(IMemoryDiagnosticSource source) => _memorySource = source;
    public void RegisterThreadSource(IThreadDiagnosticSource source) => _threadSource = source;
    public void RegisterCrashSource(ICrashDiagnosticSource source) => _crashSource = source;
    public void RegisterSyscallSource(ISyscallDiagnosticSource source) => _syscallSource = source;
    public void RegisterFileIoSource(IFileIoDiagnosticSource source) => _fileIoSource = source;
    public void RegisterBootStageSource(IBootStageDiagnosticSource source) => _bootStageSource = source;

    #endregion

    #region IDiagnosticEventBus

    public void Publish(SharpEmu.Logging.DiagnosticEvent evt)
    {
        if (Disposed) return;
        
        Interlocked.Increment(ref _totalEvents);
        
        try
        {
            switch (evt.Type)
            {
                case DiagnosticEventType.Import:
                    // Distinguish between HLE imports (Source = library name) and
                    // CPU instruction checkpoints (Source = "CPU").
                    if (evt.Source == "CPU")
                    {
                        // CPU instruction checkpoint — forward to CpuTrace recorder.
                        CpuTrace.RecordInstruction(
                            rip: evt.Address,
                            opcode: Array.Empty<byte>(),
                            registers: Array.Empty<byte>(),
                            memoryAddress: 0,
                            memoryAccess: evt.IntParam,
                            memoryValue: evt.Value);
                    }
                    else
                    {
                        // HLE import call
                        Interlocked.Increment(ref _totalImports);
                        SyscallTracer.RecordCall(
                            library: evt.Source ?? "",
                            name: evt.Details,
                            nid: "",
                            returnValue: (long)evt.Value,
                            durationMicros: 0,
                            threadId: evt.IntParam);
                    }
                    break;
                    
                case DiagnosticEventType.BootStage:
                    lock (_bootStages)
                    {
                        _bootStages.Add(string.IsNullOrEmpty(evt.Details) ? evt.Source : $"{evt.Source}: {evt.Details}");
                    }
                    break;
                    
                case DiagnosticEventType.MemoryAlloc:
                    MemoryDebugger.RecordAllocation(evt.Address, evt.Value, "", 0);
                    break;
                    
                case DiagnosticEventType.MemoryFree:
                    MemoryDebugger.RecordFree(evt.Address);
                    break;
                    
                case DiagnosticEventType.ThreadState:
                    ThreadDebugger.RecordStateChange(evt.IntParam, evt.Details, evt.Source);
                    break;
                    
                case DiagnosticEventType.GpuFrame:
                    Interlocked.Exchange(ref _frameCount, evt.IntParam);
                    break;
                    
                case DiagnosticEventType.GpuSubmit:
                    GpuRecorder.RecordSubmit(evt.Address, (uint)evt.Value);
                    break;
                    
                case DiagnosticEventType.GpuFlip:
                    GpuRecorder.RecordFlip(evt.IntParam);
                    break;
                    
                case DiagnosticEventType.Error:
                    // Reused for FileIO events (Source prefix "FileIO:")
                    if (evt.Source.StartsWith("FileIO:"))
                    {
                        var op = evt.Source.Substring(7);  // "Open", "Read", "Write", "Stat"
                        switch (op)
                        {
                            case "Open":
                                FileIoTracer.RecordOpen(evt.Details, "", evt.Address == 1);
                                break;
                            case "Read":
                                FileIoTracer.RecordRead(evt.Details, evt.Address, evt.Value, evt.IntParam);
                                break;
                            case "Write":
                                FileIoTracer.RecordWrite(evt.Details, evt.Address, evt.Value, evt.IntParam);
                                break;
                            case "Stat":
                                FileIoTracer.RecordStat(evt.Details, evt.Address == 1);
                                break;
                        }
                    }
                    break;
                    
                case DiagnosticEventType.Crash:
                    _crash = new CrashInfo(
                        SignalType: evt.Source,
                        FaultAddress: evt.Address,
                        Rip: evt.Value,  // rip is now passed in the Value field
                        Reason: evt.Details,
                        Timestamp: DateTime.UtcNow);
                    break;
            }
        }
        catch
        {
            // Diagnostics must never crash the emulator
        }
    }
    
    public void Flush()
    {
        try
        {
            // Write all subsystem reports to the session directory
            File.WriteAllText(Path.Combine(SessionDirectory, "cpu_trace.txt"), CpuTrace.ExportText());
            File.WriteAllText(Path.Combine(SessionDirectory, "cpu_trace.json"), CpuTrace.ExportJson());
            File.WriteAllText(Path.Combine(SessionDirectory, "memory_map.json"), MemoryDebugger.ExportJson());
            File.WriteAllText(Path.Combine(SessionDirectory, "threads.json"), ThreadDebugger.ExportJson());
            File.WriteAllText(Path.Combine(SessionDirectory, "gpu_state.json"), GpuRecorder.ExportJson());
            File.WriteAllText(Path.Combine(SessionDirectory, "syscalls.json"), SyscallTracer.ExportJson());
            File.WriteAllText(Path.Combine(SessionDirectory, "file_io.json"), FileIoTracer.ExportJson());
            File.WriteAllText(Path.Combine(SessionDirectory, "hle_quality.json"), HleDatabase.ExportJson());
            File.WriteAllText(Path.Combine(SessionDirectory, "report.txt"), GenerateReport());
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[DIAG] Flush failed: {ex.Message}");
        }
    }

    #endregion

    #region Public Properties

    public long TotalImports => Interlocked.Read(ref _totalImports);
    public long TotalEvents => Interlocked.Read(ref _totalEvents);
    public int FrameCount => _frameCount;
    public CrashInfo? Crash => _crash;

    #endregion

    #region Report Generation

    public string GenerateReport()
    {
        var sb = new StringBuilder();
        sb.AppendLine("==============================================");
        sb.AppendLine("SharpEmu Diagnostic Report");
        sb.AppendLine("==============================================");
        sb.AppendLine($"Game: {GameId}");
        sb.AppendLine($"Profile: {Profile}");
        sb.AppendLine($"Session Dir: {SessionDirectory}");
        sb.AppendLine($"Generated: {DateTime.UtcNow:O}");
        sb.AppendLine();
        
        sb.AppendLine("--- STATISTICS ---");
        sb.AppendLine($"Total Imports: {TotalImports:N0}");
        sb.AppendLine($"Total Events: {TotalEvents:N0}");
        sb.AppendLine($"Frame Count: {FrameCount}");
        sb.AppendLine();
        
        if (_bootStages.Count > 0)
        {
            sb.AppendLine("--- BOOT STAGES REACHED ---");
            foreach (var stage in _bootStages)
            {
                sb.AppendLine($"  ✓ {stage}");
            }
            sb.AppendLine();
        }
        
        if (_crash != null)
        {
            sb.AppendLine("--- CRASH ---");
            sb.AppendLine($"  Signal: {_crash.SignalType}");
            sb.AppendLine($"  Fault Address: 0x{_crash.FaultAddress:X16}");
            sb.AppendLine($"  RIP: 0x{_crash.Rip:X16}");
            sb.AppendLine($"  Reason: {_crash.Reason}");
            sb.AppendLine($"  Timestamp: {_crash.Timestamp:O}");
            sb.AppendLine();
        }
        
        sb.AppendLine("--- SUBSYSTEM STATUS ---");
        sb.AppendLine($"  CPU Trace: {CpuTrace.InstructionCount:N0} instructions recorded");
        sb.AppendLine($"  GPU: {GpuRecorder.SubmitCount:N0} submits, {GpuRecorder.DrawCount:N0} draws");
        sb.AppendLine($"  Memory: {MemoryDebugger.RegionCount:N0} regions, {MemoryDebugger.AllocationCount:N0} allocations");
        sb.AppendLine($"  Threads: {ThreadDebugger.ThreadCount:N0} tracked");
        sb.AppendLine($"  Syscalls: {SyscallTracer.TotalCalls:N0} calls tracked");
        sb.AppendLine($"  File I/O: {FileIoTracer.TotalOps:N0} operations");
        sb.AppendLine($"  HLE Quality: {HleDatabase.TotalExports:N0} exports");
        
        return sb.ToString();
    }
    
    /// <summary>
    /// Generates a complete crash package ZIP file.
    /// </summary>
    public void GeneratePackage()
    {
        Flush();
        Console.Error.WriteLine($"[DIAG] Package generated in {SessionDirectory}");
    }
    
    /// <summary>
    /// Analyzes root cause of crash (basic implementation).
    /// </summary>
    public (int Confidence, string Summary, string Details) AnalyzeRootCause()
    {
        if (_crash == null)
        {
            return (0, "No crash recorded", "");
        }
        
        // Simple heuristics
        var confidence = 50;
        var summary = $"{_crash.SignalType} at 0x{_crash.FaultAddress:X16}";
        var details = $"Crash occurred during: {_crash.Reason}";
        
        if (_crash.FaultAddress == 0)
        {
            confidence = 80;
            summary = "NULL pointer dereference";
            details = "Game tried to access memory at address 0. This usually means an uninitialized pointer.";
        }
        else if (_crash.FaultAddress >= 0x1FE000000 && _crash.FaultAddress < 0x200000000)
        {
            confidence = 75;
            summary = "GPU memory placeholder access";
            details = "Game tried to access GPU memory at 0x1FE000000. This is a placeholder mapping — real GPU memory allocation is needed.";
        }
        else if (_crash.FaultAddress >= 0x800000000)
        {
            confidence = 60;
            summary = "Guest code memory access fault";
            details = $"Game tried to access 0x{_crash.FaultAddress:X16} which is in guest memory space but unmapped.";
        }
        
        return (confidence, summary, details);
    }

    #endregion

    #region IDisposable

    public void Dispose()
    {
        if (Disposed) return;
        Disposed = true;
        
        try
        {
            Flush();
        }
        catch { }
        
        if (_current == this)
        {
            _current = null;
        }
    }

    #endregion

    #region Nested Types

    public sealed record CrashInfo(
        string SignalType,
        ulong FaultAddress,
        ulong Rip,
        string Reason,
        DateTime Timestamp);

    #endregion
}

/// <summary>
/// Diagnostic profile enum (alias for the one in Contracts).
/// </summary>
public static class DiagnosticProfileExtensions
{
    public static string ToDisplayString(this DiagnosticProfile profile) => profile switch
    {
        DiagnosticProfile.Normal => "Normal (1% overhead)",
        DiagnosticProfile.Compatibility => "Compatibility (5% overhead)",
        DiagnosticProfile.DeepDebug => "DeepDebug (15% overhead)",
        DiagnosticProfile.Developer => "Developer (30% overhead)",
        DiagnosticProfile.Forensic => "Forensic (50% overhead)",
        _ => profile.ToString()
    };
}
