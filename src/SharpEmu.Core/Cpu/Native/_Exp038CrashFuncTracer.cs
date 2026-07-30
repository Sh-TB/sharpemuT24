// EXP-038: Trace how the crash function 0x80135DDD0 is called.
//
// The crash function has zero static callers. It must be called via
// an indirect call (function pointer). Add INT3 at its entry to
// capture the caller at runtime.
//
// Also trace il2cpp_init's internal calls to find the registration path.

using System;
using System.Collections.Generic;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-038: Crash function caller tracing =====

    private const ulong Exp038_CrashFuncAddr = 0x80135DDD0;
    private byte _exp038CrashFuncOriginalByte;
    private bool _exp038CrashFuncPatched;
    private int _exp038CrashFuncCallCount;

    // Also trace the real init function 0x804f04ba0 (called by il2cpp_init)
    private const ulong Exp038_RealInitAddr = 0x804F04BA0;
    private byte _exp038RealInitOriginalByte;
    private bool _exp038RealInitPatched;
    private int _exp038RealInitCallCount;

    private static readonly bool _exp038TraceEnabled =
        Environment.GetEnvironmentVariable("SHARPEMU_EXP038_TRACE") == "1";

    /// <summary>
    /// Installs INT3 at the crash function and real init function.
    /// Called after modules are loaded.
    /// </summary>
    private unsafe void Exp038InstallTracers()
    {
        // Patch crash function
        if (!_exp038CrashFuncPatched)
        {
            try
            {
                var ptr = (byte*)Exp038_CrashFuncAddr;
                uint flNewProtect = 0;
                if (VirtualProtect((void*)Exp038_CrashFuncAddr, 16u, 64u, &flNewProtect))
                {
                    _exp038CrashFuncOriginalByte = ptr[0];
                    ptr[0] = 0xCC; // INT3
                    _exp038CrashFuncPatched = true;
                    Console.Error.WriteLine(
                        $"[EXP038-PATCH] crash_func at 0x{Exp038_CrashFuncAddr:X16} patched with INT3 " +
                        $"(original byte=0x{_exp038CrashFuncOriginalByte:X2})");
                    VirtualProtect((void*)Exp038_CrashFuncAddr, 16u, flNewProtect, &flNewProtect);
                    FlushInstructionCache(GetCurrentProcess(), (void*)Exp038_CrashFuncAddr, 16u);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[EXP038] Failed to patch crash_func: {ex.Message}");
            }
        }

        // Read and log current global values
        try
        {
            ulong hashTablePtr = *(ulong*)0x801EF7610;
            ulong globalPtr = *(ulong*)0x801E51240;
            Console.Error.WriteLine(
                $"[EXP038-STATE] hash_table_ptr at 0x801EF7610 = 0x{hashTablePtr:X16} " +
                $"global_ptr at 0x801E51240 = 0x{globalPtr:X16}");
        }
        catch { }
    }

    /// <summary>
    /// Tries to handle INT3 traps from the crash function.
    /// </summary>
    private unsafe bool Exp038TryHandleCrashFuncInt3(void* contextRecord, ulong rip)
    {
        // Check crash function
        if (_exp038CrashFuncPatched && rip - 1 == Exp038_CrashFuncAddr)
        {
            int tid = Environment.CurrentManagedThreadId;
            ulong rsp = ReadCtxU64(contextRecord, 152);
            ulong callerRip = 0;
            try { callerRip = *(ulong*)rsp; } catch { }

            // Read RDI (first argument)
            ulong rdi = ReadCtxU64(contextRecord, 176);

            int callNum = Interlocked.Increment(ref _exp038CrashFuncCallCount);

            // Read global values at this point
            ulong hashTablePtr = 0, globalPtr = 0;
            try { hashTablePtr = *(ulong*)0x801EF7610; } catch { }
            try { globalPtr = *(ulong*)0x801E51240; } catch { }

            Console.Error.WriteLine(
                $"[EXP038-CRASH_FUNC-ENTER] #{callNum} caller=0x{callerRip:X16} " +
                $"tid={tid} rdi=0x{rdi:X16} rsp=0x{rsp:X16}");
            Console.Error.WriteLine(
                $"[EXP038-CRASH_FUNC-STATE] hash_table=0x{hashTablePtr:X16} " +
                $"global=0x{globalPtr:X16}");

            // EXP-039: Dump hash table structure
            if (hashTablePtr != 0 && hashTablePtr > 0x1000)
            {
                try
                {
                    Console.Error.WriteLine($"[EXP039-HASH_TABLE] Dump at 0x{hashTablePtr:X16}:");
                    for (int off = 0; off < 0x40; off += 8)
                    {
                        ulong val = *(ulong*)(hashTablePtr + (ulong)off);
                        Console.Error.WriteLine($"  +0x{off:X2}: 0x{val:X16}");
                    }

                    // Dump first 16 entries from the entries array
                    ulong entriesPtr = *(ulong*)(hashTablePtr);
                    ulong mask = *(ulong*)(hashTablePtr + 8);
                    Console.Error.WriteLine($"[EXP039-HASH_ENTRIES] entries=0x{entriesPtr:X16} mask=0x{mask:X16}");
                    if (entriesPtr != 0 && entriesPtr > 0x1000)
                    {
                        for (int e = 0; e < 16; e++)
                        {
                            try
                            {
                                ulong entryVal = *(ulong*)(entriesPtr + (ulong)e * 8);
                                if (entryVal != 0)
                                {
                                    Console.Error.WriteLine($"  entry[{e}] = 0x{entryVal:X16}");
                                }
                            }
                            catch { }
                        }
                    }
                }
                catch { }
            }

            // Dump stack to find call chain
            Console.Error.WriteLine("[EXP038-CRASH_FUNC-STACK] Return addresses on stack:");
            try
            {
                byte* sp = (byte*)rsp;
                for (int i = 0; i < 16; i++)
                {
                    ulong val = *(ulong*)(sp + i * 8);
                    if (val >= 0x800000000 && val < 0x810000000)
                    {
                        Console.Error.WriteLine($"  [rsp+0x{i*8:X2}] = 0x{val:X16} (code)");
                    }
                }
            }
            catch { }
            Console.Error.Flush();

            // Restore original byte and let the function execute
            var ptr = (byte*)Exp038_CrashFuncAddr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp038_CrashFuncAddr, 16u, 64u, &flNewProtect))
            {
                ptr[0] = _exp038CrashFuncOriginalByte;
                VirtualProtect((void*)Exp038_CrashFuncAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp038_CrashFuncAddr, 16u);
            }
            _exp038CrashFuncPatched = false;

            // Set RIP to re-execute the restored instruction
            WriteCtxU64(contextRecord, 248, Exp038_CrashFuncAddr);
            return true;
        }

        return false;
    }
}
