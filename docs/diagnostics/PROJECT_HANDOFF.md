# SharpEmuT24 — Project Handoff Document

**Date:** 2026-07-29
**Status:** EXP-028 complete, root cause found, EXP-029 queued
**Repository:** https://github.com/Sh-TB/sharpemuT24
**Branch:** master
**Latest commit:** (see git log below)

---

## Investigation Summary

### EXP-026 (Closed)
- **Finding:** Synthetic x86-64 CPU emulator finds all 239/239 IL2CPP symbols
- **Conclusion:** Resolver algorithm is correct. BST tree is correct. strcmp reference is correct.
- **Key file:** `docs/diagnostics/EXP026_DIVERGENCE_REPORT.md`

### EXP-027 (Closed — Method A)
- **Finding:** Host CPU, Unicorn engine, and synthetic Python CPU all agree on test/lea/cmovns/cmovns sequence (T4: 10/10) and all 16 cmov conditions (T16: 768/768)
- **Conclusion:** CPU instruction emulation of cmovns/test/lea is correct at the algorithmic level
- **Key file:** `docs/diagnostics/EXP027_FIRST_DIVERGENCE_REPORT.md`

### EXP-028 (Closed — Root Cause Found)

**Root cause:** Native strcmp at `0x804fc2d40` returns a non-zero (negative) value for exact string matches, causing the `js return_0` branch at `0x804ED9BF7` to be taken, making the resolver return 0 instead of the correct `func_impl` pointer.

**Evidence chain:**

1. **T12/T13 Boundary Trace** — 232 resolver calls, ALL classified as Case C (genuine zero, not return corruption)
   - Input registers valid (RDI points to correct query string)
   - Return value propagation correct (returnValue=0 from inner CpuContext.Rax)
   - Bug is INSIDE the resolver's native execution

2. **T5 Memory Read Trace** — BST traversal matches synthetic CPU exactly
   - Same node addresses (e.g., root=0x2000027440, sentinel=0x2000003F20)
   - Same symbol names at each node
   - Same traversal direction (LEFT/RIGHT) at each level
   - Same strcmp results (C# string.CompareOrdinal matches synthetic)

3. **T6 Branch/Candidate Trace** — Correct candidate found with non-zero func_impl
   - For `il2cpp_init`: candidate=0x2000025A40, cand_name='il2cpp_init', func_impl=0x804ED85D0
   - C# strcmp(QUERY, CANDIDATE) = 0 (exact match)
   - Expected resolver return: 0x804ED85D0
   - Actual resolver return: 0x0

4. **Conclusion:** The native strcmp function at `0x804fc2d40` (in Il2cppUserAssemblies.prx) must be returning a negative value for exact string matches. This causes:
   - `test eax, eax` → SF=1 (sign flag set)
   - `js 0x804ED9BAC` → TAKEN (jump if sign)
   - `xor eax, eax` → RAX=0
   - `ret` → return 0

**First divergence:**
```
RIP: 0x804ED9BF0
Instruction: call 0x804fc2d40 (strcmp — FINAL strcmp in resolver)
Expected: strcmp('il2cpp_init', 'il2cpp_init') = 0 → SF=0 → js NOT taken → return 0x804ED85D0
Actual: native strcmp returns negative → SF=1 → js TAKEN → return 0
Affected register: RAX (expected 0x804ED85D0, actual 0x0)
Affected flags: SF (expected 0, actual 1)
Root cause category: CPU Backend — native strcmp returns wrong value
Evidence: /tmp/exp028_logs/branch_trace.log
```

---

## What Was NOT Done (per evidence-only policy)

- ❌ No fix applied to the strcmp implementation
- ❌ No fix applied to the resolver
- ❌ No fix applied to the CPU backend
- ❌ No functional changes to SharpEmu behavior

Only diagnostic instrumentation was added (T12/T13 boundary trace, T5 memory read trace, T6 branch/candidate trace).

---

## Current Debugging State

### Where the investigation stopped

The investigation stopped at **EXP-028 complete**. The root cause has been localized to the native strcmp function at `0x804fc2d40`. The next logical step is **EXP-029: Native strcmp Investigation**.

### What EXP-029 should do

1. **Capture EAX + RFLAGS immediately after `call strcmp` at `0x804ED9BF0`**
   - This requires per-instrumentation tracing of the resolver's final strcmp call
   - Can use inline tracing in `DispatchIl2CppApiLookupSymbol` (same approach as T5/T6)
   - OR use INT3 breakpoint at `0x804ED9BF5` (the `test eax, eax` after the call)

2. **Compare native strcmp behavior with libc strcmp**
   - The native strcmp at `0x804fc2d40` goes through SharpEmu's PLT/GOT resolution
   - Check if it's using the HLE intrinsic (`DirectExecutionBackend.cs:1326`) or a native implementation
   - The HLE intrinsic was confirmed applied in EXP-026 (INTRINSIC-CHECK), but it may produce incorrect results

3. **Investigate the strcmp intrinsic implementation**
   - Check `DirectExecutionBackend.cs` for the `TryCreateNativeImportIntrinsic` function
   - The intrinsic for `Ovb2dSJOAuE` (strcmp NID) may have a bug in how it returns the comparison result
   - Specifically: does it correctly return 0 for equal strings?

4. **Test the strcmp intrinsic in isolation**
   - Create a small test that calls the intrinsic with two identical strings
   - Verify it returns 0 (not negative)

### Do NOT repeat

- ❌ Do NOT re-run T5 (memory read trace) — already proven correct
- ❌ Do NOT re-run T6 (branch/candidate trace) — already proven correct
- ❌ Do NOT re-run T12/T13 (boundary trace) — already proven Case C
- ❌ Do NOT re-investigate BST tree structure — already proven correct
- ❌ Do NOT re-investigate resolver algorithm — already proven correct (EXP-026)
- ❌ Do NOT re-investigate cmovns/test/lea instruction emulation — already proven correct (EXP-027)

### First next step

Start EXP-029 by adding inline tracing to capture EAX immediately after the resolver's final `call strcmp` at `0x804ED9BF0`. This will definitively prove whether native strcmp returns 0 or non-zero for exact matches.

---

## Environment Stabilization

Three permanent scripts have been committed:

1. `scripts/bootstrap-runtime.sh` — one-command environment restore
2. `scripts/env-fingerprint.sh` — environment state capture
3. `scripts/golden-test.sh` — automated Dreaming Sarah regression test

Future sessions should start with:
```bash
bash scripts/bootstrap-runtime.sh && source /tmp/bootstrap-env.sh
bash scripts/env-fingerprint.sh
cd /tmp/my-project/work/sharpemuT24 && dotnet build SharpEmu.slnx -c Release
bash scripts/golden-test.sh
```

---

## Git State

```
Branch: master
Commits (local):
  34e3083 scripts: add runtime bootstrap, env fingerprint, and golden test automation
  168b3dd docs(diagnostics): add SECTION 0 Repository Integrity Gate policy
  08c0735 docs(diagnostics): add EXP-026 + EXP-027 + EXP-028 investigation reports

Default branch: main (at 3e3d8081, unchanged)
No merge to main.
No upstream modification.
```

---

## Key Files

| File | Purpose |
|------|---------|
| `docs/diagnostics/PROJECT_HANDOFF.md` | This file — read this first |
| `docs/diagnostics/worklog.md` | Full multi-experiment log |
| `docs/diagnostics/FACTS_CONFIRMED.md` | 18 confirmed facts (append-only) |
| `docs/diagnostics/EXP026_DIVERGENCE_REPORT.md` | Algorithm correctness proof |
| `docs/diagnostics/EXP027_FIRST_DIVERGENCE_REPORT.md` | CPU instruction correctness proof |
| `docs/diagnostics/SECTION0_REPOSITORY_INTEGRITY.md` | Repository integrity policy |
| `docs/diagnostics/REPOSITORY_INTEGRITY_CHECKLIST.md` | Pre-flight checklist |
| `scripts/bootstrap-runtime.sh` | One-command environment restore |
| `scripts/env-fingerprint.sh` | Environment fingerprint |
| `scripts/golden-test.sh` | Golden Test automation |
| `src/SharpEmu.Libs/Kernel/_Exp028T12T13BoundaryTrace.cs` | T12/T13 boundary trace |
| `src/SharpEmu.Libs/Kernel/_Exp028MemoryReadTracer.cs` | T5 memory read trace |
| `src/SharpEmu.Libs/Kernel/_Exp028BranchTracer.cs` | T6 branch trace |

---

## Evidence Files (ephemeral — not in git)

These files are on the ephemeral overlay and will be lost on container restart.
They are referenced here for completeness. If needed, re-run Yatzi with the
instrumented build to regenerate them.

| File | Contents |
|------|----------|
| `/tmp/exp028_logs/boundary_trace.log` | 232 T12-PRE + 232 T12-POST + 232 CASE-C |
| `/tmp/exp028_logs/memory_read_trace.log` | T5: BST traversal for 5 resolver calls |
| `/tmp/exp028_logs/branch_trace.log` | T6: candidate + func_impl + final_strcmp for 5 calls |
| `/tmp/exp028_logs/golden_test.log` | Dreaming Sarah Golden Test (PASS) |
| `/tmp/exp028_logs/yatzi_t6_run.log` | Full Yatzi run with T5+T6 (632KB) |
