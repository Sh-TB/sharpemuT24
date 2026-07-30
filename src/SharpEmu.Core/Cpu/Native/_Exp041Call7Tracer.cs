// EXP-041: Trace call #7 target and hash table state.
//
// Add INT3 at call #7 (0x804F04C5C) to:
// 1. Log the actual function being called ([rax])
// 2. Log hash table state
// 3. Log global 0x801E51240 state
//
// Also remove the EXP-040 workaround to get the original crash behavior.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    private const ulong Exp041_Call7Addr = 0x804F04C5C;
    private byte _exp041Call7OriginalByte;
    private bool _exp041Call7Patched;

    private unsafe void Exp041PatchCall7()
    {
        if (_exp041Call7Patched) return;
        try
        {
            var ptr = (byte*)Exp041_Call7Addr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp041_Call7Addr, 16u, 64u, &flNewProtect))
            {
                _exp041Call7OriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp041Call7Patched = true;
                Console.Error.WriteLine(
                    $"[EXP041-PATCH] call#7 at 0x{Exp041_Call7Addr:X16} patched with INT3");
                VirtualProtect((void*)Exp041_Call7Addr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp041_Call7Addr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP041] Failed to patch call#7: {ex.Message}");
        }
    }

    private unsafe bool Exp041TryHandleCall7Int3(void* contextRecord, ulong rip)
    {
        if (!_exp041Call7Patched) return false;
        if (rip - 1 != Exp041_Call7Addr) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rax = ReadCtxU64(contextRecord, 120);  // CTX_RAX
        ulong rsp = ReadCtxU64(contextRecord, 152);

        // rax = address of global (0x808958220)
        // [rax] = function pointer to call
        ulong funcPtr = 0;
        try { funcPtr = *(ulong*)rax; } catch { }

        ulong rdi = ReadCtxU64(contextRecord, 176); // CTX_RDI
        ulong rsi = ReadCtxU64(contextRecord, 168); // CTX_RSI
        Console.Error.WriteLine(
            $"[EXP041-CALL7] rax=0x{rax:X16} [rax]=0x{funcPtr:X16} tid={tid} rdi=0x{rdi:X16} rsi=0x{rsi:X16}");

        // EXP-046: Check [rdi+0x10] — the condition checked by 0x804D9C500
        if (rdi != 0 && rdi > 0x1000)
        {
            try
            {
                uint rdi_10 = *(uint*)(rdi + 0x10);
                Console.Error.WriteLine(
                    $"  [rdi+0x10]=0x{rdi_10:X8} (if 1 or 0xFFFFFFFD: continues, else: returns)");
            }
            catch { }
        }

        // Log hash table and global state
        try
        {
            ulong hashTablePtr = *(ulong*)0x801EF7610;
            ulong globalPtr = *(ulong*)0x801E51240;
            Console.Error.WriteLine(
                $"[EXP041-CALL7-STATE] hash_table=0x{hashTablePtr:X16} global=0x{globalPtr:X16}");

            // Check hash table entries
            if (hashTablePtr != 0)
            {
                ulong entriesPtr = *(ulong*)hashTablePtr;
                if (entriesPtr != 0)
                {
                    int populated = 0;
                    for (int i = 0; i < 100; i++)
                    {
                        ulong entry = *(ulong*)(entriesPtr + (ulong)i * 8);
                        if (entry != 0xFFFFFFFF && entry != 0)
                            populated++;
                    }
                    Console.Error.WriteLine(
                        $"[EXP041-CALL7-ENTRIES] populated={populated}/100");
                }
            }
        }
        catch { }

        // Also check: what segment is funcPtr in?
        if (funcPtr >= 0x804CD5000 && funcPtr < 0x804CD5000 + 0x2B9722A)
            Console.Error.WriteLine($"  funcPtr in PRX CODE segment");
        else if (funcPtr >= 0x804CD5000 + 0x3C50000 && funcPtr < 0x804CD5000 + 0x4094778)
            Console.Error.WriteLine($"  funcPtr in PRX DATA segment (RW)");
        else if (funcPtr >= 0x800000000 && funcPtr < 0x802000000)
            Console.Error.WriteLine($"  funcPtr in EBOOT code segment");
        else
            Console.Error.WriteLine($"  funcPtr in UNKNOWN region");

        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp041_Call7Addr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp041_Call7Addr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp041Call7OriginalByte;
            VirtualProtect((void*)Exp041_Call7Addr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp041_Call7Addr, 16u);
        }
        _exp041Call7Patched = false;

        WriteCtxU64(contextRecord, 248, Exp041_Call7Addr);
        return true;
    }
}
