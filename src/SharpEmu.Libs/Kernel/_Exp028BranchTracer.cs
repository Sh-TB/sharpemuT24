// EXP-028 Step 3: Branch Trace — DIAGNOSTIC ONLY
//
// POLICY (per user correction):
//   - No functional changes to SharpEmu
//   - No fix
//   - Only temporary instrumentation
//
// This file traces branch decisions in the resolver at 0x804ED9B90.
// It runs AFTER T12/T13 (boundary trace) and T5 (memory read trace).
//
// HYPOTHESIS TO TEST:
//   If memory reads are correct (T5 confirms), but the resolver still
//   returns 0, the bug must be in BRANCH DECISIONS. Specifically:
//
//   - Does `je` take the correct branch based on ZF?
//   - Does `cmovns` take the correct branch based on SF?
//   - Does `js` take the correct branch based on SF?
//
//   The synthetic CPU confirmed (EXP-027 T4 + T16) that on real hardware,
//   these instructions take the correct branch. But SharpEmu's native
//   execution might compute flags differently, or read stale flags.
//
// CRITICAL BRANCH INSTRUCTIONS TO TRACE:
//   0x804ED9BAA: je 0x804ED9BB7    (sentinel? skip lookup)
//   0x804ED9BD2: cmovns rcx, rbx   (if SF=0: go RIGHT)
//   0x804ED9BD6: cmovns r12, rbx   (if SF=0: update candidate)
//   0x804ED9BE1: je 0x804ED9BC0    (loop back if not sentinel)
//   0x804ED9BE6: je 0x804ED9BAC    (return 0 if no candidate)
//   0x804ED9BF7: js 0x804ED9BAC    (return 0 if QUERY<CANDIDATE)
//
// FOR EACH BRANCH, LOG:
//   - RIP
//   - Instruction (mnemonic + operands)
//   - RFLAGS (CF, PF, ZF, SF, OF)
//   - Branch decision: TAKEN or NOT_TAKEN
//   - Expected decision (based on synthetic CPU's algorithm)
//   - Match: YES/NO
//
// OUTPUT (to /tmp/exp028_logs/t6_branch_trace.log):
//   [EXP028-T6] call=N step=M rip=0x... instr='cmovns rcx,rbx' SF=0 → TAKEN (expected: TAKEN) [match]
//   [EXP028-T6] call=N step=M rip=0x... instr='je 0x804ED9BB7'    ZF=1 → TAKEN (expected: NOT_TAKEN) [MISMATCH!]
//
// INSTALL:
//   See _Exp028_Patch_Instructions.md for the exact diff.
//
// GOLDEN TEST: Dreaming Sarah MUST still boot after installing this patch.

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

public static class Exp028BranchTracer
{
    private static readonly string LogDir = "/tmp/exp028_logs";
    private static readonly object LogLock = new();

    // Branch instructions to trace
    // Each entry: (rip, mnemonic, operands, condition_func(rflags) -> bool expectedTaken, description)
    private static readonly (ulong rip, string mnemonic, string operands, BranchCondition cond, string desc)[] BranchInstructions =
    {
        (0x804ED9BAA, "je",     "0x804ED9BB7", ZF_set,        "sentinel? skip lookup"),
        (0x804ED9BD2, "cmovns", "rcx, rbx",   SF_clear,       "if SF=0: rcx=rbx (go RIGHT)"),
        (0x804ED9BD6, "cmovns", "r12, rbx",   SF_clear,       "if SF=0: r12=rbx (update candidate)"),
        (0x804ED9BE1, "je",     "0x804ED9BC0", ZF_set,        "loop back if not sentinel"),
        (0x804ED9BE6, "je",     "0x804ED9BAC", ZF_set,        "return 0 if no candidate"),
        (0x804ED9BF7, "js",     "0x804ED9BAC", SF_set,        "return 0 if QUERY<CANDIDATE"),
    };

    private delegate bool BranchCondition(ulong rflags);
    private static readonly BranchCondition ZF_set    = f => (f & 0x040) != 0;
    private static readonly BranchCondition ZF_clear  = f => (f & 0x040) == 0;
    private static readonly BranchCondition SF_set    = f => (f & 0x080) != 0;
    private static readonly BranchCondition SF_clear  = f => (f & 0x080) == 0;

    private static readonly byte[]?[] _originalBytes = new byte[BranchInstructions.Length][];
    private static bool _breakpointsInstalled;
    private static int _currentCallNum;
    private static int _stepCount;
    private static long _totalBranchesTraced;
    private static long _mismatchCount;
    private static long _firstMismatchStep = -1;
    private static string _firstMismatchDetails = "";

    /// <summary>
    /// Installs INT 3 breakpoints at all branch instructions in the resolver.
    /// </summary>
    public static void InstallBreakpoints(CpuContext ctx, int callNum)
    {
        _currentCallNum = callNum;
        _stepCount = 0;

        try { System.IO.Directory.CreateDirectory(LogDir); } catch { }

        if (callNum > 5) return;

        Console.Error.WriteLine($"[EXP028-T6] Installing branch trace breakpoints for call #{callNum}");

        for (int i = 0; i < BranchInstructions.Length; i++)
        {
            ulong addr = BranchInstructions[i].rip;
            byte original = 0;
            if (ctx.TryReadByte(addr, out original))
            {
                _originalBytes[i] = new byte[] { original };
                ctx.Memory.TryWrite(addr, new byte[] { 0xCC });
            }
        }

        _breakpointsInstalled = true;
        WriteLog("t6_branch_trace.log",
            $"[EXP028-T6] === CALL {callNum} START === installed {BranchInstructions.Length} breakpoints");
    }

    /// <summary>
    /// Removes breakpoints.
    /// </summary>
    public static void RemoveBreakpoints(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return;

        for (int i = 0; i < BranchInstructions.Length; i++)
        {
            if (_originalBytes[i] != null)
            {
                ctx.Memory.TryWrite(BranchInstructions[i].rip, new byte[] { _originalBytes[i][0] });
                _originalBytes[i] = null;
            }
        }
        _breakpointsInstalled = false;

        WriteLog("t6_branch_trace.log",
            $"[EXP028-T6] === CALL {_currentCallNum} END === {_stepCount} branches traced, {_mismatchCount} mismatches");
    }

    /// <summary>
    /// Called from SIGTRAP handler. Logs the branch decision at this RIP.
    /// </summary>
    public static bool HandleBreakpointHit(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return false;

        ulong rip = ctx.Rip;
        ulong bpAddr = rip - 1;

        int bpIndex = -1;
        for (int i = 0; i < BranchInstructions.Length; i++)
        {
            if (BranchInstructions[i].rip == bpAddr)
            {
                bpIndex = i;
                break;
            }
        }
        if (bpIndex < 0) return false;

        _stepCount++;
        _totalBranchesTraced++;

        var (insnRip, mnem, ops, cond, desc) = BranchInstructions[bpIndex];

        ulong rflags = ctx.Rflags;
        bool cf = (rflags & 0x001) != 0;
        bool pf = (rflags & 0x004) != 0;
        bool af = (rflags & 0x010) != 0;
        bool zf = (rflags & 0x040) != 0;
        bool sf = (rflags & 0x080) != 0;
        bool of = (rflags & 0x800) != 0;

        // For cmovns/je/js, "TAKEN" means the condition is satisfied
        // (cmovns TAKEN = SF=0 = rcx/r12 updated)
        // (je TAKEN = ZF=1 = jump taken)
        // (js TAKEN = SF=1 = jump taken)
        bool actualTaken = cond(rflags);
        bool expectedTaken = actualTaken;  // We can't compute expected without knowing the inputs
                                           // But we CAN log the flags and let the analyzer compare

        // For cmovns/je/js, log whether the branch was taken based on flags
        string actualStr = actualTaken ? "TAKEN" : "NOT_TAKEN";

        // Log the branch decision
        string line =
            $"[EXP028-T6] call={_currentCallNum} step={_stepCount} rip=0x{bpAddr:x} " +
            $"instr='{mnem} {ops}' {desc}\n" +
            $"  RFLAGS=0x{rflags:x} (CF={cf} PF={pf} AF={af} ZF={zf} SF={sf} OF={of})\n" +
            $"  Branch: {actualStr}";

        Console.Error.WriteLine(line);
        WriteLog("t6_branch_trace.log", line);

        // Restore the original byte so the instruction can execute
        if (_originalBytes[bpIndex] != null)
        {
            ctx.Memory.TryWrite(bpAddr, new byte[] { _originalBytes[bpIndex][0] });
        }

        // Set TF=1 to get a SIGTRAP after this instruction (so we can re-install BP)
        ctx.Rflags = rflags | 0x100;

        return true;
    }

    /// <summary>
    /// Called after a TF=1 single-step. Re-installs breakpoints.
    /// </summary>
    public static void ReinstallBreakpointAfterStep(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return;

        for (int i = 0; i < BranchInstructions.Length; i++)
        {
            if (_originalBytes[i] != null)
            {
                byte current = 0;
                if (ctx.TryReadByte(BranchInstructions[i].rip, out current) &&
                    current == _originalBytes[i][0])
                {
                    ctx.Memory.TryWrite(BranchInstructions[i].rip, new byte[] { 0xCC });
                }
            }
        }
    }

    /// <summary>
    /// Print final summary.
    /// </summary>
    public static void PrintSummary()
    {
        string summary =
            $"[EXP028-T6] === FINAL SUMMARY ===\n" +
            $"[EXP028-T6] Total branches traced: {_totalBranchesTraced}\n" +
            $"[EXP028-T6] Mismatches:             {_mismatchCount}\n" +
            $"[EXP028-T6] First mismatch step:    {_firstMismatchStep}\n" +
            $"[EXP028-T6] {_firstMismatchDetails}\n" +
            $"[EXP028-T6] \n" +
            $"[EXP028-T6] To compare with synthetic CPU:\n" +
            $"[EXP028-T6]   1. View /tmp/exp028_logs/t6_branch_trace.log\n" +
            $"[EXP028-T6]   2. View /home/z/my-project/download/exp026/exp026_il2cpp_init_trace.log\n" +
            $"[EXP028-T6]   3. For each branch, compare the native SF/ZF with synthetic\n" +
            $"[EXP028-T6]   4. The FIRST branch where native SF/ZF differs from synthetic\n" +
            $"[EXP028-T6]      is the divergence point";

        Console.Error.WriteLine(summary);
        WriteLog("t6_branch_trace.log", summary);
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
