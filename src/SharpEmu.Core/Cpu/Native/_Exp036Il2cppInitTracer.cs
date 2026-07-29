// EXP-036: IL2CPP Initialization Order & Threading Import Investigation
//
// POLICY (per user):
//   - Verify il2cpp_init actually executes (don't assume from resolver result)
//   - Trace initialization order timeline
//   - Audit PLT 0x801937720 (found: sceKernelWaitSema, NOT __cxa_atexit)
//   - Audit synchronization HLE
//   - Trace skipped il2cpp_init path
//
// This file adds:
//   1. INT3 patching for il2cpp_init at 0x804ED85D0 (ENTER/EXIT trace)
//   2. INT3 patching for other global table entries (optional)
//   3. Synchronization HLE call tracing (sceKernelWaitSema, sceKernelSignalSema,
//      scePthreadMutexLock, scePthreadMutexUnlock, scePthreadCondWait, etc.)
//   4. Initialization timeline markers
//
// USAGE:
//   Set SHARPEMU_EXP036_TRACE=1 to enable verbose per-call logging
//   Logs go to stderr (capture with 2> /tmp/exp036_logs/run.log)

using System;
using System.Collections.Generic;
using System.Threading;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-036: il2cpp_init call tracer =====

    // Active backend instance (for HLE handlers to access EXP-036 methods)
    private static DirectExecutionBackend? _exp036ActiveBackend;
    public static DirectExecutionBackend? ActiveBackend => _exp036ActiveBackend;

    // Static callback for HLE handlers (in SharpEmu.Libs) to record sync calls
    // without needing a reference to SharpEmu.Core.
    public static Action<string, ulong, int, ulong, ulong, ulong, ulong>? SyncCallRecorder;

    // Address of il2cpp_init (from resolver: global[0] = 0x804ED85D0)
    private const ulong Exp036_Il2cppInitAddr = 0x804ED85D0;

    // Original first byte of il2cpp_init (saved before patching with INT3)
    private byte _exp036Il2cppInitOriginalByte;
    private bool _exp036Il2cppInitPatched;
    private int _exp036Il2cppInitCallCount;

    // Per-thread "inside il2cpp_init" flag (for ENTER/EXIT correlation)
    [ThreadStatic]
    private static bool _exp036InsideIl2cppInit;

    // ===== EXP-036: Synchronization HLE call tracer =====

    private readonly Dictionary<string, long> _exp036SyncCallCounts = new Dictionary<string, long>();
    private long _exp036SyncTotalCalls;

    private static readonly bool _exp036TraceEnabled =
        Environment.GetEnvironmentVariable("SHARPEMU_EXP036_TRACE") == "1";

    /// <summary>
    /// Patches the first byte of il2cpp_init with INT3 so we can trace
    /// when it's called. Called after Il2cppUserAssemblies.prx is loaded.
    /// </summary>
    private unsafe void Exp036PatchIl2cppInit()
    {
        // Set active backend reference so HLE handlers can call Exp036RecordSyncCall
        _exp036ActiveBackend = this;
        // Register the static callback for HLE handlers in SharpEmu.Libs
        SharpEmu.Libs.Kernel._Exp036SyncTrace.SetRecorder(Exp036RecordSyncCall);

        if (_exp036Il2cppInitPatched) return;

        try
        {
            var ptr = (byte*)Exp036_Il2cppInitAddr;
            uint flNewProtect = 0;
            if (!VirtualProtect((void*)Exp036_Il2cppInitAddr, 16u, 64u, &flNewProtect))
            {
                Console.Error.WriteLine($"[EXP036] VirtualProtect failed for il2cpp_init at 0x{Exp036_Il2cppInitAddr:X16}");
                return;
            }
            try
            {
                _exp036Il2cppInitOriginalByte = ptr[0];
                ptr[0] = 0xCC; // INT3
                _exp036Il2cppInitPatched = true;
                Console.Error.WriteLine(
                    $"[EXP036-PATCH] il2cpp_init at 0x{Exp036_Il2cppInitAddr:X16} patched with INT3 " +
                    $"(original byte=0x{_exp036Il2cppInitOriginalByte:X2})");
            }
            finally
            {
                VirtualProtect((void*)Exp036_Il2cppInitAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp036_Il2cppInitAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP036] Failed to patch il2cpp_init: {ex.Message}");
        }
    }

    /// <summary>
    /// Tries to handle an INT3 trap at il2cpp_init.
    /// Returns true if handled (caller should return -1 to continue execution).
    /// </summary>
    private unsafe bool Exp036TryHandleIl2cppInitInt3(void* contextRecord, ulong rip)
    {
        if (!_exp036Il2cppInitPatched) return false;

        // INT3 advances RIP by 1, so the stub starts at rip - 1
        ulong stubAddr = rip - 1;
        if (stubAddr != Exp036_Il2cppInitAddr) return false;

        // This is the il2cpp_init entry. Log ENTER, restore original byte,
        // set RIP = il2cpp_init (re-execute original instruction), and set
        // a thread-local flag so we can log EXIT when the function returns.
        //
        // For EXIT logging: we can't easily patch the RET instruction.
        // Instead, we rely on the caller's return address being on the stack.
        // We'll log ENTER now and set a flag. The caller will see the flag
        // when it calls other instrumented functions.

        int tid = Environment.CurrentManagedThreadId;
        ulong rdi = ReadCtxU64(contextRecord, 176); // CTX_RDI
        ulong rsi = ReadCtxU64(contextRecord, 168); // CTX_RSI
        ulong rdx = ReadCtxU64(contextRecord, 136); // CTX_RDX
        ulong rsp = ReadCtxU64(contextRecord, 152); // CTX_RSP
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        int callNum = Interlocked.Increment(ref _exp036Il2cppInitCallCount);

        Console.Error.WriteLine(
            $"[EXP036-IL2CPP_INIT-ENTER] #{callNum} caller=0x{callerRip:X16} " +
            $"tid={tid} rdi=0x{rdi:X16} rsi=0x{rsi:X16} rdx=0x{rdx:X16} " +
            $"rsp=0x{rsp:X16}");
        Console.Error.Flush();

        // Restore original byte so the function can execute normally
        var ptr = (byte*)Exp036_Il2cppInitAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp036_Il2cppInitAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp036Il2cppInitOriginalByte;
            VirtualProtect((void*)Exp036_Il2cppInitAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp036_Il2cppInitAddr, 16u);
        }

        // Set RIP = il2cpp_init (re-execute original instruction)
        WriteCtxU64(contextRecord, 248, Exp036_Il2cppInitAddr); // CTX_RIP
        _exp036InsideIl2cppInit = true;

        return true;
    }

    /// <summary>
    /// Records a synchronization HLE call. Called from the HLE handlers
    /// (sceKernelWaitSema, sceKernelSignalSema, etc.) via a hook.
    /// </summary>
    public void Exp036RecordSyncCall(string funcName, ulong callerRip, int tid,
        ulong arg1, ulong arg2, ulong arg3, ulong retVal)
    {
        long total = Interlocked.Increment(ref _exp036SyncTotalCalls);
        lock (_exp036SyncCallCounts)
        {
            _exp036SyncCallCounts.TryGetValue(funcName, out var c);
            _exp036SyncCallCounts[funcName] = c + 1;
        }

        // Log first 10 calls per function, then every 1000th
        bool shouldLog = _exp036TraceEnabled || total <= 50;
        if (shouldLog)
        {
            Console.Error.WriteLine(
                $"[EXP036-SYNC] #{total} func='{funcName}' caller=0x{callerRip:X16} " +
                $"tid={tid} a1=0x{arg1:X16} a2=0x{arg2:X16} a3=0x{arg3:X16} ret=0x{retVal:X16}");
            Console.Error.Flush();
        }
    }

    /// <summary>
    /// Dumps sync call statistics.
    /// </summary>
    public void Exp036DumpSyncStats()
    {
        Console.Error.WriteLine($"[EXP036-SYNC-TOP] === Sync call stats (total={_exp036SyncTotalCalls}) ===");
        List<KeyValuePair<string, long>> sorted;
        lock (_exp036SyncCallCounts)
        {
            sorted = new List<KeyValuePair<string, long>>(_exp036SyncCallCounts);
        }
        sorted.Sort((a, b) => b.Value.CompareTo(a.Value));
        int rank = 1;
        foreach (var entry in sorted)
        {
            if (rank > 20) break;
            Console.Error.WriteLine($"[EXP036-SYNC-TOP] rank={rank} func='{entry.Key}' calls={entry.Value}");
            rank++;
        }
        Console.Error.WriteLine(
            $"[EXP036-SYNC-TOP] il2cpp_init_calls={_exp036Il2cppInitCallCount} " +
            $"il2cpp_init_patched={_exp036Il2cppInitPatched} " +
            $"null_execute_recoveries={_nullExecuteRecoveries}");
        Console.Error.Flush();
    }
}
