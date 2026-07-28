// EXP-028 Step 1: T12/T13 Boundary Trace — DIAGNOSTIC ONLY
//
// POLICY (per user correction):
//   - No functional changes to SharpEmu
//   - No fix
//   - Only temporary instrumentation
//   - Debug patch ≠ Code fix
//
// This file logs register state before/after TryCallGuestFunction in
// DispatchIl2CppApiLookupSymbol. It does NOT modify:
//   - The resolver's algorithm
//   - Flag computation
//   - Memory access patterns
//   - Return value propagation
//
// The resolver's computed return value is preserved exactly.
//
// TESTS:
//   T12: Call chain trace — log RAX at each boundary (caller, resolver, wrapper)
//   T13: Return corruption test — detect if resolver returns non-zero but
//        caller sees RAX=0 (which would indicate return propagation bug)
//
// THREE HYPOTHESES TO DISTINGUISH:
//
//   Case A: Bad input (RDI=0 or garbage at resolver entry)
//     → Bug is in CALL SETUP (TryCallGuestFunction register initialization)
//     → Continue investigation: T5 (Memory Read Trace) won't help;
//       focus on TryCallGuestFunction context setup
//
//   Case B: Resolver computes correct RAX internally but ReturnValue=0
//     → Bug is in RETURN PROPAGATION (ABI / context restore)
//     → Continue investigation: examine how TryCallGuestFunction reads
//       back RAX from the guest context after execution
//
//   Case C: Resolver genuinely returns 0 (RAX=0 inside, ReturnValue=0)
//     → Bug is INSIDE the resolver's native execution
//     → Continue investigation: T5 (Memory Read Trace), then T6 (Branch Trace),
//       then T1 (Per-Instruction INT3)
//
// OUTPUT (to /tmp/exp028_logs/t12_t13_boundary.log):
//   [EXP028-T12-PRE]  call=N query='...' entry=0x... RDI=0x... RAX=0x... RSP=0x... RFLAGS=0x...
//   [EXP028-T12-POST] call=N returnValue=0x... cpuContext.Rax=0x... error='...'
//   [EXP028-T13] *** RETURN CORRUPTION *** ...   (only if Case B detected)
//   [EXP028-T13] Resolver genuinely returned 0   (Case C confirmed)
//   [EXP028-T13] Resolver returned non-zero, RAX correctly propagated   (resolver works)
//
// INSTALL:
//   See _Exp028_Patch_Instructions.md for the exact diff to apply to
//   src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs
//   in function DispatchIl2CppApiLookupSymbol.
//
// GOLDEN TEST (Dreaming Sarah):
//   After installing this patch, Dreaming Sarah MUST still boot and run
//   without crashes or behavior changes. This proves the patch is
//   diagnostic-only. Run the Golden Test BEFORE collecting Yatzi traces.

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

public static class Exp028T12T13BoundaryTrace
{
    private static readonly string LogDir = "/tmp/exp028_logs";
    private static readonly object LogLock = new();

    private static long _callCount;
    private static long _caseACount;  // bad input
    private static long _caseBCount;  // return corruption
    private static long _caseCCount;  // genuine zero
    private static long _caseOKCount; // resolver works

    /// <summary>
    /// Called BEFORE TryCallGuestFunction in DispatchIl2CppApiLookupSymbol.
    /// Logs the pre-call register state. DIAGNOSTIC ONLY — no behavior change.
    /// </summary>
    public static void LogPreCall(
        CpuContext ctx,
        long callNum,
        string query,
        ulong entryPoint,
        ulong symbolNameAddress)
    {
        _callCount++;

        try { System.IO.Directory.CreateDirectory(LogDir); } catch { }

        ulong rax = ctx[CpuRegister.Rax];
        ulong rbx = ctx[CpuRegister.Rbx];
        ulong rcx = ctx[CpuRegister.Rcx];
        ulong rdx = ctx[CpuRegister.Rdx];
        ulong rsi = ctx[CpuRegister.Rsi];
        ulong rdi = ctx[CpuRegister.Rdi];
        ulong r8  = ctx[CpuRegister.R8];
        ulong r9  = ctx[CpuRegister.R9];
        ulong r12 = ctx[CpuRegister.R12];
        ulong r13 = ctx[CpuRegister.R13];
        ulong r14 = ctx[CpuRegister.R14];
        ulong r15 = ctx[CpuRegister.R15];
        ulong rbp = ctx[CpuRegister.Rbp];
        ulong rsp = ctx[CpuRegister.Rsp];
        ulong rflags = ctx.Rflags;

        // Decode RFLAGS
        bool cf = (rflags & 0x001) != 0;
        bool pf = (rflags & 0x004) != 0;
        bool af = (rflags & 0x010) != 0;
        bool zf = (rflags & 0x040) != 0;
        bool sf = (rflags & 0x080) != 0;
        bool of = (rflags & 0x800) != 0;
        bool tf = (rflags & 0x100) != 0;
        bool iff = (rflags & 0x200) != 0;

        string line =
            $"[EXP028-T12-PRE]  call={callNum} query='{query}' entry=0x{entryPoint:x} symAddr=0x{symbolNameAddress:x}\n" +
            $"  RAX=0x{rax:x} RBX=0x{rbx:x} RCX=0x{rcx:x} RDX=0x{rdx:x}\n" +
            $"  RSI=0x{rsi:x} RDI=0x{rdi:x} R8=0x{r8:x} R9=0x{r9:x}\n" +
            $"  R12=0x{r12:x} R13=0x{r13:x} R14=0x{r14:x} R15=0x{r15:x}\n" +
            $"  RBP=0x{rbp:x} RSP=0x{rsp:x}\n" +
            $"  RFLAGS=0x{rflags:x} (CF={cf} PF={pf} AF={af} ZF={zf} SF={sf} OF={of} TF={tf} IF={iff})";

        Console.Error.WriteLine(line);
        WriteLog("t12_t13_boundary.log", line);

        // T12 Case A: Bad input — RDI=0 means resolver can't read query string
        if (rdi == 0)
        {
            _caseACount++;
            string warn = $"[EXP028-T12-CASE-A] call={callNum} *** BAD INPUT: RDI=0 ***\n" +
                          $"  → Bug is in TryCallGuestFunction register setup (RDI not set to query)";
            Console.Error.WriteLine(warn);
            WriteLog("t12_t13_boundary.log", warn);
        }
        // T12 Case A: Bad input — RSP=0 means resolver will crash on push
        if (rsp == 0)
        {
            _caseACount++;
            string warn = $"[EXP028-T12-CASE-A] call={callNum} *** BAD INPUT: RSP=0 ***\n" +
                          $"  → Bug is in TryCallGuestFunction stack setup (RSP not initialized)";
            Console.Error.WriteLine(warn);
            WriteLog("t12_t13_boundary.log", warn);
        }
    }

    /// <summary>
    /// Called AFTER TryCallGuestFunction returns. Logs post-call register state
    /// and detects return-value corruption. DIAGNOSTIC ONLY.
    /// </summary>
    public static void LogPostCall(
        CpuContext ctx,
        long callNum,
        string query,
        ulong returnValue,
        string? error)
    {
        ulong postRax = ctx[CpuRegister.Rax];
        ulong postRbx = ctx[CpuRegister.Rbx];
        ulong postR12 = ctx[CpuRegister.R12];
        ulong postR14 = ctx[CpuRegister.R14];
        ulong postR15 = ctx[CpuRegister.R15];
        ulong postRflags = ctx.Rflags;

        bool postSF = (postRflags & 0x080) != 0;
        bool postZF = (postRflags & 0x040) != 0;

        string line =
            $"[EXP028-T12-POST] call={callNum} query='{query}'\n" +
            $"  returnValue=0x{returnValue:x} error='{error}'\n" +
            $"  cpuContext.Rax=0x{postRax:x} RBX=0x{postRbx:x} R12=0x{postR12:x} R14=0x{postR14:x} R15=0x{postR15:x}\n" +
            $"  RFLAGS=0x{postRflags:x} (SF={postSF} ZF={postZF})";

        Console.Error.WriteLine(line);
        WriteLog("t12_t13_boundary.log", line);

        // T13: Return corruption detection
        if (returnValue != 0)
        {
            _caseOKCount++;
            if (postRax != returnValue)
            {
                _caseBCount++;
                _caseOKCount--;  // re-classify
                string corrupt =
                    $"[EXP028-T13-CASE-B] *** RETURN CORRUPTION *** call={callNum}\n" +
                    $"  Resolver returned 0x{returnValue:x} but cpuContext.Rax = 0x{postRax:x}\n" +
                    $"  → Bug is in RETURN PROPAGATION (TryCallGuestFunction reads back RAX incorrectly)\n" +
                    $"  → Investigate: how does TryCallGuestFunction extract RAX from guest context after execution?";
                Console.Error.WriteLine(corrupt);
                WriteLog("t12_t13_boundary.log", corrupt);
            }
            else
            {
                string ok =
                    $"[EXP028-T13-OK] Resolver returned non-zero (0x{returnValue:x}), RAX correctly propagated";
                Console.Error.WriteLine(ok);
                WriteLog("t12_t13_boundary.log", ok);
            }
        }
        else
        {
            _caseCCount++;
            string genuine =
                $"[EXP028-T13-CASE-C] Resolver genuinely returned 0 (no corruption detected)\n" +
                $"  → Bug is INSIDE the resolver's native execution\n" +
                $"  → Continue with T5 (Memory Read Trace), then T6 (Branch Trace), then T1 (Per-Instruction INT3)";
            Console.Error.WriteLine(genuine);
            WriteLog("t12_t13_boundary.log", genuine);
        }
    }

    /// <summary>
    /// Print final summary. Call from any shutdown hook.
    /// </summary>
    public static void PrintSummary()
    {
        string summary =
            $"[EXP028-T12/T13] === FINAL SUMMARY ===\n" +
            $"[EXP028-T12/T13] Total resolver calls:       {_callCount}\n" +
            $"[EXP028-T12/T13] Case A (bad input):         {_caseACount}\n" +
            $"[EXP028-T12/T13] Case B (return corruption): {_caseBCount}\n" +
            $"[EXP028-T12/T13] Case C (genuine zero):      {_caseCCount}\n" +
            $"[EXP028-T12/T13] Case OK (resolver works):   {_caseOKCount}\n";

        Console.Error.WriteLine(summary);
        WriteLog("t12_t13_boundary.log", summary);

        if (_caseACount > 0)
        {
            Console.Error.WriteLine(
                "[EXP028-T12/T13] CONCLUSION: Bug is in TryCallGuestFunction register setup (RDI/RSP not initialized correctly).");
            Console.Error.WriteLine(
                "[EXP028-T12/T13] → Investigate: DirectExecutionBackend.cs::TryCallGuestFunction context initialization");
        }
        else if (_caseBCount > 0)
        {
            Console.Error.WriteLine(
                "[EXP028-T12/T13] CONCLUSION: Bug is in return value propagation between guest and host.");
            Console.Error.WriteLine(
                "[EXP028-T12/T13] → Investigate: how TryCallGuestFunction extracts RAX from guest context after execution");
        }
        else if (_caseCCount == _callCount && _caseOKCount == 0)
        {
            Console.Error.WriteLine(
                "[EXP028-T12/T13] CONCLUSION: Resolver GENUINELY returns 0 for all calls.");
            Console.Error.WriteLine(
                "[EXP028-T12/T13] → Bug is INSIDE the resolver's native execution.");
            Console.Error.WriteLine(
                "[EXP028-T12/T13] → Next step: T5 (Memory Read Trace) to check if resolver reads same bytes as synthetic CPU");
        }
        else if (_caseOKCount == _callCount)
        {
            Console.Error.WriteLine(
                "[EXP028-T12/T13] CONCLUSION: Resolver works correctly! All calls returned non-zero.");
            Console.Error.WriteLine(
                "[EXP028-T12/T13] → If Yatzi still doesn't boot, the bug is elsewhere (Stage 7+).");
        }
    }

    private static void WriteLog(string filename, string line)
    {
        lock (LogLock)
        {
            try
            {
                string path = System.IO.Path.Combine(LogDir, filename);
                System.IO.File.AppendAllText(path, line + "\n");
            }
            catch { }
        }
    }
}
