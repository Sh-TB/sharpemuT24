// EXP-041: Trace hash table state before the hash lookup in the init function.
//
// The init function (0x8013EB6B0) calls the hash function at 0x8013EEFE0.
// We need to check the hash table state at that point.
//
// Also check: what string is being hashed? The hash function takes
// a string buffer at [rsp+0x2240] with length 0xb (11 bytes).

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    private const ulong Exp041_HashCallAddr = 0x8013EEFE0;
    private byte _exp041HashCallOriginalByte;
    private bool _exp041HashCallPatched;

    private unsafe void Exp041PatchHashCall()
    {
        if (_exp041HashCallPatched) return;
        try
        {
            var ptr = (byte*)Exp041_HashCallAddr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp041_HashCallAddr, 16u, 64u, &flNewProtect))
            {
                _exp041HashCallOriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp041HashCallPatched = true;
                Console.Error.WriteLine(
                    $"[EXP041-PATCH] hash_call at 0x{Exp041_HashCallAddr:X16} patched");
                VirtualProtect((void*)Exp041_HashCallAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp041_HashCallAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP041] Failed to patch hash_call: {ex.Message}");
        }
    }

    private unsafe bool Exp041TryHandleHashCallInt3(void* contextRecord, ulong rip)
    {
        if (!_exp041HashCallPatched) return false;
        if (rip - 1 != Exp041_HashCallAddr) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);

        // The string buffer is at [rsp+0x2240] with length 0xb (11 bytes)
        // But rsp might have changed. Let me read the setup from the stack.
        // From the disassembly:
        // 0x8013EEFCB: mov edx, 0xb  (length)
        // 0x8013EEFD0: mov [rsp+0x2240], rcx  (string part 1)
        // 0x8013EEFD8: mov [rsp+0x2248], rax  (string part 2)
        // 0x8013EEFE0: call 0x800ce3aa0  (hash function)
        
        // Read the string from [rsp+0x2240]
        string strVal = "";
        try
        {
            byte* strPtr = (byte*)(rsp + 0x2240);
            byte[] strBytes = new byte[16];
            for (int i = 0; i < 16; i++)
                strBytes[i] = strPtr[i];
            strVal = System.Text.Encoding.ASCII.GetString(strBytes);
        }
        catch { }

        // Log hash table state
        try
        {
            ulong hashTablePtr = *(ulong*)0x801EF7610;
            ulong globalPtr = *(ulong*)0x801E51240;
            
            int populated = 0;
            if (hashTablePtr != 0)
            {
                ulong entriesPtr = *(ulong*)hashTablePtr;
                if (entriesPtr != 0)
                {
                    for (int i = 0; i < 100; i++)
                    {
                        ulong entry = *(ulong*)(entriesPtr + (ulong)i * 8);
                        if (entry != 0xFFFFFFFF && entry != 0)
                            populated++;
                    }
                }
            }

            Console.Error.WriteLine(
                $"[EXP041-HASH_CALL] string='{strVal}' tid={tid}");
            Console.Error.WriteLine(
                $"[EXP041-HASH_CALL-STATE] hash_table=0x{hashTablePtr:X16} " +
                $"global=0x{globalPtr:X16} populated={populated}/100");
        }
        catch { }
        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp041_HashCallAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp041_HashCallAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp041HashCallOriginalByte;
            VirtualProtect((void*)Exp041_HashCallAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp041_HashCallAddr, 16u);
        }
        _exp041HashCallPatched = false;

        WriteCtxU64(contextRecord, 248, Exp041_HashCallAddr);
        return true;
    }
}
