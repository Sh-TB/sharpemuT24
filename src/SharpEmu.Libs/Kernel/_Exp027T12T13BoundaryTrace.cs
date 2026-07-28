// EXP-027 T12/T13: DirectExecutionBackend Before/After Register Dump
//
// This is a SIMPLER instrumentation than T2/T3/T6 — it just logs the registers
// before and after TryCallGuestFunction, to detect return-value corruption.
//
// T12: Call chain trace — log RAX at each boundary:
//   - Before TryCallGuestFunction (caller's RAX, should be undefined)
//   - After TryCallGuestFunction returns (the resolver's RAX)
//   - After cpuContext[Rax] = returnValue (what the wrapper sees)
//
// T13: Return corruption test — if resolver returns 0x804ed8770 but wrapper
// sees RAX=0, the bug is in return propagation between guest and host.
//
// INSTALL:
//   In src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs,
//   function DispatchIl2CppApiLookupSymbol, around line 2384:
//
//   BEFORE:
//     scheduler.TryCallGuestFunction(
//         cpuContext,
//         RealResolverAddress,
//         symbolNameAddress,  // arg0: RDI = symbol name
//         0, 0, 0, 0,
//         "r8mvOaWdi28_resolver",
//         out var returnValue,
//         out var error);
//
//   AFTER (add these lines around the TryCallGuestFunction call):
//
//     // === EXP-027 T12: Before TryCallGuestFunction ===
//     ulong preRax = cpuContext[CpuRegister.Rax];
//     ulong preRdi = cpuContext[CpuRegister.Rdi];
//     ulong preRsp = cpuContext[CpuRegister.Rsp];
//     Console.Error.WriteLine(
//         $"[EXP027-T12] PRE  call={callNum} query='{symbolName}' " +
//         $"entry=0x{RealResolverAddress:x} RDI=0x{preRdi:x} RAX=0x{preRax:x} RSP=0x{preRsp:x}");
//
//     scheduler.TryCallGuestFunction(...);  // existing call
//
//     // === EXP-027 T12/T13: After TryCallGuestFunction ===
//     ulong postRax = cpuContext[CpuRegister.Rax];
//     Console.Error.WriteLine(
//         $"[EXP027-T12] POST call={callNum} query='{symbolName}' " +
//         $"returnValue=0x{returnValue:x} cpuContext.Rax=0x{postRax:x} error='{error}'");
//
//     // T13: Return corruption detection
//     if (returnValue != 0 && postRax != returnValue)
//     {
//         Console.Error.WriteLine(
//             $"[EXP027-T13] *** RETURN CORRUPTION *** call={callNum} " +
//             $"resolver returned 0x{returnValue:x} but RAX in context = 0x{postRax:x}");
//     }
//     if (returnValue == 0 && postRax == 0)
//     {
//         Console.Error.WriteLine(
//             $"[EXP027-T13] Resolver genuinely returned 0 (no corruption detected)");
//     }
//
// See _Exp027_Patch_Instructions.cs for the full diff.

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

/// <summary>
/// T12/T13: DirectExecutionBackend boundary tracing.
/// Pure logging — no behavior change.
/// </summary>
public static class Exp027T12T13BoundaryTrace
{
    private static long _callCount;
    private static long _returnCorruptionCount;
    private static long _resolverReturnedZero;
    private static long _resolverReturnedNonZero;

    /// <summary>
    /// Called BEFORE TryCallGuestFunction in DispatchIl2CppApiLookupSymbol.
    /// Logs the pre-call register state.
    /// </summary>
    public static void LogPreCall(
        CpuContext ctx,
        long callNum,
        string query,
        ulong entryPoint,
        ulong symbolNameAddress)
    {
        _callCount++;
        ulong rax = ctx[CpuRegister.Rax];
        ulong rdi = ctx[CpuRegister.Rdi];
        ulong rsi = ctx[CpuRegister.Rsi];
        ulong rdx = ctx[CpuRegister.Rdx];
        ulong rcx = ctx[CpuRegister.Rcx];
        ulong r8  = ctx[CpuRegister.R8];
        ulong r9  = ctx[CpuRegister.R9];
        ulong r12 = ctx[CpuRegister.R12];
        ulong r14 = ctx[CpuRegister.R14];
        ulong r15 = ctx[CpuRegister.R15];
        ulong rsp = ctx[CpuRegister.Rsp];
        ulong rbp = ctx[CpuRegister.Rbp];
        ulong rflags = ctx.Rflags;

        Console.Error.WriteLine(
            $"[EXP027-T12] === PRE-CALL #{callNum} ===");
        Console.Error.WriteLine(
            $"[EXP027-T12]   query='{query}' entry=0x{entryPoint:x} symAddr=0x{symbolNameAddress:x}");
        Console.Error.WriteLine(
            $"[EXP027-T12]   RAX=0x{rax:x} RBX=0x{ctx[CpuRegister.Rbx]:x} RCX=0x{rcx:x} RDX=0x{rdx:x}");
        Console.Error.WriteLine(
            $"[EXP027-T12]   RSI=0x{rsi:x} RDI=0x{rdi:x} R8=0x{r8:x} R9=0x{r9:x}");
        Console.Error.WriteLine(
            $"[EXP027-T12]   R12=0x{r12:x} R14=0x{r14:x} R15=0x{r15:x} RBP=0x{rbp:x} RSP=0x{rsp:x}");
        Console.Error.WriteLine(
            $"[EXP027-T12]   RFLAGS=0x{rflags:x} (SF={(rflags>>7)&1} ZF={(rflags>>6)&1} CF={(rflags>>0)&1} OF={(rflags>>11)&1})");
    }

    /// <summary>
    /// Called AFTER TryCallGuestFunction returns.
    /// Logs the post-call register state and detects return-value corruption.
    /// </summary>
    public static void LogPostCall(
        CpuContext ctx,
        long callNum,
        string query,
        ulong returnValue,
        string? error)
    {
        ulong postRax = ctx[CpuRegister.Rax];
        ulong postRdi = ctx[CpuRegister.Rdi];
        ulong postRbx = ctx[CpuRegister.Rbx];
        ulong postR12 = ctx[CpuRegister.R12];
        ulong postR14 = ctx[CpuRegister.R14];
        ulong postR15 = ctx[CpuRegister.R15];
        ulong postRflags = ctx.Rflags;

        Console.Error.WriteLine(
            $"[EXP027-T12] === POST-CALL #{callNum} ===");
        Console.Error.WriteLine(
            $"[EXP027-T12]   returnValue=0x{returnValue:x} error='{error}'");
        Console.Error.WriteLine(
            $"[EXP027-T12]   RAX(ctx)=0x{postRax:x} RBX=0x{postRbx:x} R12=0x{postR12:x} R14=0x{postR14:x} R15=0x{postR15:x}");
        Console.Error.WriteLine(
            $"[EXP027-T12]   RFLAGS=0x{postRflags:x} (SF={(postRflags>>7)&1} ZF={(postRflags>>6)&1})");

        // T13: Return corruption detection
        if (returnValue != 0)
        {
            _resolverReturnedNonZero++;
            if (postRax != returnValue)
            {
                _returnCorruptionCount++;
                Console.Error.WriteLine(
                    $"[EXP027-T13] *** RETURN CORRUPTION *** call #{callNum}: " +
                    $"resolver returned 0x{returnValue:x} but RAX in CpuContext = 0x{postRax:x}");
                Console.Error.WriteLine(
                    $"[EXP027-T13]   → Bug is in return value propagation between guest and host");
            }
            else
            {
                Console.Error.WriteLine(
                    $"[EXP027-T13] Resolver returned non-zero, RAX correctly propagated");
            }
        }
        else
        {
            _resolverReturnedZero++;
            Console.Error.WriteLine(
                $"[EXP027-T13] Resolver returned 0 (genuinely — no corruption detected)");
        }
    }

    /// <summary>
    /// Print final statistics.
    /// </summary>
    public static void PrintSummary()
    {
        Console.Error.WriteLine($"[EXP027-T12/T13] === FINAL SUMMARY ===");
        Console.Error.WriteLine($"[EXP027-T12/T13] Total resolver calls:       {_callCount}");
        Console.Error.WriteLine($"[EXP027-T12/T13] Resolver returned 0:         {_resolverReturnedZero}");
        Console.Error.WriteLine($"[EXP027-T12/T13] Resolver returned non-zero:  {_resolverReturnedNonZero}");
        Console.Error.WriteLine($"[EXP027-T12/T13] Return corruption detected:  {_returnCorruptionCount}");

        if (_resolverReturnedZero == _callCount && _returnCorruptionCount == 0)
        {
            Console.Error.WriteLine($"[EXP027-T12/T13] CONCLUSION:");
            Console.Error.WriteLine($"[EXP027-T12/T13]   Resolver GENUINELY returns 0 for all calls.");
            Console.Error.WriteLine($"[EXP027-T12/T13]   No return-value corruption.");
            Console.Error.WriteLine($"[EXP027-T12/T13]   → Bug is INSIDE the resolver's native execution,");
            Console.Error.WriteLine($"[EXP027-T12/T13]     not in return propagation.");
            Console.Error.WriteLine($"[EXP027-T12/T13]   → Next step: per-instruction trace (T2/T3/T6)");
            Console.Error.WriteLine($"[EXP027-T12/T13]     to find the diverging instruction.");
        }
    }
}
