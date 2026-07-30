// EXP-039: Trace if the hash table writer (0x8007F90A0) is ever called.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    private const ulong Exp039_HashTableWriterAddr = 0x8007F90A0;
    private byte _exp039HashTableWriterOriginalByte;
    private bool _exp039HashTableWriterPatched;
    private int _exp039HashTableWriterCallCount;

    private unsafe void Exp039PatchHashTableWriter()
    {
        if (_exp039HashTableWriterPatched) return;
        try
        {
            var ptr = (byte*)Exp039_HashTableWriterAddr;
            uint flNewProtect = 0;
            if (VirtualProtect((void*)Exp039_HashTableWriterAddr, 16u, 64u, &flNewProtect))
            {
                _exp039HashTableWriterOriginalByte = ptr[0];
                ptr[0] = 0xCC; // INT3
                _exp039HashTableWriterPatched = true;
                Console.Error.WriteLine(
                    $"[EXP039-PATCH] hash_table_writer at 0x{Exp039_HashTableWriterAddr:X16} patched with INT3 " +
                    $"(original byte=0x{_exp039HashTableWriterOriginalByte:X2})");
                VirtualProtect((void*)Exp039_HashTableWriterAddr, 16u, flNewProtect, &flNewProtect);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp039_HashTableWriterAddr, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP039] Failed to patch hash_table_writer: {ex.Message}");
        }
    }

    private unsafe bool Exp039TryHandleHashTableWriterInt3(void* contextRecord, ulong rip)
    {
        if (!_exp039HashTableWriterPatched) return false;
        if (rip - 1 != Exp039_HashTableWriterAddr) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rsp = ReadCtxU64(contextRecord, 152);
        ulong callerRip = 0;
        try { callerRip = *(ulong*)rsp; } catch { }

        int callNum = Interlocked.Increment(ref _exp039HashTableWriterCallCount);

        // Read current hash table state
        ulong hashTablePtr = 0;
        try { hashTablePtr = *(ulong*)Exp039_HashTablePtrAddr; } catch { }

        Console.Error.WriteLine(
            $"[EXP039-HASH_WRITER-ENTER] #{callNum} caller=0x{callerRip:X16} " +
            $"tid={tid} hash_table_before=0x{hashTablePtr:X16}");

        // EXP-041: Check [0x801EA49D8] (metadata callback global)
        try
        {
            ulong callbackPtr = *(ulong*)0x801EA49D8;
            Console.Error.WriteLine(
                $"[EXP041-CALLBACK-GLOBAL] [0x801EA49D8]=0x{callbackPtr:X16} at hash_writer entry");
        }
        catch { }

        // EXP-045: Check [0x801E9DF28] (registration list head)
        try
        {
            ulong listHead = *(ulong*)0x801E9DF28;
            Console.Error.WriteLine(
                $"[EXP045-LIST_HEAD] [0x801E9DF28]=0x{listHead:X16} at hash_writer entry");
        }
        catch { }

        // Dump stack
        Console.Error.WriteLine("[EXP039-HASH_WRITER-STACK] Return addresses:");
        try
        {
            byte* sp = (byte*)rsp;
            for (int i = 0; i < 16; i++)
            {
                ulong val = *(ulong*)(sp + i * 8);
                if (val >= 0x800000000 && val < 0x810000000)
                {
                    Console.Error.WriteLine($"  [rsp+0x{i*8:X2}] = 0x{val:X16}");
                }
            }
        }
        catch { }
        Console.Error.Flush();

        // Restore original byte and let it execute
        var ptr = (byte*)Exp039_HashTableWriterAddr;
        uint flNewProtect = 0;
        if (VirtualProtect((void*)Exp039_HashTableWriterAddr, 16u, 64u, &flNewProtect))
        {
            ptr[0] = _exp039HashTableWriterOriginalByte;
            VirtualProtect((void*)Exp039_HashTableWriterAddr, 16u, flNewProtect, &flNewProtect);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp039_HashTableWriterAddr, 16u);
        }
        _exp039HashTableWriterPatched = false;

        WriteCtxU64(contextRecord, 248, Exp039_HashTableWriterAddr);
        return true;
    }
}
