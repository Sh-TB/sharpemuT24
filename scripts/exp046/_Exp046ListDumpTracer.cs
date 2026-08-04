// EXP-046: Comprehensive metadata lookup + registration list tracer.
//
// This tracer:
// 1. Dumps the full registration list at [0x801E9DF28] when the metadata
//    lookup is called
// 2. Traces the metadata lookup's search path (0x800C66B40)
// 3. Dumps the returned object's vtable and function pointer
// 4. Checks if the metadata lookup returns 0 or non-zero

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-046: Metadata lookup + list dump =====

    private const ulong Exp046_ListHeadAddr = 0x801E9DF28;

    /// <summary>
    /// Dumps the registration list at [0x801E9DF28].
    /// Called from the metadata lookup INT3 handler.
    /// </summary>
    public void Exp046DumpRegistrationList(string context)
    {
        try
        {
            ulong head = *(ulong*)Exp046_ListHeadAddr;
            Console.Error.WriteLine($"[EXP046-LIST] {context}: list_head [0x801E9DF28] = 0x{head:X16}");

            if (head == 0)
            {
                Console.Error.WriteLine("[EXP046-LIST] List is EMPTY (NULL)");
                return;
            }

            // Walk the list (max 50 entries)
            ulong current = head;
            int count = 0;
            while (current != 0 && count < 50)
            {
                try
                {
                    // Entry layout:
                    // +0x08: argument (string pointer or value)
                    // +0x10: function pointer
                    // +0x20: flag/done byte
                    // +0x28: next pointer (or +0x30?)
                    // Let me try both +0x28 and +0x30
                    ulong arg = *(ulong*)(current + 0x08);
                    ulong funcPtr = *(ulong*)(current + 0x10);
                    byte flag = *((byte*)(current + 0x20));
                    ulong next28 = *(ulong*)(current + 0x28);
                    ulong next30 = *(ulong*)(current + 0x30);

                    Console.Error.WriteLine(
                        $"  [{count:2d}] node=0x{current:X16} arg=0x{arg:X16} " +
                        $"func=0x{funcPtr:X16} flag=0x{flag:X2} " +
                        $"next28=0x{next28:X16} next30=0x{next30:X16}");

                    // Follow next pointer (try +0x28 first, then +0x30)
                    if (next28 == current || next30 == current)
                    {
                        Console.Error.WriteLine("  (self-referencing → end of list)");
                        break;
                    }
                    if (next28 != 0 && next28 != current)
                        current = next28;
                    else if (next30 != 0 && next30 != current)
                        current = next30;
                    else
                        break;
                }
                catch
                {
                    Console.Error.WriteLine($"  [{count:2d}] node=0x{current:X16} → READ ERROR");
                    break;
                }
                count++;
            }
            Console.Error.WriteLine($"  Total entries: {count}");
            Console.Error.Flush();
        }
        catch { }
    }

    /// <summary>
    /// Traces the metadata lookup result.
    /// Called from the metadata lookup INT3 handler AFTER it returns.
    /// </summary>
    public void Exp046DumpLookupResult(ulong rax, string context)
    {
        Console.Error.WriteLine($"[EXP046-LOOKUP-RESULT] {context}: rax=0x{rax:X16}");

        if (rax == 0)
        {
            Console.Error.WriteLine("  → Returned 0 (NULL) — no object found");
            return;
        }

        try
        {
            // The returned object has a vtable at [rax]
            ulong vtable = *(ulong*)rax;
            Console.Error.WriteLine($"  → Object at 0x{rax:X16}, vtable=0x{vtable:X16}");

            if (vtable != 0)
            {
                // Dump first 5 vtable entries
                for (int i = 0; i < 5; i++)
                {
                    ulong fnPtr = *(ulong*)(vtable + (ulong)i * 8);
                    Console.Error.WriteLine($"    vtable[{i}] = 0x{fnPtr:X16}");
                }
            }
        }
        catch { }
        Console.Error.Flush();
    }
}
