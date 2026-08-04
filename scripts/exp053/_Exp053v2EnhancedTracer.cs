// EXP-053 v2: Enhanced tracer with wider static table dump + correct hash table ptr addr.
// Replaces the original _Exp053WrapperTracer.cs.

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-053 v2: Enhanced tracing =====

    // The wrapper tracer from v1 is reused. This file adds:
    // - A wider static table dump (0x800 bytes, covering ~4 entries)
    // - Periodic state polling (every 10s) to track when hash table gets populated

    private const ulong Exp053v2_StaticTableAddr = 0x801CC0080;
    private const ulong Exp053v2_HashTablePtrAddr = 0x801EF7610;  // CORRECT
    private const ulong Exp053v2_HashTableStructAddr = 0x801E51618;
    private const ulong Exp053v2_OnceInitFlagAddr = 0x801E516F0;

    /// <summary>
    /// Dumps a wider region of the static table and hash table state.
    /// Call this from the wrapper INT3 handler when the wrapper IS hit,
    /// OR from a periodic timer.
    /// </summary>
    private unsafe void Exp053v2DumpState(string context)
    {
        Console.Error.WriteLine($"[EXP053v2-STATE] context={context}");
        try
        {
            ulong htPtr = *(ulong*)Exp053v2_HashTablePtrAddr;
            ulong htStruct = *(ulong*)Exp053v2_HashTableStructAddr;
            byte onceFlag = *(byte*)Exp053v2_OnceInitFlagAddr;
            Console.Error.WriteLine(
                $"  hash_table_ptr=0x{htPtr:X16} (CORRECT ADDR 0x801EF7610) " +
                $"hash_struct=0x{htStruct:X16} once_flag=0x{onceFlag:X2}");

            if (htPtr != 0)
            {
                ulong entriesPtr = *(ulong*)htPtr;
                ulong mask = *(ulong*)(htPtr + 8);
                Console.Error.WriteLine($"  entries_ptr=0x{entriesPtr:X16} mask=0x{mask:X16}");

                if (entriesPtr != 0)
                {
                    int populated = 0;
                    int total = 1000;
                    for (int i = 0; i < total; i++)
                    {
                        uint entryHash = *(uint*)(entriesPtr + (ulong)i * 0x38);
                        if (entryHash != 0xFFFFFFFF && entryHash != 0)
                            populated++;
                    }
                    Console.Error.WriteLine($"  populated_entries(0-{total})={populated}");
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"  state read failed: {ex.Message}");
        }

        // Dump first 0x800 bytes of static table (covers ~4 entries of 0x218 bytes each)
        Console.Error.WriteLine($"  static_table at 0x{Exp053v2_StaticTableAddr:X16} (first 0x800 bytes):");
        try
        {
            byte* tbl = (byte*)Exp053v2_StaticTableAddr;
            for (int i = 0; i < 0x800; i += 8)
            {
                ulong val = *(ulong*)(tbl + i);
                if (val != 0)
                {
                    Console.Error.WriteLine($"    +0x{i:X4}: 0x{val:X16}");
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"  table read failed: {ex.Message}");
        }
        Console.Error.Flush();
    }
}
