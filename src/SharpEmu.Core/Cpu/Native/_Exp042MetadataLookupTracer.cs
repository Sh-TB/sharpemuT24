// EXP-042: Trace the metadata lookup function 0x800C66B40.
//
// Key branch at 0x800C66B4F:
//   cmp byte [rdx + 0x19], 0  ; check initialized flag
//   je 0x800C66B58            ; if NOT initialized, continue (return object)
//   xor eax, eax              ; if initialized, return 0
//   ret
//
// If the flag is set (initialized), it returns 0 → crash.
// If the flag is NOT set, it returns a real object → works.
//
// On SharpEmu, the crash happens because [rax] at 0x80134FA7D is called
// with rax=0 (returned by 0x800C66B40). This means the "initialized" flag
// IS set, causing the early return 0.
//
// But on a real PS5, the flag should NOT be set yet (metadata not loaded).
// So 0x800C66B40 should continue to the search path and return a real object.
//
// OR: on a real PS5, 0x800C66B40 returns 0, and the caller handles rax=0
// gracefully (doesn't call [rax]).
//
// Let me trace the actual values.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    private const ulong Exp042_MetadataLookupAddr = 0x800C66B40;
    private byte _exp042MetadataLookupOriginalByte;
    private bool _exp042MetadataLookupPatched;

    private unsafe void Exp042PatchMetadataLookup()
    {
        if (_exp042MetadataLookupPatched) return;
        try
        {
            var ptr = (byte*)Exp042_MetadataLookupAddr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp042_MetadataLookupAddr, 16u, 64u, &flNewProtect))
            {
                _exp042MetadataLookupOriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp042MetadataLookupPatched = true;
                Console.Error.WriteLine(
                    $"[EXP042-PATCH] metadata_lookup at 0x{Exp042_MetadataLookupAddr:X16} patched");
                VirtualProtect((void*)Exp042_MetadataLookupAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp042_MetadataLookupAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP042] Failed to patch metadata_lookup: {ex.Message}");
        }
    }

    private unsafe bool Exp042TryHandleMetadataLookupInt3(void* contextRecord, ulong rip)
    {
        if (!_exp042MetadataLookupPatched) return false;
        if (rip - 1 != Exp042_MetadataLookupAddr) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        // 0x800C66B40 reads [0x801EA4E80] -> [rax+8] -> [rcx+8] -> rdx
        // Then checks [rdx + 0x19]
        try
        {
            ulong lazyInitPtr = *(ulong*)0x801EA4E80;
            Console.Error.WriteLine(
                $"[EXP042-META_LOOKUP] caller=0x{callerRip:X16} tid={tid}");
            Console.Error.WriteLine(
                $"  [0x801EA4E80] = 0x{lazyInitPtr:X16}");

            if (lazyInitPtr != 0)
            {
                ulong rcx = *(ulong*)(lazyInitPtr + 8);
                Console.Error.WriteLine(
                    $"  [lazyInit+0x08] = 0x{rcx:X16}");

                if (rcx != 0)
                {
                    ulong rdx = *(ulong*)(rcx + 8);
                    Console.Error.WriteLine(
                        $"  [rcx+0x08] = 0x{rdx:X16}");

                    if (rdx != 0)
                    {
                        byte flag = *((byte*)(rdx + 0x19));
                        Console.Error.WriteLine(
                            $"  [rdx+0x19] = 0x{flag:X2} (initialized flag)");
                        Console.Error.WriteLine(
                            $"  If flag=0: search path (returns object)");
                        Console.Error.WriteLine(
                            $"  If flag!=0: return 0 (causes crash)");
                    }
                }
            }
        }
        catch { }
        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp042_MetadataLookupAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp042_MetadataLookupAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp042MetadataLookupOriginalByte;
            VirtualProtect((void*)Exp042_MetadataLookupAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp042_MetadataLookupAddr, 16u);
        }
        _exp042MetadataLookupPatched = false;

        WriteCtxU64(contextRecord, 248, Exp042_MetadataLookupAddr);
        return true;
    }
}
