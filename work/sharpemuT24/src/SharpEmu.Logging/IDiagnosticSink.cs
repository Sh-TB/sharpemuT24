// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

namespace SharpEmu.Logging;

/// <summary>
/// Diagnostic Event Bus - Central pub/sub interface for runtime diagnostics.
/// All emulator subsystems (CPU, HLE, Memory, GPU, Thread) publish events through this sink.
/// The DebugIntelligenceEngine implements this to aggregate and analyze events.
/// </summary>
public interface IDiagnosticSink
{
    /// <summary>
    /// Publishes a diagnostic event from any subsystem.
    /// </summary>
    void Publish(in DiagnosticEvent e);
    
    /// <summary>
    /// Flushes all buffered diagnostics to storage.
    /// Must be safe to call from signal handlers (no allocations).
    /// </summary>
    void Flush();
    
    /// <summary>
    /// Generates the final diagnostic package (reports, ZIP, etc.)
    /// </summary>
    void GeneratePackage();
    
    /// <summary>
    /// Returns true if the engine is active and accepting events.
    /// </summary>
    bool IsActive { get; }
}

/// <summary>
/// Represents a single diagnostic event from any subsystem.
/// Designed to be stack-allocatable and copyable (struct for zero-allocation hot path).
/// </summary>
public readonly record struct DiagnosticEvent(
    DiagnosticEventType Type,
    double TimestampMs,
    string Source,
    string Details,
    ulong Address = 0,
    ulong Value = 0,
    int IntParam = 0,
    object? Payload = null)
{
    public static DiagnosticEvent Import(string nid, string? library = null, ulong returnAddress = 0) => new(
        DiagnosticEventType.Import,
        Stopwatch.GetElapsedTimeMs(),
        "HLE",
        library is not null ? $"{library}:{nid}" : nid,
        returnAddress);
        
    public static DiagnosticEvent BootStage(string stage, string details = "") => new(
        DiagnosticEventType.BootStage,
        Stopwatch.GetElapsedTimeMs(),
        "Boot",
        stage,
        0, 0, 0, details);
        
    public static DiagnosticEvent MemoryAlloc(ulong address, ulong size) => new(
        DiagnosticEventType.MemoryAlloc,
        Stopwatch.GetElapsedTimeMs(),
        "Memory",
        $"alloc 0x{size:X}",
        address, size);
        
    public static DiagnosticEvent MemoryFree(ulong address, ulong size = 0) => new(
        DiagnosticEventType.MemoryFree,
        Stopwatch.GetElapsedTimeMs(),
        "Memory",
        $"free 0x{address:X}",
        address, size);
        
    public static DiagnosticEvent ThreadState(int threadId, string state, string? name = null) => new(
        DiagnosticEventType.ThreadState,
        Stopwatch.GetElapsedTimeMs(),
        "Thread",
        $"{state}{(name != null ? $" ({name})" : "")}",
        0, 0, threadId);
        
    public static DiagnosticEvent GpuFrame(int frameNumber) => new(
        DiagnosticEventType.GpuFrame,
        Stopwatch.GetElapsedTimeMs(),
        "GPU",
        $"frame #{frameNumber}",
        0, 0, frameNumber);
        
    public static DiagnosticEvent GpuFlip(int bufferIndex) => new(
        DiagnosticEventType.GpuFlip,
        Stopwatch.GetElapsedTimeMs(),
        "GPU",
        $"flip buf={bufferIndex}",
        0, 0, bufferIndex);
        
    public static DiagnosticEvent GpuSubmit(uint commandCount) => new(
        DiagnosticEventType.GpuSubmit,
        Stopwatch.GetElapsedTimeMs(),
        "GPU",
        $"submit cmds={commandCount}",
        0, 0, (int)commandCount);
    
    /// <summary>
    /// Boot-stage event: VideoOut was opened by the guest.
    /// </summary>
    public static DiagnosticEvent VideoOutOpen(int handle) => new(
        DiagnosticEventType.BootStage,
        Stopwatch.GetElapsedTimeMs(),
        "VideoOut",
        $"sceVideoOutOpen handle={handle}",
        (ulong)handle, 0, 0);
    
    /// <summary>
    /// Boot-stage event: AGC was initialized.
    /// </summary>
    public static DiagnosticEvent AgcInit() => new(
        DiagnosticEventType.BootStage,
        Stopwatch.GetElapsedTimeMs(),
        "AGC",
        "sceAgcInit",
        0, 0, 0);
        
    public static DiagnosticEvent Crash(string type, string message, ulong address = 0) => new(
        DiagnosticEventType.Crash,
        Stopwatch.GetElapsedTimeMs(),
        "Crash",
        message,
        address, 0, 0, type);
        
    public static DiagnosticEvent Error(string source, string message) => new(
        DiagnosticEventType.Error,
        Stopwatch.GetElapsedTimeMs(),
        source,
        message);
        
    public static DiagnosticEvent WatchpointHit(ulong address, ulong value, string accessType) => new(
        DiagnosticEventType.WatchpointHit,
        Stopwatch.GetElapsedTimeMs(),
        "Watchpoint",
        accessType,
        address, value);
}

/// <summary>
/// Categories of diagnostic events.
/// </summary>
public enum DiagnosticEventType
{
    // Boot lifecycle
    BootStage = 0,
    
    // CPU / Execution
    Import = 1,
    InstructionExecute = 2,
    
    // Memory
    MemoryAlloc = 10,
    MemoryFree = 11,
    WatchpointHit = 12,
    MemoryAccessViolation = 13,
    
    // Threading
    ThreadState = 20,
    ThreadCreate = 21,
    ThreadExit = 22,
    MutexLock = 23,
    MutexUnlock = 24,
    CondWait = 25,
    CondSignal = 26,
    SemaphoreWait = 27,
    SemaphorePost = 28,
    
    // GPU / Vulkan
    GpuInit = 30,
    GpuFrame = 31,
    GpuFlip = 32,
    GpuSubmit = 33,
    GpuDraw = 34,
    GpuDispatch = 35,
    VideoOutOpen = 36,
    
    // Errors & Crashes
    Error = 90,
    Crash = 91,
    UnhandledException = 92,
    
    // System
    StateChange = 100,
    CostSample = 101
}

/// <summary>
/// High-resolution timestamp helper for diagnostics.
/// Made public so other SharpEmu assemblies (Diagnostics, Core, Libs) can use it
/// without needing to declare their own.
/// Named 'DiagStopwatch' to avoid clashing with System.Diagnostics.Stopwatch.
/// </summary>
public static class DiagStopwatch
{
    private static readonly long _start = System.Diagnostics.Stopwatch.GetTimestamp();
    private static readonly double _frequency = (double)System.Diagnostics.Stopwatch.Frequency;
    
    public static double GetElapsedTimeMs()
    {
        var elapsed = System.Diagnostics.Stopwatch.GetTimestamp() - _start;
        return (elapsed / _frequency) * 1000.0;
    }
}

// Backwards-compat alias for any code that still references 'Logging.Stopwatch'.
// Resolves the ambiguity by explicitly redirecting to DiagStopwatch.
public static class Stopwatch
{
    public static double GetElapsedTimeMs() => DiagStopwatch.GetElapsedTimeMs();
}
