# EXP-028 — Patch Instructions for SharpEmu Integration

## POLICY (per user correction)

✅ No functional changes to SharpEmu
✅ No fix
✅ Only temporary instrumentation
✅ Debug patch ≠ Code fix

## Files to Add

1. **`src/SharpEmu.Libs/Kernel/_Exp028T12T13BoundaryTrace.cs`** — T12/T13 boundary trace
2. **`src/SharpEmu.Libs/Kernel/_Exp028MemoryReadTracer.cs`** — T5 memory read trace (NEW)
3. **`src/SharpEmu.Libs/Kernel/_Exp028BranchTracer.cs`** — T6 branch trace (NEW)
4. **`src/SharpEmu.Libs/Kernel/_Exp027ResolverTracer.cs`** — T1/T2/T3 per-instruction trace (from EXP-027, used at Step 4)

## Integration Order

Apply patches in this order. After each patch, run the Golden Test (Dreaming Sarah) to confirm no behavior change.

### Step 1: T12/T13 Boundary Trace (EASIEST — no breakpoints, just logging)

In `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs`,
function `DispatchIl2CppApiLookupSymbol` (around line 2384):

**Find:**
```csharp
                var scheduler = GuestThreadExecution.Scheduler;
                if (scheduler != null)
                {
                        try
                        {
                                scheduler.TryCallGuestFunction(
                                        cpuContext,
                                        RealResolverAddress,
                                        symbolNameAddress,
                                        0, 0, 0, 0,
                                        "r8mvOaWdi28_resolver",
                                        out var returnValue,
                                        out var error);

                                // Log exit
                                if (returnValue == 0)
                                {
                                        Interlocked.Increment(ref _resolverReturnZero);
                                        Console.Error.WriteLine(
                                                $"[RESOLVER-TRACE] Exit  #{callNum}: RAX=0x{returnValue:X16} (NULL) error='{error}'");
                                }
                                else
                                { ... }

                                cpuContext[CpuRegister.Rax] = (ulong)returnValue;
                                return OrbisGen2Result.ORBIS_GEN2_OK;
                        }
                        catch (Exception ex) { ... }
                }
```

**Replace with:**
```csharp
                var scheduler = GuestThreadExecution.Scheduler;
                if (scheduler != null)
                {
                        try
                        {
                                // === EXP-028 Step 1: T12/T13 boundary trace (DIAGNOSTIC ONLY) ===
                                SharpEmu.Libs.Kernel.Exp028T12T13BoundaryTrace.LogPreCall(
                                        cpuContext, callNum, symbolName, RealResolverAddress, symbolNameAddress);

                                scheduler.TryCallGuestFunction(
                                        cpuContext,
                                        RealResolverAddress,
                                        symbolNameAddress,
                                        0, 0, 0, 0,
                                        "r8mvOaWdi28_resolver",
                                        out var returnValue,
                                        out var error);

                                // === EXP-028 Step 1: T12/T13 post-call log + return corruption check ===
                                SharpEmu.Libs.Kernel.Exp028T12T13BoundaryTrace.LogPostCall(
                                        cpuContext, callNum, symbolName, returnValue, error);

                                // Log exit (existing code, unchanged)
                                if (returnValue == 0)
                                {
                                        Interlocked.Increment(ref _resolverReturnZero);
                                        Console.Error.WriteLine(
                                                $"[RESOLVER-TRACE] Exit  #{callNum}: RAX=0x{returnValue:X16} (NULL) error='{error}'");
                                }
                                else
                                { ... }

                                cpuContext[CpuRegister.Rax] = (ulong)returnValue;
                                return OrbisGen2Result.ORBIS_GEN2_OK;
                        }
                        catch (Exception ex) { ... }
                }
```

**Build, run Yatzi, collect logs.** Then run Golden Test (Dreaming Sarah) — must still boot.

### Step 2: T5 Memory Read Trace (requires breakpoint infrastructure)

This is more invasive — it installs INT 3 breakpoints at memory-read instructions. You need to:

1. Add the `_Exp028MemoryReadTracer.cs` file to `src/SharpEmu.Libs/Kernel/`

2. In `DispatchIl2CppApiLookupSymbol`, BEFORE the `scheduler.TryCallGuestFunction` call:
```csharp
                                // === EXP-028 Step 2: T5 memory read trace (DIAGNOSTIC ONLY) ===
                                if (callNum <= 5)
                                {
                                        SharpEmu.Libs.Kernel.Exp028MemoryReadTracer.InstallBreakpoints(cpuContext, (int)callNum);
                                }
```

3. AFTER the `scheduler.TryCallGuestFunction` call (and after T12/T13 LogPostCall):
```csharp
                                // === EXP-028 Step 2: remove T5 breakpoints + compare ===
                                SharpEmu.Libs.Kernel.Exp028MemoryReadTracer.RemoveBreakpoints(cpuContext);
                                SharpEmu.Libs.Kernel.Exp028MemoryReadTracer.CompareWithSynthetic(
                                        cpuContext, (int)callNum, symbolName, returnValue);
```

4. In `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Exceptions.cs` (or `DirectExecutionBackend.PosixSignals.cs`), in the SIGTRAP handler:
```csharp
                        // === EXP-028 Step 2: T5 breakpoint handler ===
                        if (SharpEmu.Libs.Kernel.Exp028MemoryReadTracer.HandleBreakpointHit(cpuContext))
                        {
                                // Breakpoint handled — single-step and re-install
                                // (the handler set TF=1, so we'll get another SIGTRAP after this instruction)
                                return;  // or appropriate resume logic
                        }
```

5. After the TF=1 single-step SIGTRAP (RIP advanced by 1 instruction), call:
```csharp
                        // === EXP-028 Step 2: re-install breakpoints after single-step ===
                        SharpEmu.Libs.Kernel.Exp028MemoryReadTracer.ReinstallBreakpointAfterStep(cpuContext);
```

**Build, run Yatzi, collect logs.** Then run Golden Test — must still boot.

### Step 3: T6 Branch Trace (same infrastructure as T5)

1. Add the `_Exp028BranchTracer.cs` file to `src/SharpEmu.Libs/Kernel/`

2. Same integration pattern as T5, but call `Exp028BranchTracer` instead of `Exp028MemoryReadTracer`.

3. The SIGTRAP handler should call BOTH tracers (or use a single dispatcher).

### Step 4: T1/T2/T3 Per-Instruction INT3 (from EXP-027)

Only do this if T5 + T6 don't pinpoint the divergence. Use the existing `_Exp027ResolverTracer.cs` file from `/home/z/my-project/download/exp027/`.

## Output Files

After running with all patches, you'll find these logs in `/tmp/exp028_logs/`:

| File | Test | Contents |
|------|------|----------|
| `t12_t13_boundary.log` | T12/T13 | Pre/post call register state + return corruption check |
| `t5_memory_read.log` | T5 | Every memory read by the resolver (RIP, src_addr, value) |
| `t6_branch_trace.log` | T6 | Every branch decision (RIP, RFLAGS, TAKEN/NOT_TAKEN) |

## Golden Test (Dreaming Sarah) — REGRESSION CHECK

**MUST PASS after every patch.**

The instrumentation patches are DIAGNOSTIC ONLY. They must NOT change any
observable behavior. To verify:

1. Apply the patch (e.g., T12/T13 boundary trace)
2. Build SharpEmu: `dotnet build SharpEmu.slnx -c Release`
3. Run Dreaming Sarah (a game that boots correctly without the patch):
   ```bash
   ./SharpEmu.bin /path/to/dreaming_sarah/eboot.bin 2>&1 | tee /tmp/ds_run.log
   ```
4. Verify:
   - Dreaming Sarah still boots (no crash)
   - First frame renders
   - No new errors in the log
   - The `[EXP028-T12/T13]` log lines appear (proving the patch is active)
5. Compare frame rate / behavior to baseline (no patch) — should be identical
6. If Dreaming Sarah fails to boot or crashes → the patch has a bug, fix it before continuing

**Only after Golden Test passes**, run Yatzi with the patch and collect logs.

## Analysis Workflow

After collecting logs from Yatzi:

```bash
# 1. Run the analyzer (handles all trace formats)
python3 /home/z/my-project/scripts/exp028/analyze_exp028_traces.py

# 2. The analyzer will produce:
#    - /home/z/my-project/download/exp028/EXP028_FIRST_DIVERGENCE_REPORT.md
#      (auto-populated with the first divergent instruction)
#    - /home/z/my-project/download/exp028/exp028_summary.json
#      (machine-readable summary)
```

## Expected Findings per Step

### After Step 1 (T12/T13):
- If Case A (bad input): bug is in TryCallGuestFunction register setup → investigate `DirectExecutionBackend.cs:3459-3477` (context initialization)
- If Case B (return corruption): bug is in return propagation → investigate how `TryCallGuestFunction` reads RAX back from guest context
- If Case C (genuine zero): proceed to Step 2 (T5 memory read trace)

### After Step 2 (T5):
- If native reads differ from synthetic: bug is in memory mapping or guest memory access → investigate `VirtualMemory` and `TryReadByte`/`TryReadUInt64` paths
- If native reads match synthetic: proceed to Step 3 (T6 branch trace)

### After Step 3 (T6):
- If native branch decisions differ from synthetic: bug is in flag computation or preservation → investigate `lea` (should not modify flags per Intel SDM) or `test`/`cmp` flag output
- If native branch decisions match synthetic but resolver still returns 0: investigate the final `mov rax, [r12+0x28]` and return path

### After Step 4 (T1/T2/T3):
- This is the most detailed trace — should pinpoint the exact divergent instruction
- Compare each step with the synthetic CPU's trace at `/home/z/my-project/download/exp026/exp026_il2cpp_init_trace.log`

## Rollback

To remove all EXP-028 instrumentation:
1. Delete the `_Exp028*.cs` files from `src/SharpEmu.Libs/Kernel/`
2. Revert the changes to `DirectExecutionBackend.Imports.cs` and `DirectExecutionBackend.Exceptions.cs`
3. Build and verify with Golden Test (Dreaming Sarah)
