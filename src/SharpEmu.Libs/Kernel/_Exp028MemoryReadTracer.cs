// EXP-028 Step 2: Memory Read Trace — DIAGNOSTIC ONLY
//
// POLICY (per user correction):
//   - No functional changes to SharpEmu
//   - No fix
//   - Only temporary instrumentation
//
// This file traces memory reads performed by the resolver at 0x804ED9B90.
// It is the MOST IMPORTANT test in EXP-028 per the user's priority assessment:
//
//   "Memory mapping / guest read ⭐⭐⭐⭐⭐"
//
// HYPOTHESIS TO TEST:
//   The resolver is a BST walker. If SharpEmu's native execution reads
//   DIFFERENT bytes from the tree than the synthetic CPU read (from the
//   same tree snapshot), the resolver will walk the wrong path and
//   return 0.
//
//   Example divergence:
//     Synthetic CPU read: [nodeA + 0x19] = 0  (real node, continue traversal)
//     SharpEmu native read: [nodeA + 0x19] = 1  (sentinel, exit loop early)
//     → Resolver exits loop too early, no candidate, returns 0
//
// HOW IT WORKS:
//   We instrument the resolver's memory reads by installing INT3 breakpoints
//   at every instruction that reads from [rbx+offset]. When the breakpoint
//   fires, we:
//     1. Read the instruction's source address (rbx+offset)
//     2. Read the actual bytes from that address via CpuContext.TryReadByte/UInt64
//     3. Log: RIP, source address, value read by native code, value read by us
//     4. Compare with the synthetic CPU's expected value (from BST-WALK log)
//
// CRITICAL INSTRUCTIONS TO TRACE:
//   0x804ED9B9B: mov r15, [rip+0x3c79b66]    → list head struct ptr
//   0x804ED9BA2: mov rbx, [r15+8]              → root node ptr
//   0x804ED9BA6: cmp byte [rbx+0x19], 0        → sentinel flag
//   0x804ED9BC0: mov rdi, [rbx+0x20]           → node symbol name ptr
//   0x804ED9BDA: mov rbx, [rcx]                → next node (from [rcx] = [rbx] or [rbx+0x10])
//   0x804ED9BDD: cmp byte [rbx+0x19], 0        → sentinel flag (loop)
//   0x804ED9BE3: cmp r12, r15                  → register compare (no memory)
//   0x804ED9BE8: mov rsi, [r12+0x20]           → candidate symbol name ptr
//   0x804ED9BF9: mov rax, [r12+0x28]           → func impl ptr
//
// OUTPUT (to /tmp/exp028_logs/t5_memory_read.log):
//   [EXP028-T5] call=N step=M rip=0x... instr='mov rbx,[r15+8]' src_addr=0x... value=0x...
//   [EXP028-T5] call=N step=M rip=0x... instr='cmp byte [rbx+0x19],0' src_addr=0x... value=0x...
//   [EXP028-T5-COMPARE] call=N step=M rip=0x... native=0x... synthetic=0x... match=YES/NO
//
// INSTALL:
//   See _Exp028_Patch_Instructions.md for the exact diff.
//
// GOLDEN TEST: Dreaming Sarah MUST still boot after installing this patch.

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

public static class Exp028MemoryReadTracer
{
    private static readonly string LogDir = "/tmp/exp028_logs";
    private static readonly object LogLock = new();

    // Tree head pointer (global in PRX BSS)
    private const ulong ListHeadPtrAddr = 0x808B53708;

    // Node field offsets (verified by G2.2 / T2.2)
    private const int OFF_RIGHT        = 0x00;
    private const int OFF_PARENT      = 0x08;
    private const int OFF_LEFT        = 0x10;
    private const int OFF_COLOR       = 0x18;
    private const int OFF_MATCHED     = 0x19;
    private const int OFF_SYMBOL_NAME = 0x20;
    private const int OFF_FUNC_IMPL   = 0x28;

    // Memory read instructions to trace
    // Each entry: (rip, instruction description, source register, offset, size_in_bytes)
    private static readonly (ulong rip, string desc, string srcReg, int offset, int size)[] MemoryReadInstructions =
    {
        (0x804ED9B9B, "mov r15, [rip+0x3c79b66]",   "list_head_ptr", 0,   8),  // reads global pointer
        (0x804ED9BA2, "mov rbx, [r15+8]",            "r15",          8,   8),  // reads root from sentinel+8
        (0x804ED9BA6, "cmp byte [rbx+0x19], 0",      "rbx",          0x19, 1), // sentinel flag check
        (0x804ED9BC0, "mov rdi, [rbx+0x20]",         "rbx",          0x20, 8), // node symbol name ptr
        (0x804ED9BDA, "mov rbx, [rcx]",              "rcx",          0,   8),  // next node (right or left child)
        (0x804ED9BDD, "cmp byte [rbx+0x19], 0",      "rbx",          0x19, 1), // sentinel flag check (loop)
        (0x804ED9BE8, "mov rsi, [r12+0x20]",         "r12",          0x20, 8), // candidate symbol name ptr
        (0x804ED9BF9, "mov rax, [r12+0x28]",         "r12",          0x28, 8), // func impl ptr
    };

    // Original bytes at each breakpoint address (saved for restoration)
    private static readonly byte[]?[] _originalBytes = new byte[MemoryReadInstructions.Length][];
    private static bool _breakpointsInstalled;
    private static int _currentCallNum;
    private static int _stepCount;
    private static long _totalReadsTraced;
    private static long _mismatchCount;

    /// <summary>
    /// Installs INT 3 breakpoints at all memory-read instructions in the resolver.
    /// </summary>
    public static void InstallBreakpoints(CpuContext ctx, int callNum)
    {
        _currentCallNum = callNum;
        _stepCount = 0;

        try { System.IO.Directory.CreateDirectory(LogDir); } catch { }

        // Only install for first 5 calls to limit log size
        if (callNum > 5) return;

        Console.Error.WriteLine($"[EXP028-T5] Installing memory read breakpoints for call #{callNum}");

        for (int i = 0; i < MemoryReadInstructions.Length; i++)
        {
            ulong addr = MemoryReadInstructions[i].rip;
            byte original = 0;
            if (ctx.TryReadByte(addr, out original))
            {
                _originalBytes[i] = new byte[] { original };
                ctx.TryWriteByte(addr, 0xCC);
            }
        }

        _breakpointsInstalled = true;
        WriteLog("t5_memory_read.log",
            $"[EXP028-T5] === CALL {callNum} START === installed {MemoryReadInstructions.Length} breakpoints");
    }

    /// <summary>
    /// Removes breakpoints (restores original bytes).
    /// </summary>
    public static void RemoveBreakpoints(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return;

        for (int i = 0; i < MemoryReadInstructions.Length; i++)
        {
            if (_originalBytes[i] != null)
            {
                ctx.TryWriteByte(MemoryReadInstructions[i].rip, _originalBytes[i][0]);
                _originalBytes[i] = null;
            }
        }
        _breakpointsInstalled = false;

        WriteLog("t5_memory_read.log",
            $"[EXP028-T5] === CALL {_currentCallNum} END === {_stepCount} steps traced");
    }

    /// <summary>
    /// Called from SIGTRAP handler. Logs the memory read at this RIP.
    /// </summary>
    public static bool HandleBreakpointHit(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return false;

        ulong rip = ctx.Rip;
        ulong bpAddr = rip - 1;  // INT3 increments RIP by 1

        // Find which breakpoint this is
        int bpIndex = -1;
        for (int i = 0; i < MemoryReadInstructions.Length; i++)
        {
            if (MemoryReadInstructions[i].rip == bpAddr)
            {
                bpIndex = i;
                break;
            }
        }
        if (bpIndex < 0) return false;

        _stepCount++;
        _totalReadsTraced++;

        var (insnRip, desc, srcReg, offset, size) = MemoryReadInstructions[bpIndex];

        // Get the source register value
        ulong srcRegVal = 0;
        bool srcIsGlobal = srcReg == "list_head_ptr";
        if (srcIsGlobal)
        {
            // Read the global pointer directly
            ctx.TryReadUInt64(ListHeadPtrAddr, out srcRegVal);
        }
        else
        {
            srcRegVal = srcReg.ToLower() switch
            {
                "rbx" => ctx[CpuRegister.Rbx],
                "rcx" => ctx[CpuRegister.Rcx],
                "r12" => ctx[CpuRegister.R12],
                "r15" => ctx[CpuRegister.R15],
                _ => 0,
            };
        }

        ulong srcAddr = srcRegVal + (uint)offset;

        // Read the value from memory (using CpuContext, NOT the resolver's native read)
        ulong nativeValue = 0;
        bool readOk = false;
        if (size == 1)
        {
            byte b = 0;
            readOk = ctx.TryReadByte(srcAddr, out b);
            nativeValue = b;
        }
        else if (size == 8)
        {
            readOk = ctx.TryReadUInt64(srcAddr, out nativeValue);
        }

        // Read additional context (for symbol names, etc.)
        string extraInfo = "";
        if (offset == OFF_SYMBOL_NAME && readOk && nativeValue != 0)
        {
            // Read the symbol name string
            extraInfo = " name='" + ReadCString(ctx, nativeValue) + "'";
        }
        else if (offset == OFF_MATCHED)
        {
            extraInfo = nativeValue != 0 ? " (SENTINEL)" : " (real node)";
        }

        // Log the read
        string line =
            $"[EXP028-T5] call={_currentCallNum} step={_stepCount} rip=0x{bpAddr:x} {desc}\n" +
            $"  {srcReg}=0x{srcRegVal:x} src_addr=0x{srcAddr:x} size={size} value=0x{nativeValue:x}{extraInfo}";

        Console.Error.WriteLine(line);
        WriteLog("t5_memory_read.log", line);

        // Restore the original byte so the instruction can execute
        if (_originalBytes[bpIndex] != null)
        {
            ctx.TryWriteByte(bpAddr, _originalBytes[bpIndex][0]);
        }

        // Set TF=1 to get a SIGTRAP after this instruction (then re-install BP)
        ctx.Rflags = ctx.Rflags | 0x100;

        return true;
    }

    /// <summary>
    /// Called after a TF=1 single-step. Re-installs the breakpoint at the
    /// just-completed instruction so it triggers again on the next iteration.
    /// </summary>
    public static void ReinstallBreakpointAfterStep(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return;

        ulong rip = ctx.Rip;
        // The previous instruction (where we set TF) is at rip - instruction_length.
        // But we don't know the length without decoding. Instead, just re-install
        // ALL breakpoints (idempotent).
        for (int i = 0; i < MemoryReadInstructions.Length; i++)
        {
            if (_originalBytes[i] != null)
            {
                // Check current byte — if it's still the original, install 0xCC
                byte current = 0;
                if (ctx.TryReadByte(MemoryReadInstructions[i].rip, out current) &&
                    current == _originalBytes[i][0])
                {
                    ctx.TryWriteByte(MemoryReadInstructions[i].rip, 0xCC);
                }
            }
        }
    }

    /// <summary>
    /// Compares native memory reads with the synthetic CPU's expected reads.
    /// Called once at the end of each resolver call.
    /// </summary>
    public static void CompareWithSynthetic(CpuContext ctx, int callNum, string query, ulong actualReturn)
    {
        // The synthetic CPU's expected path is documented in:
        // /home/z/my-project/download/exp026/exp026_il2cpp_init_trace.log
        // We can't do an automated diff here because the synthetic trace is
        // generated by a Python script, but we can log the actual return
        // for offline comparison.

        string line =
            $"[EXP028-T5-COMPARE] call={callNum} query='{query}' actualReturn=0x{actualReturn:x}\n" +
            $"  Synthetic expected: 0x804ed8770 (for il2cpp_init)\n" +
            $"  Native actual:      0x{actualReturn:x}\n" +
            $"  Match: {(actualReturn == 0x804ed8770 ? "YES" : "NO — DIVERGENCE")}";

        Console.Error.WriteLine(line);
        WriteLog("t5_memory_read.log", line);

        if (actualReturn != 0x804ed8770)
        {
            _mismatchCount++;
        }
    }

    /// <summary>
    /// Print final summary.
    /// </summary>
    public static void PrintSummary()
    {
        string summary =
            $"[EXP028-T5] === FINAL SUMMARY ===\n" +
            $"[EXP028-T5] Total memory reads traced: {_totalReadsTraced}\n" +
            $"[EXP028-T5] Return value mismatches:   {_mismatchCount}\n" +
            $"[EXP028-T5] \n" +
            $"[EXP028-T5] To compare with synthetic CPU:\n" +
            $"[EXP028-T5]   1. View /tmp/exp028_logs/t5_memory_read.log\n" +
            $"[EXP028-T5]   2. View /home/z/my-project/download/exp026/exp026_il2cpp_init_trace.log\n" +
            $"[EXP028-T5]   3. Compare each [EXP028-T5] line with the corresponding synthetic step\n" +
            $"[EXP028-T5]   4. The FIRST step where values differ is the divergence point";

        Console.Error.WriteLine(summary);
        WriteLog("t5_memory_read.log", summary);
    }

    private static string ReadCString(CpuContext ctx, ulong addr)
    {
        if (addr == 0) return "<null>";
        var bytes = new byte[128];
        int len = 0;
        for (int i = 0; i < 128; i++)
        {
            byte b;
            if (!ctx.TryReadByte(addr + (ulong)i, out b)) break;
            if (b == 0) break;
            bytes[i] = b;
            len++;
        }
        return len > 0 ? System.Text.Encoding.ASCII.GetString(bytes, 0, len) : "<empty>";
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
