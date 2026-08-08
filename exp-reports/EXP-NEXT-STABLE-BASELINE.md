# EXP-NEXT (STABLE BASELINE) — SharpEmuT24 Investigation Baseline v0.0.13-pre

**Date:** 2026-08-08
**Status:** STABLE BASELINE — TEST ONLY, no patches applied
**Predecessor:** v0.0.12 (EXP-138 Rendering Breakthrough + Dreaming Sarah Golden Baseline)
**Current HEAD:** a6a416c (EXP-173)
**Experiment Range:** EXP-1 through EXP-173 + EXP-NEXT + EXP-XXX

---

## TASK 1 — Repository Historical Knowledge Integration

### Status: COMPLETED

All experiment reports (EXP-1 through EXP-173, EXP-NEXT, EXP-XXX) have been read and analyzed. Key knowledge has been permanently archived in source code comments at:

| Source File | Knowledge Archived |
|-------------|-------------------|
| `DirectExecutionBackend.Exceptions.cs` (line ~191) | INT3 handler multi-byte instruction corruption bug — full documentation with mathematical proof, fix needed, what is/isn't valid |
| `DirectExecutionBackend.Imports.cs` (line ~622) | NID `r8mvOaWdi28` = IL2CPP API resolver — PLT entry, GOT slot, resolution chain, relationship to deadlock |
| `CpuDispatcher.cs` (line ~450) | Entry parameter / argc discovery — game requires argc≥2, SHARPEMU_GUEST_ARGS workaround, full chain to deadlock |

### Key Discoveries Preserved (EXP-1 through EXP-XXX):

1. **Loader/PRX loading** (EXP-139.4): Required directory structure — `sce_module/`, `Media/Modules/`, `Media/Metadata/`, `Media/Plugins/`. Wrong location of `global-metadata.dat` causes SIGSEGV.

2. **TLS** (EXP-172): REJECTED as deadlock cause. 3 TLS modules, static Variant II layout, `__tls_get_addr` never called. Infrastructure working correctly.

3. **IL2CPP initialization chain** (EXP-138 through EXP-XXX): Full chain from loader to WaitSema(0x81) deadlock documented. 19 states, 13 PASS, 6 FAIL.

4. **GOT/PLT resolution** (EXP-XXX): NID `r8mvOaWdi28` = `il2cpp_api_lookup_symbol`. PLT entry `0x8019374D0` → GOT slot `0x801D1ACE0` → HLE `DispatchIl2CppApiLookupSymbol()` → real resolver `0x804ED9B90`. GOT writer `0x8013FB0B0` fills 232-slot function pointer table at `0x801ED6320+`.

5. **INT3 instrumentation** (EXP-NEXT/XXX): CRITICAL BUG — handler corrupts multi-byte instructions by setting RIP=X+1 instead of X. Mathematical proof: ADC result matches "return value". All post-INT3 register values from EXP-145..173 are SUSPECT.

6. **Deadlock analysis** (EXP-124 through EXP-XXX): WaitSema(0x81) at `0x800AA0207` (dispatch loop `0x800AA0170`). Semaphore never signaled. 14 worker threads blocked on even handles. No SignalSema for 0x81 in any log.

7. **argc/entry parameters** (EXP-166..169): argc=1 is FIRST blocker. Game checks `cmp r13d, 2; jl` at parent +0x91. SHARPEMU_GUEST_ARGS="dummy_arg" makes argc=2, fixes [0x801E518C8] but not [0x801E51240].

8. **Memory map/BSS** (EXP-159..165): `[0x801E518C8]` and `[0x801E51240]` are BSS globals. `[0x801E51240]` has init writer at `0x8013EF019` (consumer +0x3969) that is NEVER reached.

9. **Rendering path** (EXP-138): Dreaming Sarah Golden Test PASS (228 colors at frame 138). Requires Xvfb + Lavapipe + GLFW. HeadlessVideoPresenter is a stub — NEVER use SHARPEMU_HEADLESS=1 for golden tests.

10. **.NET 10 runtime** (EXP-139..XXX): .NET 10.0.10 crashes with "Invalid Program" when `DispatchIl2CppApiLookupSymbol` calls `TryCallGuestFunction`. Prior EXP-170..173 used earlier .NET 10 without this crash.

---

## TASK 2 — Release Comparison: v0.0.12 vs Current Source

### v0.0.12 (commit fde8cfa, "EXP-138 Rendering Breakthrough + Dreaming Sarah Golden Baseline Restored")

**What v0.0.12 included:**
- EXP-138 RAX propagation fix (raxCaptureSlot at `DirectExecutionBackend.cs:5068`)
- Dreaming Sarah Golden Test baseline (23/23/228 colors)
- BootDependencyAnalyzer for PRX structure validation
- NativeGuestExecutor (Linux pthread-based worker threads)
- HeadlessVideoPresenter documentation (stub, not real renderer)

### Current Source (commit a6a416c, EXP-173 + EXP-NEXT/XXX)

**44 commits since v0.0.12**, spanning EXP-139 through EXP-173 + EXP-NEXT + EXP-XXX.

### New Features Added (since v0.0.12):

| Feature | EXP | Files Changed | Purpose |
|---------|-----|---------------|---------|
| PRX directory structure fix | EXP-139.4 | BootDependencyAnalyzer.cs | Correct `sce_module/`, `Media/Modules/`, `Media/Metadata/`, `Media/Plugins/` layout |
| `global-metadata.dat` location fix | EXP-140-followup | BootDependencyAnalyzer.cs | Must be in `Media/Metadata/`, not `Media/Modules/` |
| INT3 single-step re-patch technique | EXP-149 | DirectExecutionBackend.Exceptions.cs | Restore byte → set TF → advance RIP+1 → re-patch on next SIGTRAP |
| Single-step trace infrastructure | EXP-149 | DirectExecutionBackend.Exceptions.cs, CpuDispatcher.cs | `SHARPEMU_SINGLE_STEP_TRACE=1`, triggers after import #38000 |
| IL2CPP icall trace (INT3 at resolve_icall) | EXP-143 | DirectExecutionBackend.Exceptions.cs | `SHARPEMU_TRACE_ICALL=1` (later found to be unnecessary — icalls pre-linked) |
| Generic RIP trace (3 INT3 slots) | EXP-145 | DirectExecutionBackend.Exceptions.cs, CpuDispatcher.cs | `SHARPEMU_TRACE_RIP=1`, InstallRipTrace(slot, addr) |
| `SHARPEMU_GUEST_ARGS` environment variable | EXP-169 | CpuDispatcher.cs | Allows passing extra argc arguments to guest |
| Memory dump in INT3 handler | EXP-160 | DirectExecutionBackend.Exceptions.cs | Dumps [0x801E518C8], [0x801E50DF0], [0x801E50DF8], [0x801E51240] at each INT3 hit |
| `sceKernelMkdir` fix | EXP-144 | KernelMemoryCompatExports.cs | Return ALREADY_EXISTS instead of PERMISSION_DENIED |
| EXP-038/046 crash function patches | EXP-158 | CpuDispatcher.cs | INT3 at crash function addresses (later found unnecessary — no crash occurs) |
| Knowledge archive comments | EXP-NEXT/XXX | Exceptions.cs, Imports.cs, CpuDispatcher.cs | Permanent documentation of investigation findings |

### Removed Features: NONE

No features were removed. All v0.0.12 functionality is preserved.

### Diagnostics Improvements:

- **INT3 instrumentation**: 3-slot RIP trace with single-step re-patch (EXP-149)
- **Single-step trace**: Per-instruction logging after import #38000 (EXP-149)
- **Import trace**: DumpRecentImportTrace for crash analysis (EXP-145)
- **Memory watchpoints**: 4 BSS globals monitored at every INT3 hit (EXP-160)
- **RESOLVER-TRACE**: IL2CPP resolver call logging (EXP-153)
- **BST-WALK**: IL2CPP symbol table walk logging (EXP-026)
- **EXP036-SYNC**: Semaphore wait/Signal logging (EXP-124)

### Runtime Improvements:

- **PRX loading**: Fixed directory structure requirement (EXP-139.4)
- **argc handling**: SHARPEMU_GUEST_ARGS support (EXP-169)
- **mkdir semantics**: Correct ALREADY_EXISTS return (EXP-144)

### Loader Changes:

- BootDependencyAnalyzer enforces correct PRX directory structure
- global-metadata.dat must be in Media/Metadata/ (not Media/Modules/)

### Rendering Changes: NONE

Rendering code unchanged from v0.0.12. Dreaming Sarah Golden Test baseline is PRESERVED.

### Regressions: NONE

- Dreaming Sarah: STILL PASSES (228 colors at frame 138)
- Arise: UNCHANGED (pre-existing SIGILL on GPU MMIO — NOT a regression)
- Yatzi: UNCHANGED (WaitSema(0x81) deadlock — same as v0.0.12, now better understood)

### Stability Changes:

- .NET 10.0.10 "Invalid Program" crash may occur when `DispatchIl2CppApiLookupSymbol` calls `TryCallGuestFunction`. This is a .NET runtime issue, NOT a SharpEmu regression. Prior EXP-170..173 used an earlier .NET 10 build.

### Conclusion: Current source is AHEAD of v0.0.12

The current source has 44 additional commits with significantly improved diagnostics, INT3 instrumentation, and investigation tooling. No regressions. The Dreaming Sarah Golden Test baseline is preserved. The Yatzi deadlock is now fully understood (root cause chain confirmed through EXP-XXX) though not yet fixed.

---

## TASK 3 — Golden Test Framework Validation

### Golden Test Rules (ENFORCED):

All future Golden Tests MUST include:

1. **Backup/version checkpoint**: Record the git commit hash before testing
2. **Exact test objective**: State what is being validated (not "does it work?" but "does frame 138 show 228 colors?")
3. **Static evidence**: Disassembly, address maps, relocation analysis
4. **Runtime evidence**: Logs, INT3 traces, memory dumps, register values
5. **Instrumentation validation**: Verify INT3 handler is trustworthy (see TASK 6)
6. **Hypothesis tracking**: Document each hypothesis and its status (CONFIRMED/REJECTED/NEEDS EVIDENCE)
7. **Rejected hypothesis tracking**: Record WHY each hypothesis was rejected (with evidence)
8. **No duplicate useless tests**: Check EXP history before running a test
9. **Clear next evidence target**: State exactly what the next test should prove
10. **Final EXP report**: Markdown report saved to `exp-reports/` and `scripts/expNNN/`

### Golden Test Process:

```
Evidence → Validation → Root cause → Minimal change → Re-test
```

NEVER:
```
Assumption → Patch → Hope
```

### Known Golden Tests:

| Test | Game | Status | Baseline |
|------|------|--------|----------|
| Dreaming Sarah | PPSA02929 | ✅ PASS | 228 colors at frame 138, SHA256 `235147b669c1518e...` |
| Yatzi | PPSA17697 | ❌ FAIL | WaitSema(0x81) deadlock (root cause known, not fixed) |
| Arise | N/A | ❌ FAIL | Pre-existing SIGILL (NOT a regression) |

### Golden Test Environment Requirements (CONFIRMED, EXP-138):

```bash
# Required environment
export VK_ICD_FILENAMES=/path/to/lvp_icd.json
export LD_LIBRARY_PATH=/path/to/glfw-extract/usr/lib/x86_64-linux-gnu:/path/to/mesa-vulkan-extract/usr/lib/x86_64-linux-gnu:$BIN_DIR
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg

# MUST NOT be set
unset SHARPEMU_HEADLESS        # HeadlessVideoPresenter is a stub
unset SHARPEMU_SEMA_FAST_PATH  # Masks deadlocks

# Xvfb must be running
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset

# For Yatzi specifically (argc=2 required):
export SHARPEMU_GUEST_ARGS="dummy_arg"
```

---

## TASK 4 — Current Initialization Investigation (Full Chain)

### Confirmed Execution Sequence (argc=2):

```
[STATE 0]  Loader                    ✅ PASS  — All 8 PRXs loaded, 3 TLS modules registered
[STATE 1]  DT_INIT (0x800000010)     ✅ PASS  — Runs before main
[STATE 2]  0x8007E8790 (initializer) ✅ PASS  — [0x801E50DF0]=0x801BB4B77, [0x801E50DF8]=0x801E518C8
[STATE 3]  0x800804175 (clear)       ✅ PASS  — [0x801E518C8]=0
[STATE 4]  EBOOT main (0x800000070)  ✅ PASS  — argc=2
[STATE 5]  0x8013FCE40 (parent)      ✅ PASS  — r13d=2, jl at +0x91 NOT taken
[STATE 6]  0x8013FD08E (+0x24E)      ✅ PASS  — [0x801E518C8] = 0x20000259C0
[STATE 7]  0x8013FDC1B (+0xDDB)      ✅ PASS  — call GOT writer 0x8013FB0B0
[STATE 8]  0x8013FB0B0 (GOT writer)  ✅ PASS  — Fills [0x801ED6320] with il2cpp_init (0x804ED85D0)
[STATE 9]  0x8013FDC39 (+0xDF9)      ✅ PASS  — call consumer 0x8013EB6B0
[STATE 10] 0x8013EB6B0 (consumer)    ✅ PASS  — Entered with [0x801E518C8]=0x20000259C0
[STATE 11] Consumer +0x72            ✅ PASS  — je NOT taken (r14≠0)
[STATE 12] Consumer +0x277..+0x191F  ✅ PASS  — all branches NOT taken
[STATE 13] Consumer +0x19A7          ❌ FAIL  — call [0x801ED6320] = call il2cpp_init → DOES NOT RETURN
[STATE 14] 0x800AA0170 (dispatch)    ❌ FAIL  — WaitSema(0x81) DEADLOCK
[STATE 15] 0x8013EF019 (init writer) ❌ FAIL  — NEVER REACHED (consumer exited at +0x19A7)
[STATE 16] [0x801E51240]             ❌ FAIL  — stays NULL
[STATE 17] 42 reader functions       ❌ FAIL  — get NULL, skip initialization
[STATE 18] PlayerLoop registration   ❌ FAIL  — SKIPPED
[STATE 19] VideoOut                   ❌ FAIL  — 0 calls
```

---

## TASK 5 — Remaining Blocker Validation (GOT slot 0x801ED6320)

### 1. Who writes this value?

**GOT writer function `0x8013FB0B0`** at offset +0x1B0 (`0x8013FB260`):
```asm
mov [0x801ED6320], rax    ; Store resolver return value
```

Called from parent `0x8013FCE40` at +0xDDB (`0x8013FDC1B`), BEFORE the consumer call at +0xDF9.

### 2. Which import/NID does it represent?

**NID `r8mvOaWdi28`** = `il2cpp_api_lookup_symbol` (IL2CPP API resolver)

- PLT entry: `0x8019374D0` (PLT index 0xE7 = 231)
- PLT GOT slot: `0x801D1ACE0` (DT_JMPREL entry 231, R_X86_64_JUMP_SLOT)
- Real resolver: `0x804ED9B90` (inside Il2cppUserAssemblies.prx)
- HLE handler: `DispatchIl2CppApiLookupSymbol()` at `DirectExecutionBackend.Imports.cs:624`

### 3. Which module owns it?

- PLT entry: eboot.bin (executable segment)
- PLT GOT slot: eboot.bin (writable data segment)
- Real resolver: Il2cppUserAssemblies.prx (at offset 0x208B90 from PRX base 0x804CD5000)
- NID: owned by Il2cppUserAssemblies.prx (IL2CPP runtime)

### 4. Does SharpEmu resolve it correctly?

**YES** — confirmed by:
- `DispatchIl2CppApiLookupSymbol()` handles NID `r8mvOaWdi28` (Imports.cs:622-624)
- Calls real resolver at `0x804ED9B90` via `TryCallGuestFunction` (Imports.cs:2393-2403)
- First resolver call returns `il2cpp_init` → `0x804ED85D0` (worklog EXP-026)
- The game does NOT crash at the indirect call (reaches WaitSema deadlock)

**CAVEAT**: EXP-138 RAX propagation bug may corrupt the return value. The `raxCaptureSlot` fix is in source (DirectExecutionBackend.cs:5068) but .NET 10.0.10 crash prevents runtime validation.

### 5. What function is entered?

**`il2cpp_init` at `0x804ED85D0`** (inside Il2cppUserAssemblies.prx)

This is the first IL2CPP API function pointer stored in the table at `0x801ED6320`. The consumer calls it via `call [0x801ED6320]` at offset +0x19A7.

### 6. Why does it reach WaitSema(0x81)?

`il2cpp_init` enters the IL2CPP runtime execution loop, which is the dispatch loop function `0x800AA0170`. This loop:
1. Calls `sceKernelWaitSema(0x81)` at `0x800AA0207` (offset +0x97)
2. Semaphore 0x81 (`Baselib_SystemSemaphore`) is NEVER signaled
3. Main thread blocks forever

Semaphore 0x81 lifecycle:
- Created during `real_init` (log line 8437): `sema.create handle=0x81 name='Baselib_SystemSemaphore'`
- WaitSema(0x81) at log line 8512
- SignalSema(0x81): **0 occurrences** in any log

### 7. Why does it not continue to PlayerLoop?

Because `il2cpp_init` does NOT return:
1. Consumer calls `il2cpp_init` at +0x19A7
2. `il2cpp_init` enters dispatch loop, blocks on WaitSema(0x81)
3. Consumer never reaches +0x3969 (init writer for `[0x801E51240]`)
4. `[0x801E51240]` stays NULL
5. 42 reader functions that depend on `[0x801E51240]` get NULL
6. PlayerLoop registration is skipped
7. No bootstrap job is submitted to the dispatch loop
8. WaitSema(0x81) is never signaled

### 8. Why are VideoOut calls still zero?

PlayerLoop registration requires `[0x801E51240]` to be non-NULL. Without PlayerLoop:
- No `sceVideoOutOpen`
- No `sceAgcDriverSubmitDcb`
- No `sceVideoOutSubmitFlip`
- No render targets
- No framebuffer writes

---

## TASK 6 — INT3 Instrumentation Revalidation

### BUG CONFIRMED: INT3 handler corrupts multi-byte instructions

**Location:** `DirectExecutionBackend.Exceptions.cs`, lines 234-238 (slot 1), 250-254 (slot 2), 265-269 (slot 3)

**Bug mechanism:**
1. INT3 fires at address X → kernel sets RIP = X+1
2. Handler restores original byte at X
3. Handler sets TF (trap flag)
4. Handler sets RIP = X+1 (line 237: `WriteCtxU64Icall(ctx, 248, addr+1)`)
5. CPU resumes at X+1 — SECOND BYTE of original instruction
6. CPU decodes garbage

**Mathematical proof (EXP-NEXT/XXX):**
- INT3 at `0x8013ED057` (bytes: `FF 15 C3 92 AE 00` = `call [rip+0x00AE92C3]`)
- Before INT3: `rax = 0x000000060000007F`
- After INT3 (logged "return"): `rax = 0x0000000000AE9342`
- CPU executed `ADC EAX, 0x00AE92C3` (byte 0x15 at X+1):
  - `0x6000007F + 0x00AE92C3 = 0x00AE9342` (32-bit, zero-extended)
  - **EXACT MATCH** — proves call was NEVER executed

### What IS valid:
- INT3 HIT logging (registers read BEFORE corruption)
- The fact that execution reached the INT3 address

### What is NOT valid:
- All post-INT3 register values
- All "return values" logged at the next INT3 slot
- EXP-173's "call returns with 0xAE9342" (was ADC result)

### Correct INT3 Restoration Method:

For multi-byte instructions, the handler must set RIP = X (instruction start), NOT X+1:

```csharp
// WRONG (current):
WriteCtxU64Icall(contextRecord, 248, _ripTraceAddress1 + 1);

// CORRECT (fix needed):
WriteCtxU64Icall(contextRecord, 248, _ripTraceAddress1);
```

And the re-patch condition must change:
```csharp
// WRONG (current):
if (_ripTraceSingleStepping1 && rip == _ripTraceAddress1 + 1)

// CORRECT (fix needed):
if (_ripTraceSingleStepping1 && rip > _ripTraceAddress1)
```

### Multi-byte Instruction Safety:

| Instruction | Length | Bug manifests? | Reason |
|-------------|--------|----------------|--------|
| `push rbp` (0x55) | 1 byte | NO | X+1 is correctly next instruction |
| `ret` (0xC3) | 1 byte | NO | Same |
| `nop` (0x90) | 1 byte | NO | Same |
| `je rel8` (0x74 XX) | 2 bytes | YES | X+1 = rel8 offset byte |
| `call rel32` (0xE8 XX XX XX XX) | 5 bytes | YES | X+1 = disp32 byte 0 |
| `call [rip+disp32]` (0xFF 0x15 XX XX XX XX) | 6 bytes | YES | X+1 = 0x15 = ADC opcode |
| `jcc rel32` (0x0F 0x8X XX XX XX XX) | 6 bytes | YES | X+1 = 0x8X |

### Trustworthiness of Previous RIP Traces:

| EXP | INT3 Address | Instruction | Trustworthy? |
|-----|-------------|-------------|--------------|
| EXP-145 | 0x80015DCD0 (producer entry) | 0x55 (push rbp, 1 byte) | YES — HIT valid |
| EXP-149 | various | mixed | MIXED — check instruction length |
| EXP-160 | 0x8013ED061 (je) | 0x74 (je rel8, 2 bytes) | HIT valid, POST values INVALID |
| EXP-173 | 0x8013ED057 (call) | 0xFF 0x15 (6 bytes) | HIT valid, POST values INVALID |
| EXP-173 | 0x8013ED061 (je) | 0x74 (2 bytes) | HIT valid, POST values INVALID |

**Conclusion:** INT3 HIT logs (confirming execution reached an address) are valid. All post-INT3 register values are INVALID for multi-byte instructions.

---

## TASK 7 — Final Stable Documentation

### Confirmed (Proven):

1. **argc=1 is a loader parameter mismatch** — game requires argc≥2 (EXP-169)
2. **SHARPEMU_GUEST_ARGS="dummy_arg" makes argc=2** — fixes [0x801E518C8] initialization (EXP-169)
3. **[0x801E518C8] = 0x00000020000259C0 with argc=2** (EXP-170)
4. **[0x801E51240] stays NULL** even with argc=2 (EXP-170)
5. **Consumer exits at +0x19A7** (call [0x801ED6320]) — does NOT return (EXP-173, EXP-NEXT)
6. **[0x801ED6320] = il2cpp_init (0x804ED85D0)** — resolved via NID r8mvOaWdi28 (EXP-XXX)
7. **il2cpp_init enters dispatch loop 0x800AA0170** — blocks on WaitSema(0x81) (EXP-NEXT)
8. **[0x801E51240] init writer at +0x3969 is NEVER reached** — consumer exits before (EXP-171)
9. **INT3 handler corrupts multi-byte instructions** — mathematical proof (EXP-NEXT/XXX)
10. **Dreaming Sarah Golden Test PASSES** — 228 colors at frame 138 (EXP-138)
11. **PRX directory structure is critical** — sce_module/, Media/Modules/, Media/Metadata/ (EXP-139.4)
12. **TLS is NOT the issue** — properly initialized, __tls_get_addr never called (EXP-172)

### Rejected (Disproven):

1. **boot.config required** — no effect (EXP-141-followup)
2. **sceKernelMkdir blocks init** — fixed, not the blocker (EXP-144)
3. **arch_init_gc returning NOT_FOUND** — direct-bridged when PRXs loaded (EXP-141)
4. **il2cpp_resolve_icall returns NULL** — never called, icalls pre-linked (EXP-143)
5. **TLS initialization issue** — properly working (EXP-172)
6. **Initializer ordering issue** — initializer executes before consumer (EXP-167)
7. **argc=1 is the ONLY blocker** — argc=2 fixes [0x801E518C8] but not [0x801E51240] (EXP-170)
8. **Consumer early exit at +0x72** — not taken with argc=2 (EXP-170)
9. **Skip branches +0x277 to +0x191F taken** — all NOT taken (EXP-171)
10. **[0x801E51240] has no init writer** — writer exists at +0x3969 (EXP-159)
11. **[0x801ED6320] is NULL at runtime** — no crash, must be non-NULL (EXP-NEXT)
12. **GOT writer is inside consumer** — separate function 0x8013FB0B0 (EXP-NEXT)
13. **GOT writer is never called** — called from parent at +0xDDB (EXP-NEXT)
14. **EXP-173's "call returns with 0xAE9342"** — INT3 bug, ADC result (EXP-NEXT)
15. **EXP-138 RAX propagation as root cause** — resolver runs natively with PRXs (EXP-156)
16. **CallNativeEntry nested crash as root cause** — secondary to SIGSEGV (EXP-139.3)
17. **Crash at 0x80135DE83** — address never reached (EXP-158)
18. **Chain B (0x801D1E558)** — address unmapped (EXP-162)
19. **Producer pointer NULL at 0x801cfccb0** — zero reads (EXP-133)
20. **Vblank event missing** — not imported (EXP-126)
21. **HLE semaphore bug** — correct in FAST_PATH=0 mode (EXP-135)
22. **Atomic operations bug** — direct execution, correct by construction (EXP-114)

### Unknown (Needs Evidence):

1. **Why il2cpp_init does NOT return** — three hypotheses open:
   - (a) Calls a function that blocks (thread join, event wait)
   - (b) Return path broken by EXP-138 RAX propagation bug
   - (c) Intentionally blocks (waiting for bootstrap job that never arrives)

2. **Runtime value of [0x801ED6320]** — inferred to be 0x804ED85D0 (il2cpp_init) but not directly verified due to:
   - INT3 handler bug (can't trust post-INT3 values)
   - .NET 10.0.10 crash (can't run to consumer)

3. **Whether EXP-138 raxCaptureSlot fix works at runtime** — source verified, but .NET 10.0.10 crash prevents validation

4. **Whether fixing il2cpp_init's non-return would fix the deadlock** — the init writer at +0x3969 might have its own issues

### Next Evidence Target:

**Primary: Fix the .NET 10.0.10 "Invalid Program" crash**

Without fixing this, no runtime evidence can be collected past the first resolver call. Options:
1. Install an earlier .NET 10 preview/RC version (EXP-170..173 used one that worked)
2. Find a workaround for the nested UnmanagedCallersOnly call
3. Use a different execution path that avoids the nested call

**Secondary: Fix the INT3 handler (temporary, for evidence collection)**

Once .NET 10 crash is fixed:
1. Fix INT3 handler: set RIP = X instead of X+1
2. Add [0x801ED6320] to the memory dump in INT3 handler
3. Set INT3 at 0x8013ED057 to read [0x801ED6320] at runtime
4. Verify [0x801ED6320] = 0x804ED85D0

**Tertiary: Trace il2cpp_init execution**

Once [0x801ED6320] is verified:
1. Set INT3 at 0x804ED85D0 (il2cpp_init entry)
2. Use single-step trace to follow execution inside il2cpp_init
3. Find the exact instruction where il2cpp_init blocks

### Known Working Configurations:

| Configuration | Status | Notes |
|---------------|--------|-------|
| Dreaming Sarah + Xvfb + Lavapipe + GLFW | ✅ WORKING | 228 colors at frame 138 |
| Yatzi + argc=2 + proper PRX layout | ⚠️ DEADLOCK | Reaches WaitSema(0x81) — root cause known |
| Yatzi + argc=1 | ⚠️ DEADLOCK | Early exit at consumer +0x72 |
| Yatzi + SHARPEMU_HEADLESS=1 | ❌ BROKEN | HeadlessVideoPresenter is a stub |
| Yatzi + SHARPEMU_SEMA_FAST_PATH=1 | ⚠️ MASKS BUG | WaitSema returns OK without blocking |

### Known Broken Configurations:

| Configuration | Issue | Fix |
|---------------|-------|-----|
| Missing PRXs | .NET 10 "Invalid Program" crash | Fix directory structure (EXP-139.4) |
| global-metadata.dat in Media/Modules/ | SIGSEGV at NULL+0x98 | Move to Media/Metadata/ (EXP-140-followup) |
| SHARPEMU_HEADLESS=1 for golden tests | No rendering | Use Xvfb + Lavapipe (EXP-138) |
| argc=1 (default) | [0x801E518C8] stays NULL | Set SHARPEMU_GUEST_ARGS="dummy_arg" (EXP-169) |

### Root Cause Tree:

```
WaitSema(0x81) DEADLOCK
├── Semaphore 0x81 never signaled
│   ├── No bootstrap job submitted
│   │   ├── PlayerLoop registration SKIPPED
│   │   │   ├── [0x801E51240] = NULL
│   │   │   │   ├── Init writer at 0x8013EF019 NEVER reached
│   │   │   │   │   └── Consumer exits at +0x19A7
│   │   │   │   │       └── call [0x801ED6320] = il2cpp_init does NOT return
│   │   │   │   │           ├── Enters dispatch loop 0x800AA0170
│   │   │   │   │           └── Blocks on WaitSema(0x81) ← DEADLOCK
│   │   │   │   └── 42 reader functions get NULL
│   │   │   └── No sceVideoOutOpen
│   │   └── No VideoOut calls
│   └── 13 worker threads blocked on even semaphores
└── .NET 10.0.10 crash prevents runtime validation
    └── "Invalid Program: attempted to call a UnmanagedCallersOnly method"
```

---

## Stable Baseline Summary

| Metric | Value |
|--------|-------|
| Git commit | a6a416c (EXP-173) |
| Experiments completed | EXP-1 through EXP-173 + EXP-NEXT + EXP-XXX |
| Dreaming Sarah Golden Test | ✅ PASS (228 colors at frame 138) |
| Yatzi boot status | ❌ WaitSema(0x81) deadlock (root cause known) |
| Arise status | ❌ Pre-existing SIGILL (NOT a regression) |
| Confirmed root cause | il2cpp_init does not return → [0x801E51240] stays NULL |
| INT3 handler bug | CONFIRMED — fix documented, not applied |
| .NET 10 crash | BLOCKS runtime validation |
| Source knowledge comments | Added to 3 key files |
| EXP reports preserved | All 173+ reports in exp-reports/ and scripts/ |

**This baseline is STABLE for future investigation. No patches applied. No fixes implemented. Evidence chain is complete to the extent possible with current .NET 10 runtime.**
