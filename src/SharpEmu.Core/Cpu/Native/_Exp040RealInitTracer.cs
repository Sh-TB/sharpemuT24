// EXP-040: Trace il2cpp_init internal call sequence.
//
// Add INT3 at the real init function (0x804F04BA0) and trace its internal
// calls to understand the execution order.
//
// Also add a write-watchpoint on the hash table entries array.
// The entries are at 0x60053E990 (runtime address, may change between runs).
// We'll read the entries pointer from the hash table at runtime.

using System;
using System.Collections.Generic;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-040: il2cpp_init internal tracing =====

    // Real init function called by il2cpp_init
    private const ulong Exp040_RealInitAddr = 0x804F04BA0;
    private byte _exp040RealInitOriginalByte;
    private bool _exp040RealInitPatched;

    // Hash table entries write watchpoint
    // We'll set this at runtime after the hash table is allocated
    private ulong _exp040HashEntriesAddr;
    private ulong _exp040HashEntriesEnd;
    private bool _exp040HashEntriesWatchpointSet;

    // Track calls inside il2cpp_init
    private int _exp040CallCount;

    /// <summary>
    /// Patches the real init function with INT3.
    /// </summary>
    private unsafe void Exp040PatchRealInit()
    {
        if (_exp040RealInitPatched) return;
        try
        {
            var ptr = (byte*)Exp040_RealInitAddr;
            uint flNP042 = 0;
            if (VirtualProtect((void*)Exp040_RealInitAddr, 16u, 64u, &flNP042))
            {
                _exp040RealInitOriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp040RealInitPatched = true;
                Console.Error.WriteLine(
                    $"[EXP040-PATCH] real_init at 0x{Exp040_RealInitAddr:X16} patched with INT3");
                VirtualProtect((void*)Exp040_RealInitAddr, 16u, flNP042, &flNP042);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp040_RealInitAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP040] Failed to patch real_init: {ex.Message}");
        }
    }

    /// <summary>
    /// Handles INT3 from real_init. Logs entry, then sets up hash entries watchpoint.
    /// </summary>
    private unsafe bool Exp040TryHandleRealInitInt3(void* contextRecord, ulong rip)
    {
        if (!_exp040RealInitPatched) return false;
        if (rip - 1 != Exp040_RealInitAddr) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        Console.Error.WriteLine(
            $"[EXP040-REAL_INIT-ENTER] caller=0x{callerRip:X16} tid={tid}");

        // Read and log hash table state
        try
        {
            ulong hashTablePtr = *(ulong*)0x801EF7610;
            Console.Error.WriteLine(
                $"[EXP040-STATE] hash_table=0x{hashTablePtr:X16} global=0x{*(ulong*)0x801E51240:X16}");

            if (hashTablePtr != 0)
            {
                ulong entriesPtr = *(ulong*)hashTablePtr;
                ulong mask = *(ulong*)(hashTablePtr + 8);
                Console.Error.WriteLine(
                    $"[EXP040-STATE] entries=0x{entriesPtr:X16} mask=0x{mask:X16}");

                // Dump first 8 entries
                if (entriesPtr != 0)
                {
                    for (int i = 0; i < 8; i++)
                    {
                        ulong entry = *(ulong*)(entriesPtr + (ulong)i * 8);
                        Console.Error.WriteLine(
                            $"[EXP040-STATE] entry[{i}] = 0x{entry:X16}");
                    }
                }
            }
        }
        catch { }
        Console.Error.Flush();

        // EXP-050 FIX: NOP the conditional jump at 0x8013EE0CE that skips the hash lookup.
        // The jump is: jle 0x8013EF25E (6 bytes: 0F 8E EA 01 00 00)
        // NOP it (6 bytes: 90 90 90 90 90 90) so the hash lookup ALWAYS runs.
        // This ensures metadata fields are set before they're read.
        // ALSO: keep the callback stub from EXP-048 to prevent the callback crash.
        try
        {
            // Keep callback stub
            var cbPtr = (byte*)0x80134FA00;
            uint flNP048 = 0;
            if (VirtualProtect((void*)0x80134FA00, 8u, 64u, &flNP048))
            {
                if (cbPtr[0] == 0x55)
                {
                    cbPtr[0] = 0xB0; cbPtr[1] = 0x01; cbPtr[2] = 0xC3; cbPtr[3] = 0x90;
                    VirtualProtect((void*)0x80134FA00, 8u, flNP048, &flNP048);
                    FlushInstructionCache(GetCurrentProcess(), (void*)0x80134FA00, 8u);
                    Console.Error.WriteLine("[EXP050-FIX] Callback stub applied");
                }
            }

            // NOP the jump at 0x8013EE0CE
            var jmpPtr = (byte*)0x8013EE0CE;
            uint flNP050 = 0;
            if (VirtualProtect((void*)0x8013EE0CE, 8u, 64u, &flNP050))
            {
                // Verify it's a Jcc (0F 8E)
                if (jmpPtr[0] == 0x0F && jmpPtr[1] == 0x8E)
                {
                    jmpPtr[0] = 0x90; jmpPtr[1] = 0x90; jmpPtr[2] = 0x90;
                    jmpPtr[3] = 0x90; jmpPtr[4] = 0x90; jmpPtr[5] = 0x90;
                    VirtualProtect((void*)0x8013EE0CE, 8u, flNP050, &flNP050);
                    FlushInstructionCache(GetCurrentProcess(), (void*)0x8013EE0CE, 8u);
                    Console.Error.WriteLine("[EXP050-FIX] NOPped jump at 0x8013EE0CE (force hash lookup)");
                }
                else
                {
                    Console.Error.WriteLine(
                        $"[EXP050-FIX] WARNING: expected 0F 8E at 0x8013EE0CE, got 0x{jmpPtr[0]:X2} 0x{jmpPtr[1]:X2}");
                }
            }
        }
        catch { }

        // EXP-050 FIX: Stub 0x800C195C0 (metadata accessor) to return immediately.
        // This function is called from the init function after il2cpp_init returns.
        // It reads NULL metadata fields → SIGSEGV cascade.
        // Stubbing it prevents the cascade. The init function continues.
        try
        {
            var metaPtr = (byte*)0x800C195C0;
            uint flNP050b = 0;
            if (VirtualProtect((void*)0x800C195C0, 8u, 64u, &flNP050b))
            {
                if (metaPtr[0] == 0x55) // push rbp
                {
                    metaPtr[0] = 0xC3; // ret
                    VirtualProtect((void*)0x800C195C0, 8u, flNP050b, &flNP050b);
                    FlushInstructionCache(GetCurrentProcess(), (void*)0x800C195C0, 8u);
                    Console.Error.WriteLine("[EXP050-FIX] Stubbed 0x800C195C0 (ret)");
                }
            }
        }
        catch { }

        // EXP-044: Dump PRX fini_array entries to verify relocations applied
        Exp044DumpFiniArray();

        // Restore and let it execute
        var ptr = (byte*)Exp040_RealInitAddr;
        uint flNP042 = 0;
        if (VirtualProtect((void*)Exp040_RealInitAddr, 16u, 64u, &flNP042))
        {
            ptr[0] = _exp040RealInitOriginalByte;
            VirtualProtect((void*)Exp040_RealInitAddr, 16u, flNP042, &flNP042);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp040_RealInitAddr, 16u);
        }
        _exp040RealInitPatched = false;

        WriteCtxU64(contextRecord, 248, Exp040_RealInitAddr);
        return true;
    }

    /// <summary>
    /// Checks if the hash table entries have been populated.
    /// Called from the crash function INT3 handler.
    /// </summary>
    public void Exp040CheckHashEntries(string context)
    {
        try
        {
            ulong hashTablePtr = *(ulong*)0x801EF7610;
            if (hashTablePtr == 0) return;

            ulong entriesPtr = *(ulong*)hashTablePtr;
            if (entriesPtr == 0) return;

            // Count non-sentinel entries
            int populated = 0;
            int total = 0;
            for (int i = 0; i < 100; i++)
            {
                ulong entry = *(ulong*)(entriesPtr + (ulong)i * 8);
                if (entry != 0xFFFFFFFF && entry != 0)
                {
                    populated++;
                }
                total++;
            }

            Console.Error.WriteLine(
                $"[EXP040-ENTRIES] {context}: hash_table=0x{hashTablePtr:X16} " +
                $"entries=0x{entriesPtr:X16} populated={populated}/{total} " +
                $"global=0x{*(ulong*)0x801E51240:X16}");
            Console.Error.Flush();
        }
        catch { }
    }
}
