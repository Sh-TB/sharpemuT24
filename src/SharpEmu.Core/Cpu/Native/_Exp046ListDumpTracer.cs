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

    // EXP-046: INT3 at 0x80134FA6F (after metadata lookup in crash path)
    private const ulong Exp046_CrashPathAfterLookup = 0x80134FA6F;
    private byte _exp046CrashPathOriginalByte;
    private bool _exp046CrashPathPatched;

    private unsafe void Exp046PatchCrashPathLookup()
    {
        if (_exp046CrashPathPatched) return;
        try
        {
            var ptr = (byte*)Exp046_CrashPathAfterLookup;
            uint flNP = 0;
            if (VirtualProtect((void*)Exp046_CrashPathAfterLookup, 16u, 64u, &flNP))
            {
                _exp046CrashPathOriginalByte = ptr[0];
                ptr[0] = 0xCC;
                _exp046CrashPathPatched = true;
                Console.Error.WriteLine(
                    $"[EXP046-PATCH] crash_path_after_lookup at 0x{Exp046_CrashPathAfterLookup:X16} patched");
                VirtualProtect((void*)Exp046_CrashPathAfterLookup, 16u, flNP, &flNP);
                FlushInstructionCache(GetCurrentProcess(), (void*)Exp046_CrashPathAfterLookup, 16u);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[EXP046] Failed to patch crash_path: {ex.Message}");
        }
    }

    private unsafe bool Exp046TryHandleCrashPathInt3(void* contextRecord, ulong rip)
    {
        if (!_exp046CrashPathPatched) return false;
        if (rip - 1 != Exp046_CrashPathAfterLookup) return false;

        int tid = Environment.CurrentManagedThreadId;
        ulong rax = ReadCtxU64(contextRecord, 120); // CTX_RAX = lookup result
        ulong rsp = ReadCtxU64(contextRecord, 152);

        Console.Error.WriteLine(
            $"[EXP046-CRASH_PATH_LOOKUP] tid={tid} rax=0x{rax:X16} (metadata lookup result)");

        if (rax == 0)
        {
            Console.Error.WriteLine("  → lookup returned 0 (NULL) — call [0] will SIGSEGV");
        }
        else
        {
            try
            {
                // Check if rax is a valid object with a vtable
                ulong vtable = *(ulong*)rax;
                Console.Error.WriteLine($"  → object at 0x{rax:X16}, vtable=0x{vtable:X16}");
                if (vtable != 0)
                {
                    ulong fn0 = *(ulong*)vtable;
                    Console.Error.WriteLine($"  → vtable[0] = 0x{fn0:X16}");
                    if (fn0 == 0x80135DDD0)
                        Console.Error.WriteLine("  → *** THIS IS THE CRASH FUNCTION! ***");
                    else
                        Console.Error.WriteLine("  → Different function (NOT the crash function)");
                }
            }
            catch { }
        }

        // Also dump what's at [rsp] (return address) and [rsp+8]
        try
        {
            ulong retAddr = *(ulong*)rsp;
            Console.Error.WriteLine($"  [rsp] = 0x{retAddr:X16} (return address)");
        }
        catch { }

        Console.Error.Flush();

        // Restore and let it execute
        var ptr = (byte*)Exp046_CrashPathAfterLookup;
        uint flNP = 0;
        if (VirtualProtect((void*)Exp046_CrashPathAfterLookup, 16u, 64u, &flNP))
        {
            ptr[0] = _exp046CrashPathOriginalByte;
            VirtualProtect((void*)Exp046_CrashPathAfterLookup, 16u, flNP, &flNP);
            FlushInstructionCache(GetCurrentProcess(), (void*)Exp046_CrashPathAfterLookup, 16u);
        }
        _exp046CrashPathPatched = false;

        WriteCtxU64(contextRecord, 248, Exp046_CrashPathAfterLookup);
        return true;
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
