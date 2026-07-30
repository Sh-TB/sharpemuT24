// EXP-039: Trace hash lookup function at 0x8004BD620.
//
// The hash table IS populated but lookups return 0.
// Trace: input hash (edi), hash table pointer, return value (rax).

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    private const ulong Exp039_HashLookupAddr = 0x8004BD620;
    private byte _exp039HashLookupOriginalByte;
    private bool _exp039HashLookupPatched;
    private int _exp039HashLookupCallCount;

    private unsafe void Exp039PatchHashLookup()
    {
        if (_exp039HashLookupPatched) return;
        try
        {
            var ptr = (byte*)Exp039_HashLookupAddr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp039_HashLookupAddr, 16u, 64u, &flNewProtect))
            {
                _exp039HashLookupOriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp039HashLookupPatched = true;
                Console.Error.WriteLine(
                    $"[EXP039-PATCH] hash_lookup at 0x{Exp039_HashLookupAddr:X16} patched with INT3 " +
                    $"(original byte=0x{_exp039HashLookupOriginalByte:X2})");
                VirtualProtect((void*)Exp039_HashLookupAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp039_HashLookupAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP039] Failed to patch hash_lookup: {ex.Message}");
        }
    }

    private unsafe bool Exp039TryHandleHashLookupInt3(void* contextRecord, ulong rip)
    {
        if (!_exp039HashLookupPatched) return false;
        if (rip - 1 != Exp039_HashLookupAddr) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }
        ulong edi = ReadCtxU64(contextRecord, 176) & 0xFFFFFFFF;  // CTX_RDI (hash input)

        int callNum = Interlocked.Increment(ref _exp039HashLookupCallCount);

        // Read hash table pointer
        ulong hashTablePtr = 0;
        try { hashTablePtr = *(ulong*)Exp039_HashTablePtrAddr; } catch { }

        // Only log first 20 calls + every 100th
        if (callNum <= 20 || callNum % 100 == 0)
        {
            Console.Error.WriteLine(
                $"[EXP039-HASH_LOOKUP-ENTER] #{callNum} caller=0x{callerRip:X16} " +
                $"tid={tid} hash_input=0x{edi:X8} hash_table=0x{hashTablePtr:X16}");
            Console.Error.Flush();
        }

        // Restore and let it execute
        var ptr = (byte*)Exp039_HashLookupAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp039_HashLookupAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp039HashLookupOriginalByte;
            VirtualProtect((void*)Exp039_HashLookupAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp039_HashLookupAddr, 16u);
        }
        _exp039HashLookupPatched = false;

        WriteCtxU64(contextRecord, 248, Exp039_HashLookupAddr);
        return true;
    }
}
