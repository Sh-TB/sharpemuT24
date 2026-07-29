// EXP-027 T2/T3/T6/T12/T13: Per-Instruction Resolver Tracer for SharpEmu
//
// DIAGNOSTIC ONLY — No functional changes to SharpEmu. No fix. Only
// temporary instrumentation. Debug patch ≠ Code fix.
//
// This file adds per-instruction tracing for the resolver execution at
// 0x804ED9B90. It works by patching software breakpoints (INT 3 = 0xCC)
// at every instruction in the resolver's critical path.
//
// INSTALL:
//   1. Copy this file to: src/SharpEmu.Libs/Kernel/_Exp027ResolverTracer.cs
//   2. Add to DirectExecutionBackend.Imports.cs::DispatchIl2CppApiLookupSymbol:
//      - Before TryCallGuestFunction: Exp027ResolverTracer.InstallBreakpoints(cpuContext, query, callNum);
//      - After  TryCallGuestFunction: Exp027ResolverTracer.RemoveBreakpoints(cpuContext);
//                                    Exp027ResolverTracer.RecordActual(callNum, query, predicted, actual);
//   3. Add SIGTRAP handler in DirectExecutionBackend.Exceptions.cs:
//      On SIGTRAP, call Exp027ResolverTracer.HandleBreakpointHit(cpuContext);
//   4. See _Exp027_Patch_Instructions.cs for exact diff.
//
// OUTPUT:
//   test1_rflags.log    — RFLAGS dump after every instruction (T2)
//   test2_registers.log — Register timeline (T6)
//   test3_strcmp.log    — strcmp input/output trace (T8/T9)
//   test4_full_trace.log — Combined full per-instruction trace (T1)
//
// BREAKPOINT ADDRESSES (every instruction in the resolver):
//   0x804ED9B90: push rbp
//   0x804ED9B91: mov rbp, rsp
//   0x804ED9B94: push r15; push r14; push r12; push rbx (4 bytes)
//   0x804ED9B9B: mov r15, [rip+0x3c79b66]
//   0x804ED9BA2: mov rbx, [r15+8]
//   0x804ED9BA6: cmp byte [rbx+0x19], 0          ← T2: RFLAGS after this
//   0x804ED9BAA: je 0x804ED9BB7                  ← T2: RFLAGS before this
//   0x804ED9BAC: xor eax, eax
//   0x804ED9BAE: pop rbx; pop r12; pop r14; pop r15; pop rbp (5 bytes)
//   0x804ED9BB6: ret
//   0x804ED9BB7: mov r14, rdi
//   0x804ED9BBA: mov r12, r15
//   0x804ED9BBD: nop
//   0x804ED9BC0: mov rdi, [rbx+0x20]             (loop_start)
//   0x804ED9BC4: mov rsi, r14
//   0x804ED9BC7: call 0x804fc2d40                ← strcmp
//   0x804ED9BCC: test eax, eax                   ← T2/T3: SF set here
//   0x804ED9BCE: lea rcx, [rbx+0x10]             ← T3: SF must persist through this
//   0x804ED9BD2: cmovns rcx, rbx                 ← T3: SF consumed here
//   0x804ED9BD6: cmovns r12, rbx                 ← T3: SF consumed AGAIN here (same flag!)
//   0x804ED9BDA: mov rbx, [rcx]
//   0x804ED9BDD: cmp byte [rbx+0x19], 0
//   0x804ED9BE1: je 0x804ED9BC0
//   0x804ED9BE3: cmp r12, r15
//   0x804ED9BE6: je 0x804ED9BAC
//   0x804ED9BE8: mov rsi, [r12+0x20]
//   0x804ED9BED: mov rdi, r14
//   0x804ED9BF0: call 0x804fc2d40                ← strcmp (final)
//   0x804ED9BF5: test eax, eax
//   0x804ED9BF7: js 0x804ED9BAC
//   0x804ED9BF9: mov rax, [r12+0x28]
//   (ret follows)

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

public static class Exp027ResolverTracer
{
    // Resolver instruction addresses (every instruction)
    private static readonly ulong[] BreakpointAddresses = new ulong[]
    {
        0x804ED9B90, 0x804ED9B91, 0x804ED9B94, 0x804ED9B9B,
        0x804ED9BA2, 0x804ED9BA6, 0x804ED9BAA, 0x804ED9BAC,
        0x804ED9BAE, 0x804ED9BB6, 0x804ED9BB7, 0x804ED9BBA,
        0x804ED9BBD, 0x804ED9BC0, 0x804ED9BC4, 0x804ED9BC7,
        0x804ED9BCC, 0x804ED9BCE, 0x804ED9BD2, 0x804ED9BD6,
        0x804ED9BDA, 0x804ED9BDD, 0x804ED9BE1, 0x804ED9BE3,
        0x804ED9BE6, 0x804ED9BE8, 0x804ED9BED, 0x804ED9BF0,
        0x804ED9BF5, 0x804ED9BF7, 0x804ED9BF9,
    };

    // Original bytes at each breakpoint address (saved so we can restore)
    private static readonly byte[]?[] _originalBytes = new byte[BreakpointAddresses.Length][];

    private static bool _breakpointsInstalled;
    private static string _currentQuery = "";
    private static long _currentCallNum;
    private static int _stepCount;
    private static string _logDir = "/tmp/exp027_logs";

    // Statistics
    private static long _totalResolverCalls;
    private static long _totalStepsTraced;
    private static long _divergenceCount;
    private static ulong _lastRax;
    private static ulong _lastRflags;

    /// <summary>
    /// Installs INT 3 (0xCC) software breakpoints at every instruction in the resolver.
    /// Original bytes are saved for restoration.
    /// </summary>
    public static void InstallBreakpoints(CpuContext ctx, string query, long callNum)
    {
        _currentQuery = query;
        _currentCallNum = callNum;
        _stepCount = 0;
        _totalResolverCalls++;

        try
        {
            System.IO.Directory.CreateDirectory(_logDir);
        }
        catch { }

        // Only install breakpoints for the FIRST few calls (to avoid log explosion)
        if (callNum > 3)
        {
            return;
        }

        Console.Error.WriteLine($"[EXP027] Installing breakpoints for call #{callNum} query='{query}'");

        for (int i = 0; i < BreakpointAddresses.Length; i++)
        {
            ulong addr = BreakpointAddresses[i];
            byte original = 0;
            if (ctx.TryReadByte(addr, out original))
            {
                _originalBytes[i] = new byte[] { original };
                // Write 0xCC (INT 3)
                if (!ctx.Memory.TryWrite(addr, new byte[] { 0xCC }))
                {
                    Console.Error.WriteLine($"[EXP027]   Failed to install BP at 0x{addr:x}");
                }
            }
            else
            {
                Console.Error.WriteLine($"[EXP027]   Failed to read original byte at 0x{addr:x}");
            }
        }

        _breakpointsInstalled = true;
        Console.Error.WriteLine($"[EXP027]   Installed {BreakpointAddresses.Length} breakpoints");
    }

    /// <summary>
    /// Restores original bytes (removes breakpoints).
    /// </summary>
    public static void RemoveBreakpoints(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return;

        for (int i = 0; i < BreakpointAddresses.Length; i++)
        {
            if (_originalBytes[i] != null)
            {
                ctx.Memory.TryWrite(BreakpointAddresses[i], new byte[] { _originalBytes[i][0] });
                _originalBytes[i] = null;
            }
        }
        _breakpointsInstalled = false;
    }

    /// <summary>
    /// Called from SIGTRAP handler when a breakpoint is hit.
    /// Logs RIP, registers, and RFLAGS.
    /// </summary>
    public static bool HandleBreakpointHit(CpuContext ctx)
    {
        if (!_breakpointsInstalled) return false;

        ulong rip = ctx.Rip;
        // After INT 3, RIP points to the NEXT instruction. Decrement by 1 to get
        // the address of the INT 3 itself.
        ulong bpAddr = rip - 1;

        // Find which breakpoint this is
        int bpIndex = -1;
        for (int i = 0; i < BreakpointAddresses.Length; i++)
        {
            if (BreakpointAddresses[i] == bpAddr)
            {
                bpIndex = i;
                break;
            }
        }
        if (bpIndex < 0) return false;

        _stepCount++;
        _totalStepsTraced++;

        // Read all relevant registers
        ulong rax = ctx[CpuRegister.Rax];
        ulong rbx = ctx[CpuRegister.Rbx];
        ulong rcx = ctx[CpuRegister.Rcx];
        ulong rdx = ctx[CpuRegister.Rdx];
        ulong rsi = ctx[CpuRegister.Rsi];
        ulong rdi = ctx[CpuRegister.Rdi];
        ulong r12 = ctx[CpuRegister.R12];
        ulong r13 = ctx[CpuRegister.R13];
        ulong r14 = ctx[CpuRegister.R14];
        ulong r15 = ctx[CpuRegister.R15];
        ulong rbp = ctx[CpuRegister.Rbp];
        ulong rsp = ctx[CpuRegister.Rsp];
        ulong rflags = ctx.Rflags;

        // Decode RFLAGS bits
        bool cf = (rflags & 0x001) != 0;
        bool pf = (rflags & 0x004) != 0;
        bool af = (rflags & 0x010) != 0;
        bool zf = (rflags & 0x040) != 0;
        bool sf = (rflags & 0x080) != 0;
        bool of = (rflags & 0x800) != 0;
        bool df = (rflags & 0x400) != 0;
        bool tf = (rflags & 0x100) != 0;
        bool iff = (rflags & 0x200) != 0;

        // Log to multiple files for different tests
        string tag = $"call{_currentCallNum}_step{_stepCount:D3}_0x{bpAddr:x}";

        // T1: Full trace
        LogLine("test4_full_trace.log",
            $"[EXP027-T1] call={_currentCallNum} step={_stepCount} rip=0x{bpAddr:x} " +
            $"RAX=0x{rax:x} RBX=0x{rbx:x} RCX=0x{rcx:x} RDX=0x{rdx:x} " +
            $"RSI=0x{rsi:x} RDI=0x{rdi:x} R12=0x{r12:x} R13=0x{r13:x} " +
            $"R14=0x{r14:x} R15=0x{r15:x} RBP=0x{rbp:x} RSP=0x{rsp:x} " +
            $"RFLAGS=0x{rflags:x} (CF={cf} PF={pf} AF={af} ZF={zf} SF={sf} OF={of} DF={df} TF={tf} IF={iff})");

        // T2: RFLAGS only (focused)
        LogLine("test1_rflags.log",
            $"[EXP027-T2] call={_currentCallNum} step={_stepCount} rip=0x{bpAddr:x} " +
            $"RFLAGS=0x{rflags:x} CF={cf} PF={pf} AF={af} ZF={zf} SF={sf} OF={of} " +
            $"RAX=0x{rax:x} (eax={(int)(rax & 0xFFFFFFFF)})");

        // T3: SF preservation focus (only for the critical sequence)
        if (bpAddr == 0x804ED9BCC || bpAddr == 0x804ED9BCE ||
            bpAddr == 0x804ED9BD2 || bpAddr == 0x804ED9BD6)
        {
            LogLine("test3_sf_preservation.log",
                $"[EXP027-T3] call={_currentCallNum} rip=0x{bpAddr:x} " +
                $"SF={sf} ZF={zf} RAX=0x{rax:x} RBX=0x{rbx:x} RCX=0x{rcx:x} R12=0x{r12:x}");
        }

        // T6: Register timeline
        LogLine("test2_registers.log",
            $"[EXP027-T6] call={_currentCallNum} step={_stepCount} rip=0x{bpAddr:x} " +
            $"RBX=0x{rbx:x} RCX=0x{rcx:x} RDI=0x{rdi:x} RSI=0x{rsi:x} R12=0x{r12:x}");

        // T8/T9: strcmp input trace (when about to call strcmp)
        if (bpAddr == 0x804ED9BC7 || bpAddr == 0x804ED9BF0)
        {
            string arg1 = ReadCString(ctx, rdi);
            string arg2 = ReadCString(ctx, rsi);
            string direction = bpAddr == 0x804ED9BC7 ? "strcmp(NODE,QUERY)" : "strcmp(QUERY,CANDIDATE)";
            LogLine("test3_strcmp.log",
                $"[EXP027-T8] call={_currentCallNum} rip=0x{bpAddr:x} {direction} " +
                $"RDI=0x{rdi:x} ('{arg1}') RSI=0x{rsi:x} ('{arg2}')");
        }

        // Restore the original byte so we can re-execute the instruction
        if (_originalBytes[bpIndex] != null)
        {
            ctx.Memory.TryWrite(bpAddr, new byte[] { _originalBytes[bpIndex][0] });
        }

        // Set the Trap Flag (TF=1) so we get a SIGTRAP after the next instruction,
        // then we can re-install the breakpoint.
        ctx.Rflags = rflags | 0x100;  // set TF

        _lastRax = rax;
        _lastRflags = rflags;

        return true;
    }

    /// <summary>
    /// Called after the resolver returns. Compares predicted vs actual.
    /// </summary>
    public static void RecordActual(long callNum, string query, ulong predicted, ulong actual)
    {
        bool diverged = (predicted != 0) != (actual != 0);
        if (diverged) _divergenceCount++;

        LogLine("test4_full_trace.log",
            $"[EXP027-T1] === RESULT call={callNum} query='{query}' " +
            $"predicted=0x{predicted:x} actual=0x{actual:x} " +
            $"[{(diverged ? "DIVERGENCE!" : "match")}] ===");
    }

    /// <summary>
    /// Print final summary.
    /// </summary>
    public static void PrintSummary()
    {
        Console.Error.WriteLine($"[EXP027] === FINAL SUMMARY ===");
        Console.Error.WriteLine($"[EXP027] Total resolver calls:  {_totalResolverCalls}");
        Console.Error.WriteLine($"[EXP027] Total steps traced:   {_totalStepsTraced}");
        Console.Error.WriteLine($"[EXP027] Divergences:           {_divergenceCount}");
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

    private static void LogLine(string filename, string line)
    {
        try
        {
            string path = System.IO.Path.Combine(_logDir, filename);
            System.IO.File.AppendAllText(path, line + "\n");
        }
        catch { }
    }
}
