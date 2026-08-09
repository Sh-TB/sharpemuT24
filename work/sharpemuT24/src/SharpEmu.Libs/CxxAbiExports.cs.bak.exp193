// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System;
using System.Collections.Concurrent;
using System.Threading;
using SharpEmu.HLE;

namespace SharpEmu.Libs.CxxAbi;

public static class CxaGuardExports
{
    private const ulong GuardCompleteValue = 0x0000_0000_0000_0001;
    private const ulong GuardPendingValue = 0x0000_0000_0000_0100;
    private const ulong GuardStateMask = 0x0000_0000_0000_FFFF;

    private sealed class GuardState
    {
        public int OwnerThreadId { get; set; }
        public int RecursionDepth { get; set; }
    }

    private static readonly ConcurrentDictionary<ulong, GuardState> _inProgress = new();

    [SysAbiExport(
        Nid = "3GPpjQdAMTw",
        ExportName = "__cxa_guard_acquire",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int CxaGuardAcquire(CpuContext ctx)
    {
        var guardPtr = ctx[CpuRegister.Rdi];
        if (guardPtr == 0)
        {
            ctx[CpuRegister.Rax] = 0;
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_INVALID_ARGUMENT;
        }

        var currentThreadId = Environment.CurrentManagedThreadId;
        var spinner = new SpinWait();
        while (true)
        {
            if (!TryReadGuardState(ctx, guardPtr, out _, out var initialized, out var inProgress))
            {
                ctx[CpuRegister.Rax] = 0;
                return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_MEMORY_FAULT;
            }

            LogGuardState(ctx, "guard_acquire", guardPtr, initialized, inProgress);

            if (initialized)
            {
                ctx[CpuRegister.Rax] = 0;
                LogGuardResult("guard_acquire", guardPtr, result: 0, initialized, inProgress: false, ownerThreadId: 0);
                return (int)OrbisGen2Result.ORBIS_GEN2_OK;
            }

            var newState = new GuardState
            {
                OwnerThreadId = currentThreadId,
                RecursionDepth = 1,
            };
            if (_inProgress.TryAdd(guardPtr, newState))
            {
                if (!TryWriteGuardState(ctx, guardPtr, GuardPendingValue))
                {
                    _inProgress.TryRemove(guardPtr, out _);
                    ctx[CpuRegister.Rax] = 0;
                    return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_MEMORY_FAULT;
                }

                ctx[CpuRegister.Rax] = 1;
                LogGuardResult("guard_acquire", guardPtr, result: 1, initialized, inProgress: true, ownerThreadId: currentThreadId);
                return (int)OrbisGen2Result.ORBIS_GEN2_OK;
            }

            if (_inProgress.TryGetValue(guardPtr, out var state))
            {
                if (state.OwnerThreadId == currentThreadId)
                {
                    ctx[CpuRegister.Rax] = 0;
                    LogGuardResult("guard_acquire", guardPtr, result: 0, initialized, inProgress: true, ownerThreadId: state.OwnerThreadId);
                    return (int)OrbisGen2Result.ORBIS_GEN2_OK;
                }
            }

            spinner.SpinOnce();
            if (spinner.Count % 32 == 0)
            {
                Thread.Yield();
            }
        }
    }

    [SysAbiExport(
        Nid = "9rAeANT2tyE",
        ExportName = "__cxa_guard_release",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int CxaGuardRelease(CpuContext ctx)
    {
        var guardPtr = ctx[CpuRegister.Rdi];
        if (guardPtr == 0)
        {
            ctx[CpuRegister.Rax] = 0;
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_INVALID_ARGUMENT;
        }

        if (_inProgress.TryGetValue(guardPtr, out var state) &&
            state.OwnerThreadId != Environment.CurrentManagedThreadId)
        {
            ctx[CpuRegister.Rax] = 0;
            LogGuardResult("guard_release", guardPtr, result: 0, initialized: false, inProgress: true, ownerThreadId: state.OwnerThreadId);
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_INVALID_ARGUMENT;
        }

        if (state is not null)
        {
            lock (state)
            {
                if (state.RecursionDepth > 1)
                {
                    state.RecursionDepth--;
                    ctx[CpuRegister.Rax] = 0;
                    LogGuardResult("guard_release", guardPtr, result: 0, initialized: false, inProgress: true, ownerThreadId: state.OwnerThreadId);
                    return (int)OrbisGen2Result.ORBIS_GEN2_OK;
                }
            }
        }

        if (!TryWriteGuardState(ctx, guardPtr, GuardCompleteValue))
        {
            ctx[CpuRegister.Rax] = 0;
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_MEMORY_FAULT;
        }

        _inProgress.TryRemove(guardPtr, out _);
        LogGuardState(ctx, "guard_release", guardPtr, initialized: true, inProgress: false);

        ctx[CpuRegister.Rax] = 0;
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }

    [SysAbiExport(
        Nid = "2emaaluWzUw",
        ExportName = "__cxa_guard_abort",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int CxaGuardAbort(CpuContext ctx)
    {
        var guardPtr = ctx[CpuRegister.Rdi];
        if (guardPtr == 0)
        {
            ctx[CpuRegister.Rax] = 0;
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_INVALID_ARGUMENT;
        }

        if (_inProgress.TryGetValue(guardPtr, out var state) &&
            state.OwnerThreadId != Environment.CurrentManagedThreadId)
        {
            ctx[CpuRegister.Rax] = 0;
            LogGuardResult("guard_abort", guardPtr, result: 0, initialized: false, inProgress: true, ownerThreadId: state.OwnerThreadId);
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_INVALID_ARGUMENT;
        }

        _ = TryWriteGuardState(ctx, guardPtr, 0);
        _inProgress.TryRemove(guardPtr, out _);
        LogGuardState(ctx, "guard_abort", guardPtr, initialized: false, inProgress: false);

        ctx[CpuRegister.Rax] = 0;
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }

    // std::_Execute_once — called by Unity/IL2CPP for static initialization.
    // ABI: int _Execute_once(once_flag* flag, int(*callback)(void*, void*, void**), void* arg, void** state)
    // RDI=once_flag*, RSI=callback, RDX=arg, RCX=state
    // The callback must be called once. Other threads must block until it completes.
    [SysAbiExport(
        Nid = "DiGVep5yB5w",
        ExportName = "_ZSt13_Execute_onceRSt9once_flagPFiPvS1_PS1_ES1_",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int ExecuteOnce(CpuContext ctx)
    {
        var onceAddress = ctx[CpuRegister.Rdi];
        var callbackAddress = ctx[CpuRegister.Rsi];
        var argAddress = ctx[CpuRegister.Rdx];

        if (onceAddress == 0)
        {
            ctx[CpuRegister.Rax] = 0;
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_INVALID_ARGUMENT;
        }

        // Check if already complete (once_flag value == 2)
        if (ctx.TryReadInt32(onceAddress, out var onceValue) && onceValue == 2)
        {
            // Already initialized — return immediately
            ctx[CpuRegister.Rax] = 0;
            return (int)OrbisGen2Result.ORBIS_GEN2_OK;
        }

        // Log the Execute_once call for diagnostics
        Console.Error.WriteLine(
            $"[EXECUTE_ONCE] flag=0x{onceAddress:X16} callback=0x{callbackAddress:X16} " +
            $"arg=0x{argAddress:X16} current_value={onceValue} thread=0x{GuestThreadExecution.CurrentGuestThreadHandle:X16}");
        // G2/G3: Log caller's callee-saved registers before call_once
        Console.Error.WriteLine(
            $"[EXECUTE_ONCE-G2] BEFORE: RAX=0x{ctx[CpuRegister.Rax]:X16} RBX=0x{ctx[CpuRegister.Rbx]:X16} " +
            $"R12=0x{ctx[CpuRegister.R12]:X16} R13=0x{ctx[CpuRegister.R13]:X16} " +
            $"R14=0x{ctx[CpuRegister.R14]:X16} R15=0x{ctx[CpuRegister.R15]:X16} " +
            $"RBP=0x{ctx[CpuRegister.Rbp]:X16} RSP=0x{ctx[CpuRegister.Rsp]:X16}");

        // Try to call the guest callback via the scheduler
        var scheduler = GuestThreadExecution.Scheduler;
        // EXP-139.2: Re-enabled nested TryCallGuestFunction — now uses RunGuestEntryStub
        // (native worker thread) which avoids .NET 10 "Invalid Program" crash.
        if (scheduler is not null && callbackAddress != 0)
        {
            // Mark as in-progress
            _ = ctx.TryWriteInt32(onceAddress, 1);

            Console.Error.WriteLine($"[EXECUTE_ONCE] Calling guest callback at 0x{callbackAddress:X16}...");

            if (scheduler.TryCallGuestFunction(
                ctx,
                callbackAddress,
                onceAddress,    // arg0: once_flag pointer
                argAddress,     // arg1: user arg
                0,              // arg2: state (unused)
                0,              // stackAddress (0 = use current)
                0,              // stackSize
                "std::_Execute_once",
                out var returnValue,
                out var error))
            {
                Console.Error.WriteLine(
                    $"[EXECUTE_ONCE] callback returned {returnValue} error='{error}'");
                // G2/G3: Log caller's registers AFTER call_once callback
                Console.Error.WriteLine(
                    $"[EXECUTE_ONCE-G2] AFTER: RAX=0x{ctx[CpuRegister.Rax]:X16} RBX=0x{ctx[CpuRegister.Rbx]:X16} " +
                    $"R12=0x{ctx[CpuRegister.R12]:X16} R13=0x{ctx[CpuRegister.R13]:X16} " +
                    $"R14=0x{ctx[CpuRegister.R14]:X16} R15=0x{ctx[CpuRegister.R15]:X16} " +
                    $"RBP=0x{ctx[CpuRegister.Rbp]:X16} RSP=0x{ctx[CpuRegister.Rsp]:X16}");

                if (false) // Accept any return value — callback executed
                {
                    // Callback failed — reset flag
                    _ = ctx.TryWriteInt32(onceAddress, 0);
                    Console.Error.WriteLine($"[EXECUTE_ONCE] callback FAILED, resetting flag");
                    ctx[CpuRegister.Rax] = unchecked((ulong)(int)OrbisGen2Result.ORBIS_GEN2_ERROR_TRY_AGAIN);
                    return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_TRY_AGAIN;
                }

                // Success — mark as complete
                _ = ctx.TryWriteInt32(onceAddress, 2);
                Console.Error.WriteLine($"[EXECUTE_ONCE] callback SUCCESS, flag marked complete");
                ctx[CpuRegister.Rax] = 0;
                return (int)OrbisGen2Result.ORBIS_GEN2_OK;
            }
            else
            {
                Console.Error.WriteLine(
                    $"[EXECUTE_ONCE] scheduler.TryCallGuestFunction FAILED: {error}");
                Console.Error.WriteLine($"[EXECUTE_ONCE] Falling back to stub (mark complete without callback)");
            }
        }
        else
        {
            if (scheduler is null)
                Console.Error.WriteLine($"[EXECUTE_ONCE] No scheduler available — using stub");
            if (callbackAddress == 0)
                Console.Error.WriteLine($"[EXECUTE_ONCE] No callback address — using stub");
        }

        // Fallback: mark as complete without calling callback
        _ = ctx.TryWriteInt32(onceAddress, 2);
        ctx[CpuRegister.Rax] = 0;
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }

    // __cxa_decrement_exception_refcount — called by Unity exception handling
    [SysAbiExport(
        Nid = "MQFPAqQPt1s",
        ExportName = "__cxa_decrement_exception_refcount",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int CxaDecrementExceptionRefcount(CpuContext ctx) => ctx.SetReturn(0);

    private static bool TryReadGuardState(CpuContext ctx, ulong guardPtr, out ulong word, out bool initialized, out bool inProgress)
    {
        word = 0;
        initialized = false;
        inProgress = false;
        if (!ctx.TryReadUInt64(guardPtr, out word))
        {
            return false;
        }

        initialized = (word & GuardCompleteValue) != 0;
        inProgress = (word & 0x0000_0000_0000_FF00) != 0;
        return true;
    }

    private static bool TryWriteGuardState(CpuContext ctx, ulong guardPtr, ulong stateValue)
    {
        if (!ctx.TryReadUInt64(guardPtr, out var word))
        {
            return false;
        }

        var newWord = (word & ~GuardStateMask) | (stateValue & GuardStateMask);
        return ctx.TryWriteUInt64(guardPtr, newWord);
    }

    private static void LogGuardState(CpuContext ctx, string op, ulong guardPtr, bool initialized, bool inProgress)
    {
        if (!string.Equals(Environment.GetEnvironmentVariable("SHARPEMU_LOG_GUARDS"), "1", StringComparison.Ordinal))
        {
            return;
        }

        var readable = ctx.TryReadUInt64(guardPtr, out var word);
        Console.Error.WriteLine(
            $"[LOADER][TRACE] {op}: guard=0x{guardPtr:X16} init={initialized} in_progress={inProgress} word={(readable ? $"0x{word:X16}" : "<unreadable>")}");
    }

    private static void LogGuardResult(string op, ulong guardPtr, int result, bool initialized, bool inProgress, int ownerThreadId)
    {
        if (!string.Equals(Environment.GetEnvironmentVariable("SHARPEMU_LOG_GUARDS"), "1", StringComparison.Ordinal))
        {
            return;
        }

        Console.Error.WriteLine(
            $"[LOADER][TRACE] {op}: guard=0x{guardPtr:X16} result={result} init={initialized} in_progress={inProgress} owner_thread={ownerThreadId}");
    }
}
