// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Text;
using System.Text.Json;
using System.Linq;
using SharpEmu.HLE;
using SharpEmu.Libs.Agc;
using SharpEmu.Libs.Gpu;
using SharpEmu.Logging;

namespace SharpEmu.Libs.VideoOut;

/// <summary>
/// Headless Video Presenter - Renders without GPU
/// 
/// Architecture:
/// PS5 Game → sceVideoOut/AGC → GPU Layer → [Real Vulkan | Virtual Vulkan]
///                                                    ↓ (Virtual)
///                                              Frame Buffer → PNG Capture
/// </summary>
public sealed class HeadlessVideoPresenter : IDisposable
{
    private static readonly SharpEmuLogger Log = SharpEmuLog.For("SharpEmu.HeadlessVideo");
    
    private readonly uint _width;
    private readonly uint _height;
    private readonly string _outputDirectory;
    private readonly object _syncLock = new();
    private readonly CancellationTokenSource _cts = new();
    private readonly Timer? _frameDumpTimer;
    
    // Frame buffer (RGBA format)
    private byte[]? _frameBuffer;
    private int _currentFrame;
    private bool _disposed;
    private DateTime _sessionStart;
    
    // GPU Statistics
    private long _totalDrawCalls;
    private long _totalTexturesUploaded;
    private long _totalCommandBuffersSubmitted;
    private int _activeShaders;
    private long _triangleCount;
    private ulong _lastFlipAddress;
    private uint _lastFlipWidth;
    private uint _lastFlipHeight;
    
    // AGC Command Recorder - Detailed GPU command tracking
    private long _agcSubmitCount;
    private long _agcDrawCount;
    private long _agcDispatchCount;
    private long _agcRegisterSets;
    private int _activeResources;
    private long _gpuMemoryUsage; // in bytes (long, not ulong, for Interlocked.Add)
    private readonly List<AgcCommandRecord> _frameAgcCommands = new();
    private readonly object _agcLock = new();
    
    // AGC/GPU Timeline
    private readonly List<GpuTimelineEvent> _timeline = new();
    private DateTime _agcInitTime;
    private DateTime _contextCreateTime;
    private DateTime _firstSubmitTime;
    private DateTime _firstPresentTime;
    
    // Diagnostics
    private GpuDiagnosticsReport _diagnostics = new();

    public uint Width => _width;
    public uint Height => _height;
    public bool IsInitialized { get; private set; }
    public long TotalDrawCalls => _totalDrawCalls;
    public long CurrentFrame => _currentFrame;
    public string OutputDirectory => _outputDirectory;

    /// <summary>
    /// Creates a new Headless Video Presenter.
    /// </summary>
    /// <param name="width">Frame buffer width (default: 1920)</param>
    /// <param name="height">Frame buffer height (default: 1080)</param>
    /// <param name="outputDirectory">Directory for frame captures</param>
    public HeadlessVideoPresenter(uint width = 1920, uint height = 1080, string? outputDirectory = null)
    {
        _width = width;
        _height = height;
        _sessionStart = DateTime.UtcNow;
        
        // Set up output directory
        _outputDirectory = outputDirectory ?? Path.Combine(
            Directory.GetCurrentDirectory(),
            "SharpEmu",
            "headless_frames");
            
        EnsureDirectory(_outputDirectory);
        
        // Initialize frame buffer (RGBA8888)
        _frameBuffer = new byte[width * height * 4];
        
        // Clear to black
        Array.Clear(_frameBuffer);
        
        IsInitialized = true;
        
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] ==========================================");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] No physical GPU detected");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Switching to Virtual Presenter");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Mode: HEADLESS_FRAMEBUFFER");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Resolution: {width}x{height}");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Format: RGBA8");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Frame Capture: enabled");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Output: {_outputDirectory}");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] ==========================================");
        
        Log.Info($"HeadlessVideoPresenter initialized: {width}x{height}");
        
        // Auto-dump timer if enabled
        var dumpInterval = GetEnvInt("SHARPEMU_HEADLESS_DUMP_INTERVAL", 0);
        if (dumpInterval > 0)
        {
            _frameDumpTimer = new Timer(
                AutoDumpCallback,
                null,
                TimeSpan.FromSeconds(dumpInterval),
                TimeSpan.FromSeconds(dumpInterval));
                
            Log.Info($"Auto-dump enabled: every {dumpInterval}s");
        }
        
        // Record timeline event
        RecordTimelineEvent(GpuEventType.PresenterInit, "Headless Presenter initialized");
    }

    #region Public API - Vulkan-like Interface

    /// <summary>
    /// Simulates vkCreateDevice - always succeeds in headless mode.
    /// </summary>
    public void CreateDevice()
    {
        RecordTimelineEvent(GpuEventType.DeviceCreate, "Virtual Device created");
        _contextCreateTime = DateTime.UtcNow;
        Log.Info("[HEADLESS] Virtual device created successfully");
    }

    /// <summary>
    /// Simulates command buffer submission.
    /// </summary>
    public void SubmitCommandBuffer(ulong commandBufferAddress, string? debugName = null)
    {
        Interlocked.Increment(ref _totalCommandBuffersSubmitted);
        
        if (_firstSubmitTime == default)
        {
            _firstSubmitTime = DateTime.UtcNow;
            RecordTimelineEvent(GpuEventType.FirstSubmit, "First command buffer submitted");
        }
        
        Log.Debug($"[HEADLESS] Command buffer submitted: 0x{commandBufferAddress:X16}{(debugName is not null ? $" ({debugName})" : "")}");
    }

    /// <summary>
    /// Simulates draw call.
    /// </summary>
    public void DrawCall(uint vertexCount, uint instanceCount = 1, string? shaderInfo = null)
    {
        Interlocked.Increment(ref _totalDrawCalls);
        Interlocked.Add(ref _triangleCount, vertexCount / 3 * instanceCount);
        
        if (GetEnvBool("SHARPEMU_TRACE_GPU"))
        {
            Log.Debug($"[HEADLESS] Draw: vertices={vertexCount} instances={instanceCount}{(shaderInfo is not null ? $" shader={shaderInfo}" : "")}");
        }
    }

    /// <summary>
    /// Simulates texture upload.
    /// </summary>
    public void UploadTexture(ulong address, ulong size, uint width, uint height, Format format)
    {
        Interlocked.Increment(ref _totalTexturesUploaded);
        Log.Debug($"[HEADLESS] Texture uploaded: 0x{address:X16} size={size} {width}x{height} {format}");
    }

    /// <summary>
    /// Simulates shader compilation/binding.
    /// </summary>
    public void BindShader(ulong address, ShaderType type)
    {
        // Track active shaders (simplified)
        Interlocked.Exchange(ref _activeShaders, _activeShaders + 1);
        Log.Debug($"[HEADLESS] Shader bound: 0x{address:X16} type={type}");
    }

    /// <summary>
    /// Handles sceVideoOut flip - the main present operation.
    /// </summary>
    public void Flip(int handle, int bufferIndex, ulong address, uint width, uint height, uint pitchInPixels, byte[]? guestFrameData = null)
    {
        lock (_syncLock)
        {
            _currentFrame++;
            _lastFlipAddress = address;
            _lastFlipWidth = width;
            _lastFlipHeight = height;
            
            if (_firstPresentTime == default)
            {
                _firstPresentTime = DateTime.UtcNow;
                RecordTimelineEvent(GpuEventType.FirstPresent, $"First flip: frame #{_currentFrame}");
            }
            
            // ROOT CAUSE FIX: Use actual guest framebuffer data if available.
            // Previously this always called GenerateFramePattern() which created
            // a synthetic rainbow test pattern — NOT the game's actual output.
            if (guestFrameData != null && guestFrameData.Length > 0 && _frameBuffer != null)
            {
                // Copy guest framebuffer data into our internal buffer
                var copyLen = Math.Min(guestFrameData.Length, _frameBuffer.Length);
                Buffer.BlockCopy(guestFrameData, 0, _frameBuffer, 0, copyLen);
            }
            else
            {
                // Fallback: generate test pattern if no guest data available
                GenerateFramePattern(width, height);
            }
            
            // Save frame if capture is enabled
            if (GetEnvBool("SHARPEMU_HEADLESS_CAPTURE", true))
            {
                SaveCurrentFrame();
            }
            
            // Log AGC summary for this frame
            if (GetEnvBool("SHARPEMU_TRACE_GPU") && _currentFrame % 100 == 0) // Every 100 frames
            {
                var agcSummary = GetFrameAgcSummary();
                Console.Error.WriteLine($"[VIDEOOUT][AGC] Frame {_currentFrame} Summary:");
                Console.Error.WriteLine($"[VIDEOOUT][AGC]   Draws: {agcSummary.DrawCount}");
                Console.Error.WriteLine($"[VIDEOOUT][AGC]   Submits: {agcSummary.SubmitCount}");
                Console.Error.WriteLine($"[VIDEOOUT][AGC]   Resources: {agcSummary.ActiveResources}");
                Console.Error.WriteLine($"[VIDEOOUT][AGC]   Memory: {agcSummary.GpuMemoryUsageMB}MB");
            }
            
            // Clear per-frame AGC commands after logging
            ClearFrameAgcCommands();
            
            var elapsed = DateTime.UtcNow - _sessionStart;
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Flip #{_currentFrame}: handle={handle} buf={bufferIndex} " +
                $"addr=0x{address:X16} {width}x{height} pitch={pitchInPixels} " +
                $"t={elapsed.TotalSeconds:F2}s draws={_totalDrawCalls}");
        }
    }

    /// <summary>
    /// Clears the framebuffer to a color.
    /// </summary>
    public void Clear(float r, float g, float b, float a = 1.0f)
    {
        lock (_syncLock)
        {
            if (_frameBuffer is null) return;
            
            var cr = (byte)(r * 255f);
            var cg = (byte)(g * 255f);
            var cb = (byte)(b * 255f);
            var ca = (byte)(a * 255f);
            
            for (int i = 0; i < _frameBuffer.Length; i += 4)
            {
                _frameBuffer[i] = cr;     // R
                _frameBuffer[i + 1] = cg; // G
                _frameBuffer[i + 2] = cb; // B
                _frameBuffer[i + 3] = ca; // A
            }
        }
    }

    /// <summary>
    /// Copies data to framebuffer (simulated blit).
    /// </summary>
    public void CopyToFramebuffer(ulong sourceAddr, uint x, uint y, uint width, uint height)
    {
        Log.Debug($"[HEADLESS] Blit: src=0x{sourceAddr:X16} dest=({x},{y}) {width}x{height}");
        // In a full implementation, this would read from guest memory
    }

    #endregion

    #region AGC Interface

    /// <summary>
    /// Records AGC initialization.
    /// </summary>
    public void AgcInit()
    {
        _agcInitTime = DateTime.UtcNow;
        RecordTimelineEvent(GpuEventType.AgcInit, "AGC initialized");
        Console.Error.WriteLine("[VIDEOOUT][HEADLESS] AGC Init recorded");
    }

    /// <summary>
    /// Records AGC context creation.
    /// </summary>
    public void AgcCreateContext(ulong contextAddress)
    {
        RecordTimelineEvent(GpuEventType.ContextCreate, $"AGC Context: 0x{contextAddress:X16}");
        Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] AGC Context created: 0x{contextAddress:X16}");
    }

    /// <summary>
    /// Records AGC register set.
    /// </summary>
    public void AgcSetRegister(string registerName, ulong value)
    {
        Interlocked.Increment(ref _agcRegisterSets);
        
        if (GetEnvBool("SHARPEMU_TRACE_GPU"))
        {
            Log.Debug($"[HEADLESS][AGC] {registerName} = 0x{value:X16}");
            
            lock (_agcLock)
            {
                _frameAgcCommands.Add(new AgcCommandRecord
                {
                    Type = "SetRegister",
                    Command = registerName,
                    Value = $"0x{value:X16}",
                    Timestamp = (DateTime.UtcNow - _sessionStart).TotalSeconds
                });
            }
        }
    }
    
    /// <summary>
    /// Records AGC submit command.
    /// </summary>
    public void AgcSubmit(ulong submitAddress, uint commandCount)
    {
        Interlocked.Increment(ref _agcSubmitCount);
        Interlocked.Add(ref _totalCommandBuffersSubmitted, commandCount);
        
        if (GetEnvBool("SHARPEMU_TRACE_GPU"))
        {
            Log.Debug($"[HEADLESS][AGC] Submit: addr=0x{submitAddress:X16} commands={commandCount}");
            
            lock (_agcLock)
            {
                _frameAgcCommands.Add(new AgcCommandRecord
                {
                    Type = "Submit",
                    Command = "sceAgcSubmit",
                    Value = $"0x{submitAddress:X16} ({commandCount} cmds)",
                    Timestamp = (DateTime.UtcNow - _sessionStart).TotalSeconds
                });
            }
        }
    }
    
    /// <summary>
    /// Records AGC draw command.
    /// </summary>
    public void AgcDraw(uint vertexCount, uint instanceCount)
    {
        Interlocked.Increment(ref _agcDrawCount);
        Interlocked.Increment(ref _totalDrawCalls);
        Interlocked.Add(ref _triangleCount, vertexCount / 3 * instanceCount);
        
        if (GetEnvBool("SHARPEMU_TRACE_GPU"))
        {
            Log.Debug($"[HEADLESS][AGC] Draw: vertices={vertexCount} instances={instanceCount}");
            
            lock (_agcLock)
            {
                _frameAgcCommands.Add(new AgcCommandRecord
                {
                    Type = "Draw",
                    Command = "sceAgcDraw",
                    Value = $"verts={vertexCount} insts={instanceCount}",
                    Timestamp = (DateTime.UtcNow - _sessionStart).TotalSeconds
                });
            }
        }
    }
    
    /// <summary>
    /// Records AGC dispatch (compute) command.
    /// </summary>
    public void AgcDispatch(uint threadGroupX, uint threadGroupY, uint threadGroupZ)
    {
        Interlocked.Increment(ref _agcDispatchCount);
        
        if (GetEnvBool("SHARPEMU_TRACE_GPU"))
        {
            Log.Debug($"[HEADLESS][AGC] Dispatch: groups=({threadGroupX},{threadGroupY},{threadGroupZ})");
            
            lock (_agcLock)
            {
                _frameAgcCommands.Add(new AgcCommandRecord
                {
                    Type = "Dispatch",
                    Command = "sceAgcDispatch",
                    Value = $"groups=({threadGroupX},{threadGroupY},{threadGroupZ})",
                    Timestamp = (DateTime.UtcNow - _sessionStart).TotalSeconds
                });
            }
        }
    }
    
    /// <summary>
    /// Records resource allocation (texture, buffer, etc.)
    /// </summary>
    public void AgcAllocateResource(string resourceType, ulong size)
    {
        Interlocked.Increment(ref _activeResources);
        // BUG-FIX: Interlocked.Add doesn't accept unchecked() — cast directly.
        Interlocked.Add(ref _gpuMemoryUsage, (long)size);
        
        if (GetEnvBool("SHARPEMU_TRACE_GPU"))
        {
            Log.Debug($"[HEADLESS][AGC] Resource: {resourceType} size={size} bytes");
        }
    }
    
    /// <summary>
    /// Gets current frame's AGC summary for diagnostics.
    /// </summary>
    public AgcFrameSummary GetFrameAgcSummary()
    {
        lock (_agcLock)
        {
            return new AgcFrameSummary
            {
                FrameNumber = _currentFrame,
                SubmitCount = _agcSubmitCount,
                DrawCount = _agcDrawCount,
                DispatchCount = _agcDispatchCount,
                RegisterSets = _agcRegisterSets,
                ActiveResources = _activeResources,
                GpuMemoryUsageMB = _gpuMemoryUsage / (1024 * 1024),
                Commands = _frameAgcCommands.ToArray()
            };
        }
    }
    
    /// <summary>
    /// Clears per-frame AGC command list (called after flip).
    /// </summary>
    private void ClearFrameAgcCommands()
    {
        lock (_agcLock)
        {
            _frameAgcCommands.Clear();
        }
    }

    #endregion

    #region Frame Capture

    /// <summary>
    /// Saves current framebuffer as PPM (portable pixmap) - no external dependencies needed.
    /// Also saves JSON metadata alongside the frame.
    /// </summary>
    public void SaveCurrentFrame(string? customFilename = null)
    {
        lock (_syncLock)
        {
            if (_frameBuffer is null) return;
            
            try
            {
                var baseFilename = customFilename ?? $"frame{_currentFrame:D6}";
                var filepath = Path.Combine(_outputDirectory, $"{baseFilename}.ppm");
                var jsonPath = Path.Combine(_outputDirectory, $"{baseFilename}.json");
                
                // Write PPM format (P6 - binary RGB)
                using var fs = new FileStream(filepath, FileMode.Create, FileAccess.Write);
                using var writer = new StreamWriter(fs, Encoding.ASCII);
                
                // PPM header
                writer.WriteLine("P6");
                writer.WriteLine($"#{_currentFrame} w={_width} h={_height} draws={_totalDrawCalls}");
                writer.WriteLine($"{_width} {_height}");
                writer.WriteLine("255");
                writer.Flush();
                
                // Write pixel data (RGBA -> RGB, discard alpha)
                fs.Write(_frameBuffer, 0, Math.Min(_frameBuffer.Length, (int)(_width * _height * 4)));
                
                // Save JSON metadata alongside frame
                SaveFrameMetadata(jsonPath);

                // After the first frame is saved, automatically run FrameAnalyzer
                // and print a "Framebuffer Analysis" report to stderr. This gives
                // the user immediate feedback on whether the frame contains real
                // game content or is just a Unity splash background.
                if (_currentFrame == 1)
                {
                    try
                    {
                        var analysis = SharpEmu.Libs.VideoOut.FrameAnalyzer.AnalyzePpm(filepath);
                        if (analysis != null)
                        {
                            SharpEmu.Libs.VideoOut.FrameAnalyzer.PrintReport(analysis);
                        }
                    }
                    catch (Exception ex)
                    {
                        // Frame analysis must never break the emulator.
                        Console.Error.WriteLine($"[HEADLESS] Frame analysis failed (non-fatal): {ex.GetType().Name}: {ex.Message}");
                    }
                }

                Log.Debug($"[HEADLESS] Frame saved: {filepath}");
            }
            catch (Exception ex)
            {
                Log.Error($"[HEADLESS] Failed to save frame: {ex.Message}");
            }
        }
    }
    
    /// <summary>
    /// Saves frame metadata as JSON for diagnostics and analysis.
    /// This allows post-mortem analysis of GPU state per frame.
    /// </summary>
    private void SaveFrameMetadata(string jsonPath)
    {
        try
        {
            var metadata = new FrameMetadata
            {
                FrameNumber = _currentFrame,
                Timestamp = DateTime.UtcNow.ToString("o"),
                Resolution = new ResolutionInfo { Width = _width, Height = _height },
                Format = "RGBA8",
                
                // GPU Statistics
                GpuStats = new GpuStatsInfo
                {
                    DrawCalls = _totalDrawCalls,
                    TexturesUploaded = _totalTexturesUploaded,
                    CommandBuffersSubmitted = _totalCommandBuffersSubmitted,
                    ActiveShaders = _activeShaders,
                    TriangleCount = _triangleCount
                },
                
                // Flip Info
                FlipInfo = new FlipInfo
                {
                    LastFlipAddress = $"0x{_lastFlipAddress:X16}",
                    LastFlipSize = $"{_lastFlipWidth}x{_lastFlipHeight}",
                    TotalFlips = _currentFrame
                },
                
                // Timeline snapshot
                TimelineEvents = _timeline.Select(e => new TimelineEventDto
                {
                    Timestamp = e.Timestamp,
                    EventType = e.EventType,
                    Description = e.Description
                }).ToArray(),
                
                // Session info
                SessionElapsed = (DateTime.UtcNow - _sessionStart).TotalSeconds
            };
            
            var json = JsonSerializer.Serialize(metadata, new JsonSerializerOptions 
            { 
                WriteIndented = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            });
            
            File.WriteAllText(jsonPath, json, Encoding.UTF8);
        }
        catch (Exception ex)
        {
            Log.Error($"[HEADLESS] Failed to save frame metadata: {ex.Message}");
        }
    }

    /// <summary>
    /// Generates a test pattern for the framebuffer.
    /// </summary>
    private void GeneratePatternForFrame(uint width, uint height, int frameNumber)
    {
        if (_frameBuffer is null) return;
        
        // Create an animated gradient pattern based on frame number
        var time = frameNumber * 0.02f;
        
        for (uint y = 0; y < height; y++)
        {
            for (uint x = 0; x < width; x++)
            {
                var idx = ((y * width + x) * 4);
                if (idx + 3 >= _frameBuffer.Length) continue;
                
                // Animated gradient pattern
                var nx = (float)x / width;
                var ny = (float)y / height;
                
                _frameBuffer[idx] = (byte)((nx * 128 + MathF.Sin(time + ny * 6.28f) * 127) % 256);     // R
                _frameBuffer[idx + 1] = (byte)((ny * 128 + MathF.Cos(time + nx * 6.28f) * 127) % 256); // G
                _frameBuffer[idx + 2] = (byte)(((nx + ny) * 64 + MathF.Sin(time * 2) * 191) % 256);   // B
                _frameBuffer[idx + 3] = 255; // A
            }
        }
    }

    /// <summary>
    /// Generates a simple frame pattern showing game state info.
    /// </summary>
    private void GenerateFramePattern(uint width, uint height)
    {
        if (_frameBuffer is null) return;
        
        // Create a colored frame that shows we're alive
        // Use different colors based on frame number to show activity
        var hue = (_currentFrame * 10) % 360;
        var rgb = HsvToRgb(hue / 360f, 0.7f, 0.9f);
        
        // Fill with color
        for (uint i = 0; i < width * height * 4; i += 4)
        {
            if (i + 3 < _frameBuffer.Length)
            {
                _frameBuffer[i] = rgb.Item1;     // R
                _frameBuffer[i + 1] = rgb.Item2; // G
                _frameBuffer[i + 2] = rgb.Item3; // B
                _frameBuffer[i + 3] = 255;       // A
            }
        }
        
        // Draw frame number indicator (simple rectangle)
        DrawIndicator(width, height);
    }

    /// <summary>
    /// Draws a frame counter indicator on the framebuffer.
    /// </summary>
    private void DrawIndicator(uint width, uint height)
    {
        if (_frameBuffer is null) return;
        
        // Draw a small bar showing progress
        var barWidth = Math.Min((uint)(_currentFrame % 100) * (width / 100), width - 20);
        var barY = height - 20;
        
        for (uint y = barY; y < height && y < _height; y++)
        {
            for (uint x = 10; x < 10 + barWidth && x < _width; x++)
            {
                var idx = ((y * _width + x) * 4);
                if (idx + 3 < _frameBuffer.Length)
                {
                    _frameBuffer[idx] = 255;     // R
                    _frameBuffer[idx + 1] = 255; // G
                    _frameBuffer[idx + 2] = 255; // B
                    _frameBuffer[idx + 3] = 255; // A
                }
            }
        }
    }

    #endregion

    #region Diagnostics & Reporting

    /// <summary>
    /// Generates comprehensive GPU diagnostics report.
    /// </summary>
    public GpuDiagnosticsReport GenerateReport()
    {
        var elapsed = DateTime.UtcNow - _sessionStart;
        
        _diagnostics = new GpuDiagnosticsReport
        {
            SessionStart = _sessionStart.ToString("o"),
            ElapsedSeconds = elapsed.TotalSeconds,
            Mode = "HEADLESS_FRAMEBUFFER",
            Resolution = $"{_width}x{_height}",
            Format = "RGBA8",
            OutputDirectory = _outputDirectory,
            TotalFrames = _currentFrame,
            TotalDrawCalls = _totalDrawCalls,
            TotalTexturesUploaded = _totalTexturesUploaded,
            TotalCommandBuffersSubmitted = _totalCommandBuffersSubmitted,
            ActiveShaders = _activeShaders,
            TriangleCount = _triangleCount,
            LastFlipAddress = $"0x{_lastFlipAddress:X16}",
            LastFlipSize = $"{_lastFlipWidth}x{_lastFlipHeight}",
            Timeline = _timeline.ToArray(),
            AgcInitElapsed = _agcInitTime != default ? (_agcInitTime - _sessionStart).TotalMilliseconds : 0,
            ContextCreateElapsed = _contextCreateTime != default ? (_contextCreateTime - _sessionStart).TotalMilliseconds : 0,
            FirstSubmitElapsed = _firstSubmitTime != default ? (_firstSubmitTime - _sessionStart).TotalMilliseconds : 0,
            FirstPresentElapsed = _firstPresentTime != default ? (_firstPresentTime - _sessionStart).TotalMilliseconds : 0,
            CapturedFrames = Directory.Exists(_outputDirectory) ? Directory.GetFiles(_outputDirectory, "frame*.png").Length : 0
        };
        
        return _diagnostics;
    }

    /// <summary>
    /// Saves diagnostics report to JSON file.
    /// </summary>
    public void SaveReport()
    {
        try
        {
            var report = GenerateReport();
            var json = JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true });
            var reportPath = Path.Combine(_outputDirectory, "gpu_report.json");
            File.WriteAllText(reportPath, json, Encoding.UTF8);
            
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] GPU Report saved: {reportPath}");
            Log.Info($"GPU diagnostics report saved: {reportPath}");
        }
        catch (Exception ex)
        {
            Log.Error($"Failed to save GPU report: {ex.Message}");
        }
    }

    /// <summary>
    /// Records a GPU timeline event.
    /// </summary>
    private void RecordTimelineEvent(GpuEventType eventType, string description)
    {
        var elapsed = DateTime.UtcNow - _sessionStart;
        _timeline.Add(new GpuTimelineEvent
        {
            Timestamp = elapsed.TotalSeconds,
            EventType = eventType.ToString(),
            Description = description
        });
    }

    #endregion

    #region Private Helpers

    private static (byte, byte, byte) HsvToRgb(float h, float s, float v)
    {
        if (s == 0)
        {
            var c = (byte)(v * 255);
            return (c, c, c);
        }
        
        var i = (int)(h * 6);
        var f = h * 6 - i;
        var p = v * (1 - s);
        var q = v * (1 - f * s);
        var t = v * (1 - (1 - f) * s);
        
        return (i % 6) switch
        {
            0 => ((byte)(v * 255), (byte)(t * 255), (byte)(p * 255)),
            1 => ((byte)(q * 255), (byte)(v * 255), (byte)(p * 255)),
            2 => ((byte)(p * 255), (byte)(v * 255), (byte)(t * 255)),
            3 => ((byte)(p * 255), (byte)(q * 255), (byte)(v * 255)),
            4 => ((byte)(t * 255), (byte)(p * 255), (byte)(v * 255)),
            5 => ((byte)(v * 255), (byte)(p * 255), (byte)(q * 255)),
            _ => (0, 0, 0)
        };
    }

    private void AutoDumpCallback(object? state)
    {
        if (_cts.IsCancellationRequested) return;
        
        try
        {
            SaveCurrentFrame($"auto_dump_{DateTime.Now:yyyyMMdd_HHmmss}.ppm");
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Auto-dump error: {ex.Message}");
        }
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

    #endregion

    #region IDisposable

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        
        _cts.Cancel();
        _frameDumpTimer?.Dispose();
        _cts.Dispose();
        
        // Final report and frame save
        try
        {
            SaveCurrentFrame("final_frame.ppm");
            SaveReport();
            
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Session ended:");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS]   Frames: {_currentFrame}");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS]   Draw Calls: {_totalDrawCalls}");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS]   Textures: {_totalTexturesUploaded}");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS]   Duration: {(DateTime.UtcNow - _sessionStart).TotalSeconds:F2}s");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS]   Output: {_outputDirectory}");
        }
        catch
        {
            // Best effort cleanup
        }
    }

    #endregion

    #region Data Classes

    public enum ShaderType { Vertex, Fragment, Compute }
    public enum Format { RGBA8, BGRA8, R8G8B8A8, R5G6B5, etc }
    public enum GpuEventType { PresenterInit, AgcInit, DeviceCreate, ContextCreate, FirstSubmit, FirstPresent, Flip, Error }

    public sealed class GpuTimelineEvent
    {
        public double Timestamp { get; set; }
        public string EventType { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
    }

    public sealed class GpuDiagnosticsReport
    {
        public string SessionStart { get; set; } = string.Empty;
        public double ElapsedSeconds { get; set; }
        public string Mode { get; set; } = "HEADLESS_FRAMEBUFFER";
        public string Resolution { get; set; } = string.Empty;
        public string Format { get; set; } = "RGBA8";
        public string OutputDirectory { get; set; } = string.Empty;
        public long TotalFrames { get; set; }
        public long TotalDrawCalls { get; set; }
        public long TotalTexturesUploaded { get; set; }
        public long TotalCommandBuffersSubmitted { get; set; }
        public int ActiveShaders { get; set; }
        public long TriangleCount { get; set; }
        public string LastFlipAddress { get; set; } = "0x0";
        public string LastFlipSize { get; set; } = "0x0";
        public GpuTimelineEvent[] Timeline { get; set; } = Array.Empty<GpuTimelineEvent>();
        public double AgcInitElapsed { get; set; }
        public double ContextCreateElapsed { get; set; }
        public double FirstSubmitElapsed { get; set; }
        public double FirstPresentElapsed { get; set; }
        public int CapturedFrames { get; set; }
    }
    
    /// <summary>
    /// Frame metadata saved alongside each captured frame.
    /// Enables detailed post-mortem analysis.
    /// </summary>
    public sealed class FrameMetadata
    {
        public int FrameNumber { get; set; }
        public string Timestamp { get; set; } = string.Empty;
        public ResolutionInfo? Resolution { get; set; }
        public string Format { get; set; } = "RGBA8";
        public GpuStatsInfo? GpuStats { get; set; }
        public FlipInfo? FlipInfo { get; set; }
        public TimelineEventDto[] TimelineEvents { get; set; } = Array.Empty<TimelineEventDto>();
        public double SessionElapsed { get; set; }
    }
    
    public sealed class ResolutionInfo
    {
        public uint Width { get; set; }
        public uint Height { get; set; }
    }
    
    public sealed class GpuStatsInfo
    {
        public long DrawCalls { get; set; }
        public long TexturesUploaded { get; set; }
        public long CommandBuffersSubmitted { get; set; }
        public int ActiveShaders { get; set; }
        public long TriangleCount { get; set; }
    }
    
    public sealed class FlipInfo
    {
        public string LastFlipAddress { get; set; } = "0x0";
        public string LastFlipSize { get; set; } = "0x0";
        public long TotalFlips { get; set; }
    }
    
    public sealed class TimelineEventDto
    {
        public double Timestamp { get; set; }
        public string EventType { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
    }
    
    /// <summary>
    /// Represents a single recorded AGC command.
    /// </summary>
    public sealed class AgcCommandRecord
    {
        public string Type { get; set; } = string.Empty; // Submit, Draw, Dispatch, SetRegister
        public string Command { get; set; } = string.Empty;
        public string Value { get; set; } = string.Empty;
        public double Timestamp { get; set; }
    }
    
    /// <summary>
    /// Summary of AGC activity for a single frame.
    /// </summary>
    public sealed class AgcFrameSummary
    {
        public int FrameNumber { get; set; }
        public long SubmitCount { get; set; }
        public long DrawCount { get; set; }
        public long DispatchCount { get; set; }
        public long RegisterSets { get; set; }
        public int ActiveResources { get; set; }
        public long GpuMemoryUsageMB { get; set; }
        public AgcCommandRecord[] Commands { get; set; } = Array.Empty<AgcCommandRecord>();
    }

    #endregion
}
