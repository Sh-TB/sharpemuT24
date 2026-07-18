// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

// ============================================================================
// DIAGNOSTIC RUNTIME ADAPTER
//
// This file bridges the Emulator Core to the Diagnostics subsystem via
// the Contracts interfaces. Core calls DiagnosticAdapter.* (which is in-process
// and fast); the Adapter delegates to whatever IDiagnosticEventBus is currently
// registered (set by SharpEmu.CLI at startup).
//
// ARCHITECTURE:
// - Core calls DiagnosticAdapter.NotifyInstruction(...) etc.
// - Adapter checks if a bus is registered.
// - If yes, publishes via the bus (Diagnostics subsystem receives).
// - If no, returns immediately (zero overhead).
//
// This breaks the circular dependency: Core no longer references Diagnostics.
// ============================================================================

using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Logging;

namespace SharpEmu.Diagnostics.Contracts;

/// <summary>
/// Static adapter that the Emulator Core/Libs/HLE use to publish diagnostic events.
/// This is the ONLY entry point from Core/Libs/HLE into the Diagnostics subsystem.
/// </summary>
public static class DiagnosticAdapter
{
    private static IDiagnosticEventBus? _bus;
    private static ICpuDiagnosticSource? _cpuSource;
    private static IGpuDiagnosticSource? _gpuSource;
    private static IMemoryDiagnosticSource? _memorySource;
    private static IThreadDiagnosticSource? _threadSource;
    private static ICrashDiagnosticSource? _crashSource;
    private static ISyscallDiagnosticSource? _syscallSource;
    private static IFileIoDiagnosticSource? _fileIoSource;
    private static IBootStageDiagnosticSource? _bootStageSource;
    
    /// <summary>
    /// True if any diagnostic bus is registered and active.
    /// </summary>
    public static bool IsActive => _bus?.IsActive ?? false;
    
    /// <summary>
    /// The currently-registered event bus, or null.
    /// (Libs/HLE use this to call Publish directly with custom events.)
    /// </summary>
    public static IDiagnosticEventBus? Bus => _bus;
    
    /// <summary>
    /// Registers the diagnostic event bus (called by SharpEmu.CLI at startup).
    /// </summary>
    public static void RegisterBus(IDiagnosticEventBus bus)
    {
        _bus = bus;
    }
    
    public static void RegisterCpuSource(ICpuDiagnosticSource source) => _cpuSource = source;
    public static void RegisterGpuSource(IGpuDiagnosticSource source) => _gpuSource = source;
    public static void RegisterMemorySource(IMemoryDiagnosticSource source) => _memorySource = source;
    public static void RegisterThreadSource(IThreadDiagnosticSource source) => _threadSource = source;
    public static void RegisterCrashSource(ICrashDiagnosticSource source) => _crashSource = source;
    public static void RegisterSyscallSource(ISyscallDiagnosticSource source) => _syscallSource = source;
    public static void RegisterFileIoSource(IFileIoDiagnosticSource source) => _fileIoSource = source;
    public static void RegisterBootStageSource(IBootStageDiagnosticSource source) => _bootStageSource = source;
    
    // ========================================================
    // Convenience methods — Core calls these instead of RealRuntimeHooks
    // ========================================================
    
    public static void NotifyInstruction(
        ulong rip,
        ReadOnlySpan<byte> opcode,
        ReadOnlySpan<byte> registers,
        ulong memoryAddress = 0,
        int memoryAccess = 0,
        ulong memoryValue = 0)
    {
        if (!IsActive) return;
        _cpuSource?.RecordInstruction(rip, opcode, registers, memoryAddress, memoryAccess, memoryValue);
        // Also publish to bus so DebugIntelligenceEngine.CpuTrace receives it.
        // We use the Import event type as a generic "instruction checkpoint" since
        // DiagnosticEventType doesn't have a dedicated Instruction type.
        // The engine's CpuTrace subsystem records it.
        _bus?.Publish(new DiagnosticEvent(
            DiagnosticEventType.Import,  // reuse Import type for instruction checkpoints
            DiagStopwatch.GetElapsedTimeMs(),
            "CPU",
            $"rip=0x{rip:X16}",
            rip,
            memoryValue,
            memoryAccess));
    }
    
    public static void NotifyInstructionLightweight(ulong rip)
    {
        if (!IsActive) return;
        _cpuSource?.RecordInstructionLightweight(rip);
        _bus?.Publish(new DiagnosticEvent(
            DiagnosticEventType.Import,
            DiagStopwatch.GetElapsedTimeMs(),
            "CPU",
            $"rip=0x{rip:X16} (lightweight)",
            rip, 0, 0));
    }
    
    public static void NotifyGpuSubmit(ulong commandBufferAddress, uint commandCount)
    {
        if (!IsActive) return;
        _gpuSource?.RecordSubmit(commandBufferAddress, commandCount);
        _bus?.Publish(DiagnosticEvent.GpuSubmit(commandCount));
    }
    
    public static void NotifyGpuDraw(uint vertexCount, uint instanceCount, ulong shaderId)
    {
        if (!IsActive) return;
        _gpuSource?.RecordDraw(vertexCount, instanceCount, shaderId);
    }
    
    public static void NotifyGpuDispatch(uint x, uint y, uint z)
    {
        if (!IsActive) return;
        _gpuSource?.RecordDispatch(x, y, z);
    }
    
    public static void NotifyShaderCompiled(ulong shaderId, byte[] sourceHash, string shaderType, bool success, string? error = null)
    {
        if (!IsActive) return;
        _gpuSource?.RecordShaderCompiled(shaderId, sourceHash, shaderType, success, error);
    }
    
    public static void NotifyGpuResourceCreated(ulong address, string type, ulong size, string format)
    {
        if (!IsActive) return;
        _gpuSource?.RecordResourceCreated(address, type, size, format);
    }
    
    public static void NotifyGpuResourceDestroyed(ulong address)
    {
        if (!IsActive) return;
        _gpuSource?.RecordResourceDestroyed(address);
    }
    
    public static void NotifyMemoryAllocated(ulong address, ulong size, string allocator, ulong callerAddress)
    {
        if (!IsActive) return;
        _memorySource?.RecordAllocation(address, size, allocator, callerAddress);
        _bus?.Publish(DiagnosticEvent.MemoryAlloc(address, size));
    }
    
    public static void NotifyMemoryFreed(ulong address)
    {
        if (!IsActive) return;
        _memorySource?.RecordFree(address);
        _bus?.Publish(DiagnosticEvent.MemoryFree(address));
    }
    
    public static void NotifyMemoryAccess(ulong address, ulong size, int accessType, ulong rip)
    {
        if (!IsActive) return;
        _memorySource?.RecordAccess(address, size, accessType, rip);
    }
    
    public static void NotifyThreadStateChange(int threadId, string newState, string? reason = null)
    {
        if (!IsActive) return;
        _threadSource?.RecordStateChange(threadId, newState, reason);
        _bus?.Publish(DiagnosticEvent.ThreadState(threadId, newState, reason));
    }
    
    public static void NotifyMutexAcquire(int threadId, ulong mutexAddress)
    {
        if (!IsActive) return;
        _threadSource?.RecordMutexAcquire(threadId, mutexAddress);
    }
    
    public static void NotifyMutexRelease(int threadId, ulong mutexAddress)
    {
        if (!IsActive) return;
        _threadSource?.RecordMutexRelease(threadId, mutexAddress);
    }
    
    public static void NotifySyscall(
        string library,
        string name,
        string nid,
        long returnValue,
        long durationMicros = 0,
        int threadId = 0,
        ulong[]? args = null)
    {
        if (!IsActive) return;
        _syscallSource?.RecordCall(library, name, nid, returnValue, durationMicros, threadId, args);
    }
    
    public static void NotifyFileOpen(string path, string mode, bool success)
    {
        if (!IsActive) return;
        _fileIoSource?.RecordOpen(path, mode, success);
        // Publish to bus so engine's FileIoTracer receives it (reusing Error type with Source="FileIO").
        _bus?.Publish(new DiagnosticEvent(
            DiagnosticEventType.Error,
            DiagStopwatch.GetElapsedTimeMs(),
            "FileIO:Open",
            path,
            success ? 1UL : 0UL,
            0,
            0));
    }
    
    public static void NotifyFileRead(string path, ulong offset, ulong size, double durationMs)
    {
        if (!IsActive) return;
        _fileIoSource?.RecordRead(path, offset, size, durationMs);
        _bus?.Publish(new DiagnosticEvent(
            DiagnosticEventType.Error,
            DiagStopwatch.GetElapsedTimeMs(),
            "FileIO:Read",
            path,
            offset,
            size,
            (int)durationMs));
    }
    
    public static void NotifyFileWrite(string path, ulong offset, ulong size, double durationMs)
    {
        if (!IsActive) return;
        _fileIoSource?.RecordWrite(path, offset, size, durationMs);
        _bus?.Publish(new DiagnosticEvent(
            DiagnosticEventType.Error,
            DiagStopwatch.GetElapsedTimeMs(),
            "FileIO:Write",
            path,
            offset,
            size,
            (int)durationMs));
    }
    
    public static void NotifyFileStat(string path, bool success)
    {
        if (!IsActive) return;
        _fileIoSource?.RecordStat(path, success);
        _bus?.Publish(new DiagnosticEvent(
            DiagnosticEventType.Error,
            DiagStopwatch.GetElapsedTimeMs(),
            "FileIO:Stat",
            path,
            success ? 1UL : 0UL,
            0,
            0));
    }
    
    public static void NotifyBootStage(string stageName, string details = "")
    {
        if (!IsActive) return;
        _bootStageSource?.RecordBootStage(stageName, details);
        _bus?.Publish(DiagnosticEvent.BootStage(stageName, details));
    }
    
    public static void NotifyCrash(string signalType, ulong faultAddress, ulong rip, in RegisterSnapshot registers)
    {
        // Crash notifications ALWAYS go through, even if IsActive is false
        _crashSource?.QueueCrash(signalType, faultAddress, rip, in registers);
        // Publish crash event with faultAddress in Address field and rip in Value field
        // (so the engine can extract both).
        _bus?.Publish(new DiagnosticEvent(
            DiagnosticEventType.Crash,
            DiagStopwatch.GetElapsedTimeMs(),
            signalType,
            $"at 0x{faultAddress:X16} RIP=0x{rip:X16}",
            faultAddress,
            rip,
            0));
    }
    
    public static void PublishImport(string importName, string? library, ulong returnAddress, ulong returnValue)
    {
        if (!IsActive) return;
        _bus?.Publish(DiagnosticEvent.Import(importName, library, returnAddress) with { Value = returnValue });
    }
    
    public static void Flush()
    {
        _bus?.Flush();
    }
}
