// EXP-097: Runtime tracer — read the 7 runtime-set function pointer globals
// at the point where the _ThreadPoolWaitCallback lookup succeeds.
//
// From static analysis (EXP-097 Step 4):
//   7 RW data globals are called via call [rip+disp] and are NULL at file time.
//   They must be populated at runtime. If any remains NULL, that's a missing
//   function pointer registration.
//
// The globals (all in 0x808B417E0..0x808B41938 range):
//   0x808B417E0  (1 call site)
//   0x808B417E8  (2 call sites)
//   0x808B417F8  (2 call sites)
//   0x808B418E8  (1 call site)
//   0x808B418F0  (35 call sites!)  ← most heavily used
//   0x808B41900  (15 call sites)
//   0x808B41938  (1 call site)
//
// Also reads the 3 IL2CPP registration globals:
//   0x808B542E8  (Il2CppCodeRegistration*)
//   0x808B542F0  (Il2CppMetadataRegistration*)
//   0x808B542F8  (method pointers array)
//
// And checks if any of these point to structures containing the 5 dead-code
// function addresses (0x804F456E0, 0x804F9FA80, 0x804FA1440, 0x804FA1FE0, 0x804F6EC20).

using System;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    // ===== EXP-097: Function pointer global dump =====

    // The 7 runtime-set function pointer globals (called via call [rip+disp])
    private static readonly ulong[] Exp097_FuncPtrGlobals = new ulong[]
    {
        0x808B417E0,
        0x808B417E8,
        0x808B417F8,
        0x808B418E8,
        0x808B418F0,  // 35 call sites — most heavily used
        0x808B41900,  // 15 call sites
        0x808B41938,
    };

    // The 3 IL2CPP registration globals (saved by il2cpp_codegen_register)
    private static readonly ulong[] Exp097_Il2CppGlobals = new ulong[]
    {
        0x808B542E8,
        0x808B542F0,
        0x808B542F8,
    };

    // The 5 dead-code function addresses we're looking for
    private static readonly ulong[] Exp097_DeadCodeTargets = new ulong[]
    {
        0x804F456E0,
        0x804F9FA80,
        0x804FA1440,
        0x804FA1FE0,
        0x804F6EC20,
    };

    private bool _exp097Dumped;

    /// <summary>
    /// Dumps all function pointer globals and IL2CPP registration globals.
    /// Called once from the EXP-095 return-site handler (after lookup succeeds).
    /// </summary>
    private unsafe void Exp097DumpFunctionPointerGlobals()
    {
        if (_exp097Dumped) return;
        _exp097Dumped = true;

        Console.Error.WriteLine("[EXP097] ===== Function Pointer Global Dump =====");

        // Dump the 7 runtime-set function pointer globals
        Console.Error.WriteLine("[EXP097] --- 7 runtime-set function pointer globals (call [rip+disp] targets) ---");
        for (int i = 0; i < Exp097_FuncPtrGlobals.Length; i++)
        {
            ulong addr = Exp097_FuncPtrGlobals[i];
            ulong val = 0;
            try { val = *(ulong*)addr; } catch { }
            string status;
            if (val == 0)
                status = "*** NULL — never set! ***";
            else if (val == 0xFFFFFFFFFFFFFFFF)
                status = "(sentinel 0xFFFF...)";
            else
            {
                // Check if the value is one of our dead-code targets
                bool isDeadCode = false;
                for (int j = 0; j < Exp097_DeadCodeTargets.Length; j++)
                {
                    if (val == Exp097_DeadCodeTargets[j])
                    {
                        isDeadCode = true;
                        break;
                    }
                }
                status = isDeadCode ? "*** MATCHES DEAD-CODE FUNCTION ***" : "(populated)";
            }
            // Classify the value
            string region = "";
            if (val >= 0x804CD5000 && val < 0x808800000) region = " (PRX code)";
            else if (val >= 0x800000000 && val < 0x804CD5000) region = " (EBOOT code)";
            else if (val >= 0x600000000 && val < 0x700000000) region = " (guest heap)";
            Console.Error.WriteLine($"  [0x{addr:X}] = 0x{val:X16}{region}  {status}");
        }

        // Dump the 3 IL2CPP registration globals
        Console.Error.WriteLine("[EXP097] --- 3 IL2CPP registration globals (saved by il2cpp_codegen_register) ---");
        for (int i = 0; i < Exp097_Il2CppGlobals.Length; i++)
        {
            ulong addr = Exp097_Il2CppGlobals[i];
            ulong val = 0;
            try { val = *(ulong*)addr; } catch { }
            string status = val == 0 ? "*** NULL — il2cpp_codegen_register not yet called! ***" : "(populated)";
            string region = "";
            if (val >= 0x804CD5000 && val < 0x808800000) region = " (PRX)";
            else if (val >= 0x800000000 && val < 0x804CD5000) region = " (EBOOT)";
            else if (val >= 0x600000000 && val < 0x700000000) region = " (guest heap)";
            Console.Error.WriteLine($"  [0x{addr:X}] = 0x{val:X16}{region}  {status}");
        }

        // Also dump the once-init guard
        Console.Error.WriteLine("[EXP097] --- Once-init guard ---");
        try
        {
            ulong guardVal = *(ulong*)0x808B418D8;
            Console.Error.WriteLine($"  [0x808B418D8] = 0x{guardVal:X16}  {(guardVal == 0xFFFFFFFFFFFFFFFF ? "(sentinel — not yet initialized)" : guardVal == 0 ? "(cleared)" : "(initialized)")}");
        }
        catch { }

        Console.Error.Flush();
    }
}
