# Yatzi Complete Diagnostic History

**Single source of truth for all Yatzi (PPSA17697) debugging experiments.**
**Coverage: EXP-026 through EXP-098 + EXP-111 (71 entries — note: EXP-099..110 do not exist, numbering gap from EXP-111 side test)**
**Last updated: 2026-08-02 (EXP-098)**

This file consolidates ALL diagnostic knowledge from every EXP report, git commit, and worklog entry. Future debugging MUST start from this file.

---

## Table of Contents

1. [EXP Timeline (EXP-026 through EXP-097)](#exp-timeline)
2. [Phase Summary](#phase-summary)
3. [Key Corrections and Superseded Theories](#key-corrections)
4. [Current State (after EXP-097)](#current-state)
5. [Knowledge Rules Learned](#knowledge-rules)
6. [All Links](#all-links)

---

## EXP Timeline

### Phase 1: CPU/Resolver Verification (EXP-026 to EXP-032)

#### EXP-026 — IL2CPP Symbol Resolver Algorithm Verification
- **Date:** 2026-07-28
- **Commit:** [08c0735](https://github.com/Sh-TB/sharpemuT24/commit/08c0735)
- **Question:** Does the IL2CPP symbol resolver BST algorithm work correctly?
- **Hypothesis:** The BST walk algorithm has a bug causing it to miss IL2CPP symbols.
- **Tools/Logs:** Synthetic x86-64 CPU emulator (Python), Unicorn engine, host CPU comparison
- **Finding:** Synthetic x86-64 CPU emulator finds all 239/239 IL2CPP symbols. Algorithm definitively correct. Reference RBTree agrees.
- **Root Cause:** None — resolver algorithm is correct
- **Status:** CONFIRMED
- **Related:** EXP-028 (continued investigation)
- **Impact:** Closed: resolver algorithm verified correct. Mismatch was elsewhere.

#### EXP-027 — CPU Instruction Emulation Verification
- **Date:** 2026-07-28
- **Commit:** [08c0735](https://github.com/Sh-TB/sharpemuT24/commit/08c0735)
- **Question:** Is CPU instruction emulation correct (test/lea/cmovns/cmov conditions)?
- **Hypothesis:** CPU instruction emulation has a bug in condition flags or cmov handling.
- **Tools/Logs:** Host CPU, Unicorn engine, synthetic Python CPU — T4 (10/10), T16 (768/768)
- **Finding:** Host CPU, Unicorn engine, and synthetic Python CPU all agree on test/lea/cmovns/cmovns sequence (T4: 10/10) and all 16 cmov conditions (T16: 768/768).
- **Root Cause:** None — CPU instruction emulation is correct
- **Status:** CONFIRMED
- **Related:** EXP-028 (Method B continued)
- **Impact:** Closed: CPU emulation verified correct. Divergence was elsewhere.

#### EXP-028 — First Divergence Investigation
- **Date:** 2026-07-29
- **Commit:** [f1d0968](https://github.com/Sh-TB/sharpemuT24/commit/f1d0968)
- **Question:** Find the first divergence between SharpEmu and reference CPU execution.
- **Hypothesis:** The divergence is in the IL2CPP resolver's strcmp path.
- **Tools/Logs:** EXP028 tracers, GOT slot analysis
- **Finding:** strcmp GOT slot points to freed memory — the GOT was being set up correctly but the target string was in a region that got freed/moved.
- **Root Cause:** strcmp GOT pointing to freed memory
- **Status:** CONFIRMED
- **Related:** EXP-026, EXP-027
- **Impact:** Fixed GOT lifetime. Enabled IL2CPP resolver to work.

#### EXP-029 — strcmp GOT Root Cause
- **Date:** 2026-07-29
- **Commit:** [13d7a4c](https://github.com/Sh-TB/sharpemuT24/commit/13d7a4c)
- **Question:** Why does the IL2CPP BST strcmp fail after resolver runs?
- **Finding:** strcmp GOT points to freed memory — the trampoline lifetime was too short.
- **Root Cause:** Trampoline/GOT lifetime management
- **Status:** CONFIRMED
- **Related:** EXP-028, EXP-030
- **Impact:** Root cause of resolver crash identified.

#### EXP-030 — Trampoline Lifetime Fix (Revised)
- **Date:** 2026-07-29
- **Commit:** [ee1ed98](https://github.com/Sh-TB/sharpemuT24/commit/ee1ed98)
- **Question:** Fix trampoline lifetime to prevent GOT invalidation.
- **Finding:** Trampoline lifetime fix attempted, root cause revised — the issue was deeper than just lifetime.
- **Root Cause:** Revised: see EXP-031/032
- **Status:** SUPERSEDED
- **Related:** EXP-029, EXP-031
- **Impact:** Superseded by EXP-031/032 findings.

#### EXP-031 — TryCallGuestFunction Context
- **Date:** 2026-07-29
- **Commit:** [a8d5c09](https://github.com/Sh-TB/sharpemuT24/commit/a8d5c09)
- **Question:** Narrow down the execution context issue in TryCallGuestFunction.
- **Finding:** Root cause narrowed to TryCallGuestFunction execution context — return value not propagating correctly.
- **Root Cause:** Revised: see EXP-032
- **Status:** SUPERSEDED
- **Related:** EXP-030, EXP-032
- **Impact:** Led to EXP-032's definitive root cause.

#### EXP-032 — ROOT CAUSE: CpuContext.Rax Not Updated
- **Date:** 2026-07-29
- **Commit:** [3c186a4](https://github.com/Sh-TB/sharpemuT24/commit/3c186a4) (analysis), [4b920fe](https://github.com/Sh-TB/sharpemuT24/commit/4b920fe) (fix)
- **Question:** Why does the resolver return 0 (NULL) for IL2CPP function addresses?
- **Hypothesis:** The return value from native calls is not being propagated to the guest context.
- **Tools/Logs:** RESOLVER-TRACE logging, CallNativeEntry analysis
- **Finding:** ROOT CAUSE FOUND: CpuContext.Rax never updated from nativeReturn — CallNativeEntry return value (int→long truncation + missing CpuContext update).
- **Root Cause:** CallNativeEntry int→long truncation + CpuContext.Rax not updated
- **Status:** CONFIRMED
- **Related:** EXP-031, EXP-033
- **Impact:** Fixed: return value propagation. All 232 IL2CPP functions now resolve correctly.

### Phase 2: NULL Execute Investigation (EXP-033 to EXP-036)

#### EXP-033 — NULL Execute Fault Limit
- **Date:** 2026-07-29
- **Commit:** [af7d8b8](https://github.com/Sh-TB/sharpemuT24/commit/af7d8b8)
- **Question:** Why does the game crash after the resolver completes?
- **Finding:** Post-resolver crash from NULL execute fault limit (100000) — guest code calls NULL function pointers.
- **Root Cause:** NULL function pointer calls in guest code (IL2CPP stubs)
- **Status:** CONFIRMED
- **Related:** EXP-032, EXP-034
- **Impact:** Identified NULL execute as the next blocker.

#### EXP-034 — Globals Populated But Stubs Still NULL
- **Date:** 2026-07-29
- **Commit:** [0e13c17](https://github.com/Sh-TB/sharpemuT24/commit/0e13c17)
- **Question:** Are IL2CPP globals populated after resolver runs?
- **Finding:** Globals ARE populated (all 232 real func_impl addresses found). But fake heap stubs still cause NULL calls — re-patching import stubs with real addresses fails (0/232 patched).
- **Root Cause:** Re-patching fails because NID-to-name lookup fails for eboot imports
- **Status:** SUPERSEDED (by EXP-067)
- **Related:** EXP-033, EXP-035, EXP-066
- **Impact:** Superseded: EXP-067 proved re-patching was unnecessary (resolver returns real addresses directly).

#### EXP-035 — Fake Heap Disproven
- **Date:** 2026-07-29
- **Commit:** [56bd06c](https://github.com/Sh-TB/sharpemuT24/commit/56bd06c)
- **Question:** Is the fake heap the cause of NULL executes?
- **Finding:** Fake heap disproven — root cause is uninitialized task descriptor. Workers call [rbx+0xF8]=NULL because task function pointer is never set.
- **Root Cause:** Uninitialized task descriptor [rbx+0xF8]=NULL
- **Status:** SUPERSEDED (by EXP-081)
- **Related:** EXP-034, EXP-064
- **Impact:** Superseded: EXP-081 found the real reason [rbx+0xF8] is NULL (FAST_PATH=1).

#### EXP-036 — FAST_PATH=1 Causing il2cpp_init Starvation
- **Date:** 2026-07-29
- **Commit:** [7986cbe](https://github.com/Sh-TB/sharpemuT24/commit/7986cbe)
- **Question:** Why is il2cpp_init never reached?
- **Hypothesis:** FAST_PATH=1 causes workers to spin and starve the main thread.
- **Finding:** SHARPEMU_SEMA_FAST_PATH=1 was causing il2cpp_init starvation — workers spin and starve the main thread.
- **Root Cause:** FAST_PATH=1 makes WaitSema return immediately, starving main thread
- **Status:** CONFIRMED — REPEATED IN EXP-081
- **Related:** EXP-062, EXP-063, EXP-068, EXP-081
- **Impact:** This finding was CORRECT but was overridden by EXP-063 which switched back to FAST_PATH=1. EXP-081 re-discovered this same root cause. **This is the most important finding in the entire investigation — it was found, lost, and found again.**

### Phase 3: IL2CPP Initialization Investigation (EXP-037 to EXP-052)
*(All EXPs in this phase were based on the WRONG eboot — see EXP-061)*

#### EXP-037 — Empty init_array
- **Date:** 2026-07-29
- **Commit:** [5a5d782](https://github.com/Sh-TB/sharpemuT24/commit/5a5d782)
- **Finding:** IL2CPP static initializers not running — empty init_array. No .init_array entries found.
- **Status:** SUPERSEDED (dump was wrong — EXP-061)
- **Related:** EXP-038, EXP-059, EXP-061

#### EXP-038 — DT_INIT Callback (rdx) Not Passed
- **Date:** 2026-07-30
- **Commit:** [6f7a979](https://github.com/Sh-TB/sharpemuT24/commit/6f7a979)
- **Finding:** DT_INIT callback (rdx) not passed — IL2CPP registration never runs. rdx=0 instead of callback address.
- **Status:** SUPERSEDED (by EXP-039)
- **Related:** EXP-037, EXP-039

#### EXP-039 — DT_INIT rdx Hypothesis Disproven
- **Date:** 2026-07-30
- **Commit:** [1e13915](https://github.com/Sh-TB/sharpemuT24/commit/1e13915)
- **Finding:** DT_INIT rdx hypothesis disproven — circular dependency in il2cpp_init. Passing rdx doesn't help.
- **Status:** CONFIRMED
- **Related:** EXP-038, EXP-040

#### EXP-040 — Hash Table Entries Never Filled
- **Date:** 2026-07-30
- **Commit:** [f41736c](https://github.com/Sh-TB/sharpemuT24/commit/f41736c)
- **Finding:** Hash table entries never filled — workaround clears original crash.
- **Status:** CONFIRMED
- **Related:** EXP-039, EXP-041

#### EXP-041 — Init Order Issue
- **Date:** 2026-07-30
- **Commit:** [d76f7bf](https://github.com/Sh-TB/sharpemuT24/commit/d76f7bf)
- **Finding:** il2cpp_init called BEFORE hash lookup sets 0x801E51240.
- **Status:** CONFIRMED
- **Related:** EXP-040, EXP-042

#### EXP-042 — Metadata Lookup Returns Valid Object
- **Date:** 2026-07-30
- **Commit:** [813a5d2](https://github.com/Sh-TB/sharpemuT24/commit/813a5d2)
- **Finding:** Metadata lookup returns valid object — 0x801E51240 needs pre-init.
- **Status:** CONFIRMED
- **Related:** EXP-041, EXP-043

#### EXP-043 — Pre-init Mechanism Missing
- **Date:** 2026-07-30
- **Commit:** [7a7b4ad](https://github.com/Sh-TB/sharpemuT24/commit/7a7b4ad)
- **Finding:** Pre-init mechanism missing — PRX DT_INIT flag forces jump to INT3.
- **Status:** SUPERSEDED (by EXP-044)
- **Related:** EXP-042, EXP-044

#### EXP-044 — INT3 is ELF Padding
- **Date:** 2026-07-30
- **Commit:** [7465613](https://github.com/Sh-TB/sharpemuT24/commit/7465613)
- **Finding:** INT3 is ELF padding (not module_start) — fini_array has 11 entries.
- **Status:** CONFIRMED
- **Related:** EXP-043, EXP-045

#### EXP-045 — eboot fini_array
- **Date:** 2026-07-30
- **Commit:** [aedf782](https://github.com/Sh-TB/sharpemuT24/commit/aedf782)
- **Finding:** eboot fini_array found (20 entries) but not root cause.
- **Status:** CONFIRMED
- **Related:** EXP-044, EXP-046

#### EXP-046 — Crash from Call #8
- **Date:** 2026-07-30
- **Commit:** [4721b59](https://github.com/Sh-TB/sharpemuT24/commit/4721b59)
- **Finding:** Crash is from call #8, not #7 — metadata lookup returns non-zero.
- **Status:** CONFIRMED
- **Related:** EXP-045, EXP-047

#### EXP-047 — Three Fixes Prevent Callback Crash
- **Date:** 2026-07-30
- **Commit:** [3428a8f](https://github.com/Sh-TB/sharpemuT24/commit/3428a8f)
- **Finding:** Three fixes prevent callback crash but cascade remains.
- **Status:** CONFIRMED
- **Related:** EXP-046, EXP-048

#### EXP-048 — Callback Stub Allows il2cpp_init Progress
- **Date:** 2026-07-30
- **Commit:** [538c4da](https://github.com/Sh-TB/sharpemuT24/commit/538c4da)
- **Finding:** Callback stub-ret allows il2cpp_init to progress — workers created.
- **Status:** CONFIRMED
- **Related:** EXP-047, EXP-049

#### EXP-049 — NULL at 0x801E51220
- **Date:** 2026-07-30
- **Commit:** [db3d578](https://github.com/Sh-TB/sharpemuT24/commit/db3d578)
- **Finding:** NULL pointer at 0x801E51220 — same class as 0x801E51240. Systemic pattern.
- **Status:** CONFIRMED
- **Related:** EXP-048, EXP-050

#### EXP-050 — Hash Lookup Skipped by Conditional Jumps
- **Date:** 2026-07-30
- **Commit:** [ea58673](https://github.com/Sh-TB/sharpemuT24/commit/ea58673)
- **Finding:** Hash lookup skipped by 15+ conditional jumps — stub cleared first cascade.
- **Status:** CONFIRMED
- **Related:** EXP-049, EXP-051

#### EXP-051 — Buffer+NOP+Loop Fix Tested
- **Date:** 2026-07-30
- **Commit:** [30e6215](https://github.com/Sh-TB/sharpemuT24/commit/30e6215)
- **Finding:** Buffer+NOP+loop fix tested — all cause new crashes, reverted.
- **Status:** CONFIRMED
- **Related:** EXP-050, EXP-052

#### EXP-052 — Missing il2cpp_codegen_register
- **Date:** 2026-07-30
- **Commit:** [0f6db8d](https://github.com/Sh-TB/sharpemuT24/commit/0f6db8d)
- **Finding:** Missing mechanism identified — wrapper 0x800805AE0 = il2cpp_codegen_register, called indirectly, never invoked.
- **Status:** CONFIRMED
- **Related:** EXP-051, EXP-053

### Phase 4: Metadata Structure Investigation (EXP-053 to EXP-058)
*(All EXPs in this phase were based on the WRONG eboot — see EXP-061)*

#### EXP-053 — Wrapper Never Called
- **Date:** 2026-07-30
- **Commit:** [6b62771](https://github.com/Sh-TB/sharpemuT24/commit/6b62771)
- **Finding:** Wrapper 0x800805AE0 NEVER called. Static table 0x1CC0080 is string fragment pool not Il2CppMetadataRegistration.
- **Status:** CONFIRMED
- **Related:** EXP-052, EXP-054

#### EXP-054 — Il2CppCodeRegistration Found
- **Date:** 2026-07-30
- **Commit:** [a101e62](https://github.com/Sh-TB/sharpemuT24/commit/a101e62)
- **Finding:** Il2CppCodeRegistration found at 0x8086E9000.
- **Status:** CONFIRMED
- **Related:** EXP-053, EXP-055

#### EXP-055 — MetadataRegistration Found
- **Date:** 2026-07-30
- **Commit:** [5f89b31](https://github.com/Sh-TB/sharpemuT24/commit/5f89b31)
- **Finding:** MetadataRegistration found at 0x80885C580. PRX DT_INIT invalid.
- **Status:** CONFIRMED
- **Related:** EXP-054, EXP-056

#### EXP-056 — Missing Consumer Function
- **Date:** 2026-07-30
- **Commit:** [d325f54](https://github.com/Sh-TB/sharpemuT24/commit/d325f54)
- **Finding:** Major pivot — structs already populated. Root cause is missing CONSUMER function.
- **Status:** CONFIRMED
- **Related:** EXP-055, EXP-057

#### EXP-057 — Call #7 is Consumer
- **Date:** 2026-07-30
- **Commit:** [77bd7dc](https://github.com/Sh-TB/sharpemuT24/commit/77bd7dc)
- **Finding:** Call #7 (0x804F23320) is consumer candidate with 0x38-byte stride loops.
- **Status:** CONFIRMED
- **Related:** EXP-056, EXP-058

#### EXP-058 — Metadata Loader Fails
- **Date:** 2026-07-30
- **Commit:** [d928189](https://github.com/Sh-TB/sharpemuT24/commit/d928189)
- **Finding:** Call #7 entered but returns early — metadata loader 0x804F04750 fails (missing metadata file).
- **Status:** CONFIRMED
- **Related:** EXP-057, EXP-059

### Phase 5: Dump Correction (EXP-059 to EXP-061)

#### EXP-059 — Dump Completeness Issue
- **Date:** 2026-07-31
- **Commit:** [efd65f5](https://github.com/Sh-TB/sharpemuT24/commit/efd65f5)
- **Finding:** Ground-truth diff with Unity 2022.3.5f1 source — struct at 0x8086E9000 is Il2CodeGenModule not CodeReg. Root cause is DUMP COMPLETENESS (missing PRX + metadata).
- **Status:** CONFIRMED
- **Related:** EXP-058, EXP-060

#### EXP-060 — Complete Dump Fixes IL2CPP Init
- **Date:** 2026-07-31
- **Commit:** [a915330](https://github.com/Sh-TB/sharpemuT24/commit/a915330)
- **Finding:** Complete dump verified — IL2CPP init WORKS, metadata loaded. New blocker is AssetGarbageCollectorHelper semaphore stall.
- **Status:** CONFIRMED
- **Related:** EXP-059, EXP-061

#### EXP-061 — CRITICAL: Mixed Dump Detected
- **Date:** 2026-07-31
- **Commit:** [b28cce2](https://github.com/Sh-TB/sharpemuT24/commit/b28cce2)
- **Finding:** MIXED DUMP DETECTED — old eboot (7.7MB) was Dreaming Sarah, not Yatzi! All EXP-035..058 addresses were invalid.
- **Root Cause:** Wrong eboot.bin (Dreaming Sarah instead of Yatzi)
- **Status:** CRITICAL CORRECTION
- **Related:** EXP-035..058 ALL INVALID
- **Impact:** ALL EXP-035..058 conclusions invalidated. Re-investigation needed with correct dump. **This was the biggest waste of debugging time in the entire investigation.**

### Phase 6: Semaphore/FAST_PATH Investigation (EXP-062 to EXP-069)

#### EXP-062 — FAST_PATH=0 Deadlock (REPORTED — NEEDS RE-VALIDATION)
- **Date:** 2026-07-31
- **Commit:** [89ad82e](https://github.com/Sh-TB/sharpemuT24/commit/89ad82e)
- **Question:** Does FAST_PATH=0 cause deadlock?
- **Finding:** Semaphore deadlock confirmed — SignalSema NEVER called. 14 threads blocked.
- **Root Cause:** Reported: deadlock from SignalSema never being called
- **Status:** SUPERSEDED BY EXP-081 (needs re-validation)
- **Related:** EXP-063, EXP-081
- **Impact:** Originally reported FAST_PATH=0 causes deadlock. EXP-081 challenges this — with current codebase (post-EXP-065), FAST_PATH=0 may work. **This is the critical question that EXP-081 validation must answer.**

#### EXP-063 — FAST_PATH=1 Resolves Deadlock (WRONG — CORRECTED BY EXP-081)
- **Date:** 2026-07-31
- **Commit:** [6a1819d](https://github.com/Sh-TB/sharpemuT24/commit/6a1819d)
- **Finding:** FAST_PATH=1 resolves semaphore deadlock — game reaches Unity game manager loading. New crash at RIP=0 (NULL execute).
- **Root Cause:** FAST_PATH=1 as workaround for deadlock
- **Status:** SUPERSEDED BY EXP-081
- **Related:** EXP-062, EXP-064, EXP-081
- **Impact:** FAST_PATH=1 was adopted as workaround. EXP-081 proves this was wrong — it causes the NULL execute crash by making workers race ahead of the dispatcher.

#### EXP-064 — NULL Execute Root Cause
- **Date:** 2026-07-31
- **Commit:** [202e54d](https://github.com/Sh-TB/sharpemuT24/commit/202e54d)
- **Finding:** NULL execute root cause = IL2CPP stubs return NULL. Host stack corruption after 1004 recoveries.
- **Status:** CONFIRMED
- **Related:** EXP-063, EXP-065

#### EXP-065 — Heap Allocation Fix (PARTIAL)
- **Date:** 2026-07-31
- **Commit:** [47274be](https://github.com/Sh-TB/sharpemuT24/commit/47274be)
- **Question:** Does heap allocation fix the stack corruption?
- **Finding:** Heap allocation fix for POSIX signal handler context buffer (stackalloc → NativeMemory.AllocZeroed). Stack smashing persists from deeper source.
- **Root Cause:** Partial: stackalloc replaced, but deeper corruption remains
- **Status:** PARTIAL
- **Related:** EXP-064, EXP-066
- **Impact:** Partial fix applied. This fix MAY have resolved the EXP-062 deadlock (by allowing signal handler to survive more invocations), but this was not proven until EXP-081.

#### EXP-066 — EXP-034 Re-patching Fails (SUPERSEDED)
- **Date:** 2026-07-31
- **Commit:** [137f3d7](https://github.com/Sh-TB/sharpemuT24/commit/137f3d7)
- **Finding:** Root cause = EXP-034 re-patching fails (0/232). Stubs use INT3 not DecideIl2cppReturnValue.
- **Status:** SUPERSEDED (by EXP-067)
- **Related:** EXP-065, EXP-067

#### EXP-067 — Re-patching Unnecessary
- **Date:** 2026-07-31
- **Commit:** [45af2a2](https://github.com/Sh-TB/sharpemuT24/commit/45af2a2)
- **Finding:** Re-patching unnecessary — resolver returns real addresses directly. NULL executes are task-submission issue.
- **Status:** CONFIRMED
- **Related:** EXP-066, EXP-068

#### EXP-068 — FAST_PATH Tension
- **Date:** 2026-07-31
- **Commit:** [936a53c](https://github.com/Sh-TB/sharpemuT24/commit/936a53c)
- **Finding:** FAST_PATH tension confirmed — SignalSema never called. Same root cause as EXP-036/062.
- **Status:** CONFIRMED
- **Related:** EXP-036, EXP-062, EXP-069

#### EXP-069 — SignalSema Never Called
- **Date:** 2026-07-31
- **Commit:** [3c60edc](https://github.com/Sh-TB/sharpemuT24/commit/3c60edc)
- **Finding:** SignalSema IS imported and implemented but NEVER called — code path issue.
- **Status:** CONFIRMED
- **Related:** EXP-068, EXP-070

### Phase 7: Gate/Dependency Investigation (EXP-070 to EXP-078)
*(All EXPs in this phase were conducted with the NOP bypass active — see EXP-080)*

#### EXP-070 — Gate Found
- **Date:** 2026-07-31
- **Commit:** [9304030](https://github.com/Sh-TB/sharpemuT24/commit/9304030)
- **Finding:** GATE FOUND — cmp byte [rbx+0x108], 0 + jne skips SignalSema. Flag=0x01 at runtime.
- **Status:** CONFIRMED
- **Related:** EXP-069, EXP-071

#### EXP-071 — [rbx+0x108] as Tagged Pointer (SUPERSEDED)
- **Date:** 2026-07-31
- **Commit:** [a59f6a6](https://github.com/Sh-TB/sharpemuT24/commit/a59f6a6)
- **Finding:** [rbx+0x108] is tagged pointer to unresolved dependency. CLEAR function never called.
- **Status:** SUPERSEDED BY EXP-079
- **Related:** EXP-070, EXP-072
- **Impact:** EXP-079 proved [rbx+0x108] is a byte flag (0x01), not a tagged pointer.

#### EXP-072 — NOP Gate Patch (DIAGNOSTIC)
- **Date:** 2026-07-31
- **Commit:** [3511466](https://github.com/Sh-TB/sharpemuT24/commit/3511466)
- **Finding:** NOP gate patch CONFIRMED — SignalSema fires, 0 NULL executes, 300x more execution.
- **Status:** CONFIRMED — DIAGNOSTIC PATCH
- **Related:** EXP-071, EXP-073
- **Impact:** Diagnostic patch. Not a permanent fix. Removed in EXP-080.

#### EXP-073 — 11-byte NOP (DIAGNOSTIC)
- **Date:** 2026-07-31
- **Commit:** [d1a90df](https://github.com/Sh-TB/sharpemuT24/commit/d1a90df)
- **Finding:** 11-byte NOP — SignalSema fires 13141 times, 0 NULL executes, 0 crashes. BUT signals wrong sema.
- **Status:** CONFIRMED — DIAGNOSTIC PATCH
- **Related:** EXP-072, EXP-074
- **Impact:** Created artificial execution path. Removed in EXP-080.

#### EXP-074 — Game Does NOT Reach Rendering
- **Date:** 2026-07-31
- **Commit:** [1204062](https://github.com/Sh-TB/sharpemuT24/commit/1204062)
- **Finding:** Game does NOT reach rendering — SignalSema fires on wrong handles.
- **Status:** CONFIRMED (NOP-contaminated)
- **Related:** EXP-073, EXP-075

#### EXP-075 — CLEAR Should Signal 0x5C (SUPERSEDED)
- **Date:** 2026-07-31
- **Commit:** [64b43b0](https://github.com/Sh-TB/sharpemuT24/commit/64b43b0)
- **Finding:** CLEAR function should signal 0x5C but async dependency never completes.
- **Status:** SUPERSEDED BY EXP-079
- **Related:** EXP-074, EXP-076

#### EXP-076 — Dependency is Chain Pointer (CORRECTED)
- **Date:** 2026-07-31
- **Commit:** [b0b641d](https://github.com/Sh-TB/sharpemuT24/commit/b0b641d)
- **Finding:** Dependency is chain ptr to prev worker. Root cause = missing GPU/graphics init.
- **Status:** CORRECTED BY EXP-077/079
- **Related:** EXP-075, EXP-077
- **Impact:** EXP-077 proved GPU init is NOT the blocker. EXP-079 proved [rbx+0x108] is a byte flag, not a chain pointer.

#### EXP-077 — GPU Init NOT the Blocker
- **Date:** 2026-07-31
- **Commit:** [a2982c9](https://github.com/Sh-TB/sharpemuT24/commit/a2982c9)
- **Finding:** GPU init is NOT the blocker — same semaphore spin class. Main thread reaches GPU memory alloc but stalls.
- **Status:** CONFIRMED
- **Related:** EXP-076, EXP-078

#### EXP-078 — Handle 0x5C Never Signaled (NOP-CONTAMINATED)
- **Date:** 2026-07-31
- **Commit:** [c839ae3](https://github.com/Sh-TB/sharpemuT24/commit/c839ae3)
- **Finding:** CASE 1 CONFIRMED — handle 0x5C NEVER signaled (0/5.7M).
- **Status:** CONFIRMED — BUT NOP-CONTAMINATED
- **Related:** EXP-077, EXP-079
- **Impact:** Finding was correct for the NOP-contaminated run. EXP-080 proved the NOP created an artificial execution path.

### Phase 8: Clean Run Validation (EXP-079 to EXP-081)

#### EXP-079 — Static Analysis Corrections
- **Date:** 2026-07-31
- **Commit:** [d13b8c9](https://github.com/Sh-TB/sharpemuT24/commit/d13b8c9)
- **Finding:** CLEAR is a C++ destructor (not a dependency callback). [rbx+0x108] is a byte flag (low byte 0x01), not a tagged pointer. Upper bytes are heap garbage. EXP-079's "array_proc corrupted count" claim was based on NOP-contaminated data and was retracted.
- **Status:** CONFIRMED
- **Related:** EXP-071, EXP-075, EXP-076, EXP-080

#### EXP-080 — A/B Test: Clean vs NOP
- **Date:** 2026-07-31
- **Commit:** [d13b8c9](https://github.com/Sh-TB/sharpemuT24/commit/d13b8c9)
- **Finding:** Clean run NEVER reaches il2cpp_init. 100,000+ NULL execute faults. EXP-079's "array_proc corrupted count" was NOP-contaminated and not reproducible. hash_table "corruption" was a false alarm (compared two different addresses: 0x801EF7610 vs 0x801EE7610).
- **Status:** CONFIRMED
- **Related:** EXP-079, EXP-081

#### EXP-081 — Root Cause: FAST_PATH=1
- **Date:** 2026-07-31
- **Commit:** [97db9fc](https://github.com/Sh-TB/sharpemuT24/commit/97db9fc)
- **Question:** Why are worker task function pointers [worker+0xF8] NULL?
- **Finding:** SHARPEMU_SEMA_FAST_PATH=1 causes WaitSema to return immediately, making workers race ahead of the dispatcher and call [worker+0xF8]=NULL. FAST_PATH=0 eliminates this: 0 NULL executes, il2cpp_init called, Unity job system starts, graphics threads created.
- **Root Cause:** FAST_PATH=1 (pending full validation)
- **Status:** CONFIRMED — PENDING VALIDATION
- **Related:** EXP-036, EXP-062, EXP-063, EXP-068
- **Impact:** Root cause found. FAST_PATH=0 proposed as fix. **Needs validation that EXP-062 deadlock doesn't recur with current codebase.**

---

## Phase Summary

| Phase | EXPs | Key Outcome |
|-------|------|-------------|
| 1. CPU/Resolver | 026-032 | Resolver algorithm and CPU emulation verified correct. Root cause: CpuContext.Rax not updated (fixed). |
| 2. NULL Execute | 033-036 | NULL executes from IL2CPP stubs. FAST_PATH=1 identified as causing il2cpp_init starvation (EXP-036). **This finding was lost and re-discovered in EXP-081.** |
| 3. IL2CPP Init | 037-052 | Investigated init_array, DT_INIT, hash table, metadata registration. **ALL INVALIDATED by EXP-061 (wrong dump).** |
| 4. Metadata Structs | 053-058 | Found Il2CppCodeRegistration and MetadataRegistration. **ALL INVALIDATED by EXP-061.** |
| 5. Dump Correction | 059-061 | Discovered dump was mixed (Dreaming Sarah eboot, not Yatzi). Complete dump fixes IL2CPP init. |
| 6. Semaphore/FAST_PATH | 062-069 | EXP-062 reported FAST_PATH=0 deadlock. EXP-063 adopted FAST_PATH=1 (wrong). EXP-065 applied partial stack fix. |
| 7. Gate/Dependency | 070-078 | Found gate at 0x800AA0207. Applied NOP bypass (diagnostic). **All NOP-contaminated.** |
| 8. Clean Validation | 079-081 | Corrected prior theories. Proved NOP contamination. Found root cause: FAST_PATH=1. |

---

## Key Corrections

### 1. EXP-061: Wrong Dump (Dreaming Sarah, not Yatzi)
- **Invalidated:** EXP-035 through EXP-058 (24 experiments)
- **Cause:** 7.7MB eboot.bin was from Dreaming Sarah, not Yatzi (32.7MB)
- **Lesson:** Always verify SHA256 of ALL game files before analysis

### 2. EXP-079: [rbx+0x108] is Byte Flag, Not Tagged Pointer
- **Corrected:** EXP-071 ("tagged pointer"), EXP-075 ("dependency pointer"), EXP-076 ("chain pointer")
- **Truth:** Low byte 0x01 = work-pending flag. Upper 7 bytes = uninitialized heap garbage.
- **Proof:** Every read is `cmp byte [rbx+0x108], 0`. Every write is `mov byte [rbx+0x108], <imm8>`.

### 3. EXP-079: CLEAR is C++ Destructor, Not Dependency Callback
- **Corrected:** EXP-075 ("CLEAR should signal 0x5C"), EXP-076 ("CLEAR clears dependency")
- **Truth:** CLEAR (0x800A9F750) is a C++ destructor for the worker pool singleton. It calls scePthreadMutexDestroy, sceKernelDeleteSema, frees worker descriptors. Only invoked during pool teardown (process exit).

### 4. EXP-077: GPU Init NOT the Blocker
- **Corrected:** EXP-076 ("root cause = missing GPU/graphics init")
- **Truth:** GPU init is downstream. Main thread reaches sceKernelAllocateDirectMemory but stalls before reaching il2cpp_init.

### 5. EXP-080: NOP Bypass Created Artificial Execution Path
- **Corrected:** EXP-073/074/075/076/077/078 (all conducted with NOP active)
- **Truth:** The 11-byte NOP at 0x800AA0207 prevented workers from crashing on NULL [rbx+0xF8], but redirected them to signal the wrong semaphore. This created an artificial execution path that allowed the main thread to progress further than it naturally would.

### 6. EXP-080: hash_table "Corruption" Was False Alarm
- **Corrected:** EXP-080's own initial claim of "hash_table corruption"
- **Truth:** Compared values from two DIFFERENT addresses: 0x801EF7610 (EXP058 tracer) vs 0x801EE7610 (EXP039 tracer). These differ by 64KB and are NOT the same variable.

### 7. EXP-081: FAST_PATH=1 is the Real Root Cause
- **Corrected:** EXP-063 (adopted FAST_PATH=1 as workaround)
- **Truth:** FAST_PATH=1 makes WaitSema return immediately, causing workers to race ahead of the dispatcher and call [worker+0xF8]=NULL. FAST_PATH=0 eliminates this entirely.
- **Note:** EXP-036 already discovered this in 2026-07-29, but EXP-063 overrode it. The finding was lost for 2 days and re-discovered in EXP-081.

---

## Current State (after EXP-081)

### What is Solved
- IL2CPP symbol resolver works correctly (EXP-032)
- Complete game dump verified (EXP-060/061)
- IL2CPP init works with correct dump + FAST_PATH=0 (EXP-081)
- Worker NULL [rbx+0xF8] crash eliminated with FAST_PATH=0 (EXP-081)

### What is Proven
- FAST_PATH=1 causes workers to race ahead of dispatcher → NULL crash (EXP-036, EXP-081)
- FAST_PATH=0 eliminates NULL execute crashes entirely (EXP-081)
- With FAST_PATH=0: il2cpp_init called, Unity job system starts, graphics threads created (EXP-081)
- NOP bypass is NOT needed and creates artificial execution paths (EXP-080)
- GPU init is downstream, not causal (EXP-077)

### What is Still Blocked (PENDING VALIDATION)
**CRITICAL:** EXP-062 reported that FAST_PATH=0 causes deadlock (SignalSema never called). EXP-081's FAST_PATH=0 run showed 18 SignalSema calls and no deadlock — BUT this needs full validation:
- Does the game progress past the EXP-062 deadlock point?
- Are worker semaphores (0x5C, 0x5E, ...) eventually signaled?
- Does the game reach sceVideoOutOpen?

### Current Crash Location (with FAST_PATH=0)
- **Address:** 0x80080684D
- **Instruction:** `mov r8d, [r15+rcx]` where r15=NULL
- **Type:** NULL pointer dereference in Unity IL2CPP metadata iteration
- **Classification:** UNKNOWN — needs to determine if this is before or after the EXP-062 deadlock point

### Exact Next Debugging Target
1. **Validate FAST_PATH=0:** Run with semaphore statistics logging. Confirm worker semaphores (0x5C, 0x5E, ...) are eventually signaled. Confirm game progresses past EXP-062 deadlock point.
2. **Classify crash at 0x80080684D:** Is it Case A (after EXP-062 deadlock point — FAST_PATH=0 genuinely moved forward) or Case B (before — deadlock still exists)?
3. **If Case A:** Investigate 0x80080684D crash (NULL ptr in Unity metadata) as EXP-082.
4. **If Case B:** Investigate why SignalSema is never called (semaphore synchronization chain).

---

## Knowledge Rules Learned

### 1. Always verify game file identity
- **Rule:** SHA256 of eboot.bin, PRX, and metadata MUST be verified before any analysis.
- **Reason:** EXP-061 found that 24 experiments (EXP-035..058) were wasted on the wrong game dump.
- **Action:** Run `sha256sum` on all game files before starting any EXP.

### 2. Never treat temporary patches as fixes
- **Rule:** NOP patches, FAST_PATH=1, and other bypasses are DIAGNOSTIC ONLY.
- **Reason:** EXP-073's NOP bypass masked the real issue for 8 experiments (EXP-073..080).
- **Action:** Mark all diagnostic patches clearly. Remove them before drawing conclusions.

### 3. Always run clean A/B tests
- **Rule:** Any finding obtained with a patch active must be re-verified without the patch.
- **Reason:** EXP-080 proved that EXP-079's "corrupted count" finding was NOP-contaminated.
- **Action:** Remove all patches, rebuild, re-run, compare.

### 4. Environment variables can invalidate experiments
- **Rule:** Track ALL environment variables. A single env var change can invalidate results.
- **Reason:** FAST_PATH=1 vs FAST_PATH=0 completely changes the execution path.
- **Action:** Record env vars in every EXP report. Verify they match between runs.

### 5. Never trust a single memory dump without wider range validation
- **Rule:** A single memory value at one address does not prove a pattern.
- **Reason:** EXP-080's "hash_table corruption" was caused by comparing two different addresses.
- **Action:** Always verify which address a value comes from. Check neighboring addresses.

### 6. Every root cause requires reproduction
- **Rule:** A root cause claim must be reproducible in a clean run.
- **Reason:** EXP-079's "array_proc corrupted count" was not reproducible without the NOP.
- **Action:** Reproduce the finding in a clean environment before accepting it.

### 7. Address typos can cause wasted work
- **Rule:** Similar-looking addresses (e.g., 0x801EF7610 vs 0x801EE7610) must be explicitly distinguished.
- **Reason:** This specific typo (EF vs EE) caused wasted analysis TWICE (EXP-053, EXP-080).
- **Action:** When comparing values from different tracers, verify they read from the same address.

### 8. Log throttling can hide true counts
- **Rule:** `grep -c` counts LOG LINES, not events. Throttled logging undercounts.
- **Reason:** EXP-080 reported "1005 NULL executes" but the actual count was 100,000+ (logging throttles after #1000).
- **Action:** Check for throttling. Use the highest numbered event, not line count.

### 9. Don't override correct findings without proof
- **Rule:** If an EXP finds a root cause, don't override it without disproving it first.
- **Reason:** EXP-036 correctly identified FAST_PATH=1 as the problem. EXP-063 overrode this without disproving it, switching back to FAST_PATH=1. This wasted 18 experiments (EXP-063..080).
- **Action:** Before overriding a finding, explicitly disprove it with evidence.

### 10. Preserve both original and corrected conclusions
- **Rule:** When correcting an EXP, keep both the original and corrected versions.
- **Reason:** Future agents need to understand what was tried and why it was wrong.
- **Action:** Mark corrections explicitly. Never delete old conclusions.

---

## All Links

### GitHub Issues
- [Issue #1: EXP-081 Root Cause](https://github.com/Sh-TB/sharpemuT24/issues/1)

### Key Commits
- [EXP-026/027/028: CPU/Resolver verification](https://github.com/Sh-TB/sharpemuT24/commit/08c0735)
- [EXP-032: CpuContext.Rax fix](https://github.com/Sh-TB/sharpemuT24/commit/4b920fe)
- [EXP-036: FAST_PATH=1 starvation (first discovery)](https://github.com/Sh-TB/sharpemuT24/commit/7986cbe)
- [EXP-061: Mixed dump detected](https://github.com/Sh-TB/sharpemuT24/commit/b28cce2)
- [EXP-062: FAST_PATH=0 deadlock report](https://github.com/Sh-TB/sharpemuT24/commit/89ad82e)
- [EXP-063: FAST_PATH=1 adopted (wrong)](https://github.com/Sh-TB/sharpemuT24/commit/6a1819d)
- [EXP-065: Heap allocation fix](https://github.com/Sh-TB/sharpemuT24/commit/47274be)
- [EXP-073: 11-byte NOP diagnostic](https://github.com/Sh-TB/sharpemuT24/commit/d1a90df)
- [EXP-079/080: NOP removed, clean A/B test](https://github.com/Sh-TB/sharpemuT24/commit/d13b8c9)
- [EXP-081: FAST_PATH=1 root cause](https://github.com/Sh-TB/sharpemuT24/commit/97db9fc)

### EXP Report Files
All EXP reports are in `docs/diagnostics/EXP-*.md` in the repository.

### Other Key Files
- `docs/diagnostics/worklog.md` — Running worklog of all EXPs
- `docs/diagnostics/YATZI_EXP_INDEX.md` — Quick-reference table
- `docs/diagnostics/YATZI_KNOWLEDGE_BASE.md` — Detailed per-EXP listing
- `SHARPEMU_KNOWLEDGE_BASE.md` — General SharpEmu knowledge
- `AI_CONTEXT.md` — AI agent context
- `PROJECT_HANDOFF.md` — Project handoff document

---

## Current True Blocker

**PENDING VALIDATION:**

EXP-081 proposes `SHARPEMU_SEMA_FAST_PATH=0` as the fix for the worker NULL `[rbx+0xF8]` crash. This eliminates 100,000+ NULL execute faults and allows the game to reach il2cpp_init + Unity job system + graphics threads.

**However, EXP-062 reported that FAST_PATH=0 causes a deadlock** (SignalSema never called, all threads blocked). EXP-081's run showed 18 SignalSema calls and no deadlock — but this may be because the game crashed (at 0x80080684D) before reaching the deadlock point.

**The validation that must happen before EXP-082:**
1. Run with FAST_PATH=0 and full semaphore statistics
2. Confirm worker semaphores (0x5C, 0x5E, 0x60, ...) are eventually signaled
3. Confirm the game progresses past the EXP-062 deadlock point
4. Classify the crash at 0x80080684D as Case A (after deadlock point) or Case B (before)

If Case A: FAST_PATH=0 is validated. The new blocker is the 0x80080684D crash (EXP-082).
If Case B: The semaphore deadlock from EXP-062 still exists. The SignalSema source must be investigated.


---

## EXP-082 (added 2026-07-31)

### EXP-082 — Crash at 0x80080684D: NULL Per-Image Hash Table
- **Date:** 2026-07-31
- **Commit:** [a922906](https://github.com/Sh-TB/sharpemuT24/commit/a922906)
- **Question:** Why does the game crash at 0x80080684D (mov r8d, [r15+rcx] where r15=NULL)?
- **Finding:** The crash is a NULL per-image hash table dereference. r15 = rdi = [r12+0x278] where r12 is an IL2CPP image object. The per-image hash table at [image+0x278] was never initialized because the IL2CPP metadata registration process is incomplete. This is downstream of EXP-053's wrapper-never-called issue.
- **Root Cause:** IL2CPP metadata registration wrapper (0x800805AE0) is never called → per-image hash tables stay NULL → hash lookup crashes
- **Status:** CONFIRMED
- **Related:** EXP-053, EXP-056, EXP-052
- **Impact:** The crash is NOT a new bug — it's the next symptom of the still-open EXP-053 mechanism. Fix requires completing the IL2CPP registration chain in SharpEmu HLE.

### Updated Current State (after EXP-082)

**Solved:**
- Worker NULL [rbx+0xF8] crash (FAST_PATH=0, EXP-081)
- il2cpp_init reaches successfully (FAST_PATH=0, EXP-081)
- Unity job system starts (FAST_PATH=0, EXP-081)
- Graphics threads created (FAST_PATH=0, EXP-081)

**Still blocked:**
- IL2CPP metadata registration incomplete (EXP-053/082)
- Per-image type hash tables not initialized (EXP-082)
- Crash at 0x80080684D when Unity tries type lookup (EXP-082)
- Rendering not reached (sceVideoOutOpen never called)

**Current crash location:** 0x80080684D (NULL per-image hash table)
**Next debugging target:** Find what should trigger the metadata registration wrapper at 0x800805AE0 and why it's never reached (EXP-083)


---

## EXP-083 (added 2026-07-31)

### EXP-083 — Metadata Global 0x801E51240 Never Populated
- **Date:** 2026-07-31
- **Commit:** [acd9271](https://github.com/Sh-TB/sharpemuT24/commit/acd9271)
- **Resumes:** EXP-057 (abandoned when EXP-061 found wrong dump)
- **Question:** Where should the call to wrapper 0x800805AE0 happen, and why is metadata registration not completing?
- **Finding:** The wrapper at 0x800805AE0 is a #dllimport: string parser, NOT il2cpp_codegen_register (EXP-052/053 misidentified it). The actual root cause is that the metadata global at 0x801E51240 is never populated because hash_lookup (0x8004BD620) returns NULL, causing the conditional write at 0x8013EF019 to be skipped. crash_func (0x80135DDD0) reads the NULL global and crashes at [NULL+0x98].
- **Root Cause:** hash_lookup returns NULL → metadata global stays NULL → crash_func crashes
- **Status:** CONFIRMED
- **Related:** EXP-041, EXP-042, EXP-053, EXP-057, EXP-082
- **Impact:** Root cause of the crash at 0x80080684D (and the earlier crash at 0x80135DE83) is that the IL2CPP metadata hash table has 0 populated entries. The hash table structure exists (0x600103DB0) but no entries were inserted. Fix requires finding what should populate the hash table entries.

### Updated Current State (after EXP-083)

**Solved:**
- Worker NULL [rbx+0xF8] crash (FAST_PATH=0, EXP-081)
- il2cpp_init reaches successfully (FAST_PATH=0, EXP-081)
- Unity job system starts (FAST_PATH=0, EXP-081)
- Graphics threads created (FAST_PATH=0, EXP-081)
- EXP-053 wrapper mystery resolved — it's a #dllimport: parser, not il2cpp_codegen_register

**Still blocked:**
- IL2CPP metadata hash table has 0 populated entries (EXP-041/083)
- Metadata global at 0x801E51240 stays NULL (EXP-083)
- crash_func crashes at [NULL+0x98] (EXP-083)
- Rendering not reached

**Current crash location:** 0x80135DE83 (crash_func reads NULL metadata global)
**Next debugging target:** Trace hash_lookup to find what key it searches for and why entries are empty (EXP-084)


---

## EXP-084 (added 2026-07-31)

### EXP-084 — Metadata List Flag Bug: Premature Searchable Entries
- **Date:** 2026-07-31
- **Commit:** [49ad4b8](https://github.com/Sh-TB/sharpemuT24/commit/49ad4b8)
- **Resumes:** EXP-039/040/041/046 (hash table population thread, abandoned when EXP-061 found wrong dump)
- **Question:** What key does hash_lookup search for, and why are entries empty?
- **Finding:** The crash is NOT caused by empty hash table entries. It is caused by prematurely searchable metadata list entries. The metadata list at [0x801EA4E80] has entries with flag=0x00 at offset +0x19. metadata_lookup (0x800C66B40) checks this flag: if 0, it searches and returns non-zero; if non-zero, it returns 0. On real PS5, the flag would be non-zero (not searchable), causing the lookup to return 0. On SharpEmu, flag=0 → lookup finds match → returns non-zero → callback calls crash_func → crash.
- **Root Cause:** Metadata list entries have flag=0x00 (searchable) when they should have flag!=0 (not searchable) before il2cpp_init runs.
- **Status:** CONFIRMED
- **Related:** EXP-039, EXP-040, EXP-041, EXP-046, EXP-083
- **Impact:** Root cause fully mapped since EXP-040/046. The fix is to set [entry+0x19]=1 before il2cpp_init. This makes metadata_lookup return 0, matching real PS5 behavior.

### Updated Current State (after EXP-084)

**Solved:**
- Worker NULL [rbx+0xF8] crash (FAST_PATH=0, EXP-081)
- il2cpp_init reaches successfully (FAST_PATH=0, EXP-081)
- Unity job system starts (FAST_PATH=0, EXP-081)
- Graphics threads created (FAST_PATH=0, EXP-081)
- EXP-053 wrapper mystery resolved (EXP-083: it's a #dllimport: parser)
- Metadata global NULL root cause identified (EXP-083/084: flag=0x00 on list entries)

**Still blocked:**
- Metadata list entries have flag=0x00 (should be non-zero before il2cpp_init)
- metadata_lookup returns non-zero → callback crashes
- Rendering not reached

**Current crash location:** 0x80135DE83 (crash_func reads NULL metadata global)
**Proposed fix:** Set [metadata_list_entry+0x19]=1 before il2cpp_init
**Next debugging target:** Apply the fix and verify game progresses (EXP-085)


---

## EXP-085 (added 2026-07-31)

### EXP-085 — Metadata Flag Patch: Crash Eliminated, VideoOut Reached
- **Date:** 2026-07-31
- **Commit:** [f2b5870](https://github.com/Sh-TB/sharpemuT24/commit/f2b5870)
- **Question:** Does setting [metadata_list_entry+0x19]=1 before il2cpp_init allow the game to progress?
- **Finding:** YES. The patch eliminates the crash at 0x80135DE83. metadata_lookup returns 0 (matching real PS5). il2cpp_init completes. Game reaches VideoOut initialization — the furthest progress ever achieved for Yatzi. New crash at 0x80080684D (per-image hash table, separate issue) occurs AFTER VideoOut.
- **Root Cause:** CONFIRMED — metadata list entries had flag=0x00 (searchable) when they should be non-zero
- **Status:** CONFIRMED — patch works, progress proven
- **Related:** EXP-040, EXP-041, EXP-046, EXP-082, EXP-083, EXP-084
- **Impact:** MAJOR MILESTONE — first time Yatzi reaches VideoOut. The metadata flag fix is the correct fix for the crash_func crash. The remaining crash at 0x80080684D is a separate per-image hash table issue.

### Updated Current State (after EXP-085)

**Solved:**
- Worker NULL [rbx+0xF8] crash (FAST_PATH=0, EXP-081)
- il2cpp_init reaches and completes (FAST_PATH=0 + metadata flag patch, EXP-085)
- Metadata lookup returns correct value (0, matching real PS5) (EXP-085)
- crash_func crash at 0x80135DE83 eliminated (EXP-085)
- Unity job system starts (EXP-081/085)
- Graphics threads created (EXP-081/085)
- **VideoOut reached** (EXP-085) ← FIRST TIME

**Still blocked:**
- Per-image hash table at [image+0x278] is NULL (EXP-082, separate issue)
- Crash at 0x80080684D when Unity tries type lookup (EXP-082)
- X11 display :99 not available for GLFW (host-side config issue)
- Rendering not yet achieved

**Current crash location:** 0x80080684D (per-image hash table NULL, AFTER VideoOut attempt)
**Next debugging target:** Fix X11 display, then check if per-image hash table crash persists (EXP-086)


---

## Metadata File Validation (2026-07-31, post-EXP-085)

### External Claim Validation

An external observation claimed global-metadata.dat has:
- Magic: 0xFAB11BAF
- Version: 29
- Types: 468,472
- Strings: 1,613,544
- Methods: 80,736

### Verification Results

**CHECK 1 — File identity:**
- Path: `/tmp/games/yatzi/global-metadata.dat` (root) + `/tmp/games/yatzi/Media/Metadata/global-metadata.dat` (copy)
- SHA256: `4c85fdec4efdb59534ab20af49615a36cbeef549f2f8de0431d78dbc5f21d918`
- Size: 10,669,264 bytes
- Magic: 0xFAB11BAF ✓ (matches)
- Version: 29 ✓ (matches)
- String table byte size: 1,613,544 ✓ (matches external "strings" claim)
- Type definitions byte size: 1,142,064 (external "types=468,472" is a different metric — likely element count using a different struct size)
- Methods byte size: 2,695,968 (external "methods=80,736" is a different metric — likely element count)

**CHECK 2 — SharpEmu loads it:**
- SharpEmu's BootDependencyAnalyzer checks `Media/Metadata/global-metadata.dat`
- WITHOUT file at Media/Metadata/: "Exists: NO, Status: MISSING"
- WITH file at Media/Metadata/: "Exists: YES, Size: 10.2 MB"
- SharpEmu does NOT parse the file itself — the PRX (Il2cppUserAssemblies.prx) loads it via sceOpen

**CHECK 3 — File vs runtime metadata:**
- Cannot directly compare — SharpEmu doesn't parse metadata fields internally
- The PRX parses the metadata file internally during il2cpp_init

**CHECK 4 — Registration path consumes the data:**
- WITHOUT file at Media/Metadata/: PRX takes fallback path → crash at 0x80080684D (per-image hash table NULL) — but reaches VideoOut first
- WITH file at Media/Metadata/: PRX reads file → proper init path → DEADLOCK (EXP-062 pattern: all 14 threads blocked on WaitSema, main thread on handle 0x83)

### Conclusion

The external metadata claim is **CORRECT and RELEVANT**. The file exists, is valid (magic/version match), and IS loaded by the PRX. The string table byte size matches exactly.

However, loading the metadata correctly leads to the **EXP-062 deadlock** (all threads blocked on WaitSema). NOT loading it (file at wrong path) leads to a different crash (0x80080684D) but allows further progress (reaches VideoOut).

This is **supporting evidence only**, not a root cause. The metadata file is valid and consumed correctly by the PRX. The blocker is the semaphore synchronization deadlock that occurs after the metadata is loaded.

### Important Discovery: File Path Matters

The file was originally at the ROOT (`/tmp/games/yatzi/global-metadata.dat`) but SharpEmu expects it at `Media/Metadata/global-metadata.dat`. This path mismatch caused the PRX to take a different code path:
- Wrong path → PRX can't find metadata → fallback init → crash at 0x80080684D → but reaches VideoOut
- Correct path → PRX reads metadata → proper init → deadlock (EXP-062 pattern)

This means the EXP-085 run that reached VideoOut was actually running with the metadata file NOT being found by the PRX. The "progress" to VideoOut was on a fallback code path, not the normal init path.


---

## Golden Rule Validation (2026-07-31)

### Golden Rule 1 — File Exists

```
Hypothesis: global-metadata.dat exists and is valid
Evidence:
  Location 1: /tmp/games/yatzi/global-metadata.dat (root, original extraction)
    Size: 10,669,264 bytes
    SHA256: 4c85fdec4efdb59534ab20af49615a36cbeef549f2f8de0431d78dbc5f21d918
  Location 2: /tmp/games/yatzi/Media/Metadata/global-metadata.dat (copy, created during validation)
    Size: 10,669,264 bytes
    SHA256: 4c85fdec4efdb59534ab20af49615a36cbeef549f2f8de0431d78dbc5f21d918
  Both copies are identical (same SHA256).
Conclusion: CONFIRMED — file exists, valid, two identical copies
```

### Golden Rule 2 — Loader Path

```
Hypothesis: The PRX expects global-metadata.dat at Media/Metadata/ (relative to /app0/)
Evidence:
  - PRX (Il2cppUserAssemblies.prx) contains string "global-metadata.dat" (filename only)
  - PRX contains string "/app0/" (base path)
  - PRX contains string "Metadata" (directory component)
  - EBOOT contains string "/app0/" at offset 0x1BBB235
  - SharpEmu's BootDependencyAnalyzer checks "Media/Metadata/global-metadata.dat"
  - With file at Media/Metadata/: PRX takes proper init path (deadlock, different behavior)
  - Without file at Media/Metadata/: PRX takes fallback path (crash at 0x80080684D)
  - The different behavior proves the file IS found at Media/Metadata/ when present
Conclusion: CONFIRMED — expected loader path is /app0/Media/Metadata/global-metadata.dat
  Host path: /tmp/games/yatzi/Media/Metadata/global-metadata.dat
  Match: YES (file exists at expected location)
```

### Golden Rule 3 — Metadata Header

```
Hypothesis: global-metadata.dat has valid IL2CPP v29 header
Evidence:
  Magic: 0xFAB11BAF (expected: 0xFAB11BAF) ✓
  Version: 29 (expected: 29) ✓
  String table byte size: 1,613,544
  Type definitions byte size: 1,142,064
  Methods byte size: 2,695,968
  Images byte size: 4,160
  Assemblies byte size: 6,656
Conclusion: CONFIRMED — valid IL2CPP v29 metadata file
```

### Golden Rule 4 — Test A vs Test B

```
Hypothesis: Behavior differs when metadata file is found vs not found
Evidence:

Test A (metadata NOT at Media/Metadata/):
  - PRX cannot find file → takes fallback init path
  - il2cpp_init called but uses fallback metadata handling
  - metadata_lookup returns 0 (with EXP-085 flag patch)
  - Game reaches VideoOut (GPU detected, Vulkan selected)
  - Crashes at 0x80080684D (per-image hash table NULL)
  - 36+ threads created (Job.workers, Gfx threads)
  - Exit code: 139 (SIGSEGV)

Test B (metadata at Media/Metadata/):
  - PRX finds and reads file → takes proper init path
  - il2cpp_init called with real metadata
  - metadata_lookup NOT reached (different code path)
  - Game does NOT reach VideoOut
  - DEADLOCK: all 14 threads blocked on WaitSema
  - Main thread blocked on handle 0x83 at ret=0x804FB5BAF
  - Workers blocked on handles 0x5C, 0x5E, etc.
  - Exit code: 4 (stall)

  | Metric | Test A (no Media/Metadata/) | Test B (with Media/Metadata/) |
  |--------|---------------------------|------------------------------|
  | File found by PRX | NO | YES |
  | il2cpp_init | YES | YES |
  | metadata_lookup | returns 0 (patched) | not reached |
  | VideoOut | REACHED | NOT reached |
  | Job.workers | 29 | 0 |
  | Gfx threads | 3 | 0 |
  | Result | SIGSEGV at 0x80080684D | Deadlock (all blocked) |
  | Exit code | 139 | 4 |

Conclusion: CONFIRMED — behavior differs significantly.
  - Without metadata: fallback path → crash but reaches VideoOut
  - With metadata: proper path → deadlock (EXP-062 pattern)
```

### Golden Rule 5 — Answers to Questions

```
Q1: Do we actually have a valid global-metadata.dat?
A: YES. Magic 0xFAB11BAF, version 29, SHA256 4c85fdec..., 10.7MB.

Q2: Is it located where the loader expects it?
A: YES, when placed at Media/Metadata/global-metadata.dat.
   The original extraction put it at the root, which is NOT where the PRX looks.
   A copy was placed at Media/Metadata/ during validation.

Q3: Is SharpEmu running the real metadata initialization path or a fallback path?
A: BOTH paths have been tested:
   - Without Media/Metadata/ copy: FALLBACK path (PRX can't find file)
   - With Media/Metadata/ copy: REAL path (PRX reads file)
   The EXP-085 run that reached VideoOut was on the FALLBACK path.

Q4: Does behavior change between metadata missing vs metadata correctly loaded?
A: YES, significantly:
   - Missing: crash at 0x80080684D, but reaches VideoOut (fallback path)
   - Loaded: deadlock (all threads blocked on WaitSema) — EXP-062 pattern
   The correct metadata loading leads to the semaphore deadlock.
```

### Impact on Current Understanding

The metadata validation does NOT change our current understanding. The key findings are:

1. The metadata file is valid and IS loaded by the PRX when placed at the correct path
2. Correct loading leads to the EXP-062 deadlock (semaphore synchronization issue)
3. The EXP-085 "VideoOut reached" milestone was on the FALLBACK path (metadata not found)
4. The real blocker when metadata is correctly loaded is the semaphore deadlock, not the metadata

This is supporting evidence only. The metadata file is not the root cause — the semaphore synchronization is.


---

## EXP-086 (added 2026-07-31)

### EXP-086 — Path B Deadlock Analysis: Main Thread Goes Silent After AllocateDirectMemory
- **Date:** 2026-07-31
- **Commit:** [1c26932](https://github.com/Sh-TB/sharpemuT24/commit/1c26932)
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active
- **Path:** B (real metadata path)
- **Question:** What is the main thread doing after `sceKernelAllocateDirectMemory`, and why does it stops making progress?
- **Hypothesis:** Main thread is in a long PRX computation or an error-retry loop caused by failed HLE imports.
- **Tools/Logs:** Stall report, import trace, sema statistics
- **Finding:** Stall detector shows main thread NOT blocked — running but silent after `Import#79360` (`sceKernelAllocateDirectMemory`). All 14 other threads (13 workers + 1 GC) are blocked on their semaphores. Import errors observed: `sceKernelVirtualQuery` NOT_FOUND, `sceKernelDirectMemoryQuery` NOT_FOUND, `fopen` NOT_FOUND, `scePadDeviceClassGetExtendedInformation` UNRESOLVED, unknown NID `1-LFLmRFxxM` PERMISSION_DENIED.
- **Root Cause:** Preliminary — main thread appears to be in a PRX computation or error path; root cause not yet identified.
- **Status:** CONFIRMED (symptom) — but root cause was WRONG (corrected in EXP-087)
- **Related:** EXP-085, EXP-087
- **Impact:** Identified the exact point of main-thread silence (`sceKernelAllocateDirectMemory`). Captured thread states and import errors for downstream EXPs.

### Updated Current State (after EXP-086)
**Solved:** Path B reaches `sceKernelAllocateDirectMemory` — GPU memory allocated.
**Still blocked:** Main thread silent after `AllocateDirectMemory`. All workers + GC thread blocked. No crashes.
**Next debugging target:** Is the main thread in a spinlock/retry loop, or making slow forward progress in PRX code? (EXP-087)


---

## EXP-087 (added 2026-07-31)

### EXP-087 — Main Thread Blocked on WaitSema(0x81): All 15 Threads Deadlocked
- **Date:** 2026-07-31
- **Commit:** [bc9f963](https://github.com/Sh-TB/sharpemuT24/commit/bc9f963)
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What is the main thread doing after `sceKernelAllocateDirectMemory`?
- **Hypothesis:** Re-examine stall snapshot for main thread state.
- **Tools/Logs:** Stall detector snapshot (already in EXP-086 log, but not analyzed)
- **Finding:** Main thread IS blocked — on `sceKernelWaitSema(handle=0x81)`. The stall snapshot captured: `rip=0x6FFFFD001150` (WaitSema import stub), `rdi=0x6FFF00000081` (handle 0x81), `ret=0x804F6E9EB` (PRX vaddr 0x2999EB). ALL 15 threads blocked. Handle 0x81 = `Baselib_SystemSemaphore`, created alongside 0x80, 0x82, right before GC semaphores 0x83, 0x84. 0 `sema.signal` entries for any of 0x5C..0x74, 0x81, 0x83 in entire log.
- **Root Cause:** True all-threads-deadlock — nobody signals handle 0x81.
- **Status:** CONFIRMED
- **Related:** EXP-086 (corrected), EXP-088
- **Impact:** Re-classified deadlock from "main thread running silently" to "main thread blocked on WaitSema(0x81)". The stall detector's `Stall snapshot` line was always there but had been overlooked.

### Correction
EXP-086 said "main thread is NOT blocked — it's running." **WRONG.** The stall detector lists only HLE-handler-blocked threads; the main thread is in the import-stub path and was missed. **Corrected:** ALL 15 threads are blocked — true deadlock.

### Updated Current State (after EXP-087)
**Solved:** Identified exact semaphore handle blocking main thread (0x81 = `Baselib_SystemSemaphore`).
**Still blocked:** Nobody signals handle 0x81. All 15 threads deadlocked.
**Next debugging target:** What PRX function calls `WaitSema(0x81)` at `0x804F6E9EB`, and what should signal it? (EXP-088)


---

## EXP-088 (added 2026-07-31)

### EXP-088 — Semaphore 0x81 Owner: IL2CPP ThreadPool Work-Available Semaphore
- **Date:** 2026-07-31
- **Commit:** [eca949c](https://github.com/Sh-TB/sharpemuT24/commit/eca949c)
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What PRX function calls `WaitSema(0x81)` at `0x804F6E9EB`, and what code should call `SignalSema(0x81)`?
- **Hypothesis:** Handle 0x81 belongs to a specific IL2CPP subsystem with a known signal site.
- **Tools/Logs:** Static analysis (disassembly of WaitSema/SignalSema callers, thread-pool dispatch loop)
- **Finding:** Handle 0x81 is the **IL2CPP ThreadPool work-available semaphore**. WaitSema caller = `0x804F6E510` (PRX vaddr 0x299510, ThreadPool dispatch function, confirmed by strings `"IL2CPP Threadpool worker"`, `"ThreadPool"`). Handle loaded from `[r14+0x88]` (thread-pool context). SignalSema caller at `0x804F6ECF9` is in the SAME function — invoked only when an atomic CAS on `[entry+0x90]` succeeds AND the work delta is negative (worker needs wake). 181 total callers of the SignalSema wrapper in the PRX; only 1 uses offset `+0x88`. SignalSema never fires because **no work is ever submitted to the thread pool**.
- **Root Cause:** No work is submitted to the IL2CPP ThreadPool — the CAS at `0x804F6EC75` never succeeds — `SignalSema(0x81)` never called.
- **Status:** CONFIRMED
- **Related:** EXP-087, EXP-089
- **Impact:** Re-classified deadlock from "missing signal" to "missing work submission". The fix is NOT to force `SignalSema(0x81)` (would wake main thread with garbage work) — the fix is to find what should submit work to the pool.

### Updated Current State (after EXP-088)
**Solved:** Semaphore 0x81 ownership = IL2CPP ThreadPool work-available. SignalSema exists but is gated on work being submitted.
**Still blocked:** No work submitted to the thread pool — main thread enters pool and waits forever.
**Next debugging target:** What prevents the IL2CPP runtime from submitting work to the thread pool after allocating GPU memory? (EXP-089)


---

## EXP-089 (added 2026-07-31)

### EXP-089 — Missing Work Submission: Main Thread Enters ThreadPool Without Queuing Work
- **Date:** 2026-07-31
- **Commit:** [5ee1a46](https://github.com/Sh-TB/sharpemuT24/commit/5ee1a46)
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What prevents IL2CPP from submitting work to the ThreadPool after `sceKernelAllocateDirectMemory`?
- **Hypothesis:** An HLE error or missing trigger prevents the runtime from reaching the work submission stage.
- **Tools/Logs:** Log timeline analysis (line-by-line HLE calls and semaphore operations)
- **Finding:** Only 18 log lines between `sceKernelAllocateDirectMemory` (line 8905) and the deadlock (line 8923). Main thread creates GC system (lines 8906-8907), thread-pool semaphores 0x85-0x90 (lines 8908-8918), GC thread (line 8922), then IMMEDIATELY enters the pool as a worker and blocks on `WaitSema(0x81)` (line 8923). No work is queued between GC creation and pool entry. 0 sema.signal calls in this window. The missing work submission is likely a GC trigger, IL2CPP runtime callback, or timer/event that SharpEmu doesn't generate.
- **Root Cause (preliminary):** Classification D — Unity/IL2CPP waiting for an event SharpEmu never generates.
- **Status:** CONFIRMED — but classification was CORRECTED in EXP-090
- **Related:** EXP-088, EXP-090
- **Impact:** Pinned the missing transition down to an 18-line window. Eliminated the EXP-058 "2.45 billion entries" bug — the tracer was dividing a pointer by entry_size; the actual count is `rcx=0x379=889`.

### Correction
EXP-058/079 reported `array_proc count=2454267240`. **WRONG** — tracer bug (rsi is a pointer, not count*entry_size). **Corrected:** count = `rcx=0x379=889`.

### Updated Current State (after EXP-089)
**Solved:** Pinned missing work submission to an 18-line window. Tracer bug for array_proc count corrected.
**Still blocked:** Unknown what event should trigger work submission.
**Next debugging target:** What event should trigger IL2CPP runtime to submit work to the ThreadPool after GC system creation? (EXP-090)


---

## EXP-090 (added 2026-07-31)

### EXP-090 — Missing Trigger: _ThreadPoolWaitCallback Lookup Returns NULL Due to Empty Hash Table
- **Date:** 2026-07-31
- **Commit:** [431fdf5](https://github.com/Sh-TB/sharpemuT24/commit/431fdf5)
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What event should trigger the first IL2CPP ThreadPool work submission?
- **Hypothesis:** The missing trigger is a function pointer that the IL2CPP runtime looks up via the metadata hash table.
- **Tools/Logs:** Static analysis of `real_init` (`0x804F04BA0`) — found `_ThreadPoolWaitCallback` string reference and lookup call.
- **Finding:** The missing trigger is the **`_ThreadPoolWaitCallback` function pointer**. `real_init` at offset `+0x0A36` performs: `mov rdi, [type_ptr]; lea rsi, [namespace]; lea rdx, ["_ThreadPoolWaitCallback"]; call 0x804F21D70` (il2cpp_class_get_method_from_name). Result stored at global `0x808B53C48`. Because the hash table is empty (EXP-040), the lookup returns NULL, the global stays NULL, and the ThreadPool has no callback to invoke when work is submitted. The EXP-085 metadata flag patch (`[entry+0x19]=1`) makes `metadata_lookup` return 0 for ALL queries, compounding the issue.
- **Root Cause:** IL2CPP metadata hash table empty → `_ThreadPoolWaitCallback` lookup returns NULL → ThreadPool has no worker callback → no work dispatched → deadlock.
- **Status:** CONFIRMED
- **Related:** EXP-040, EXP-085, EXP-088, EXP-089, EXP-091
- **Impact:** Re-classified from "missing event" (D) to "missing HLE implementation" (A) — metadata hash table not populated. Single root cause now links EXP-040, EXP-083, EXP-085, EXP-088, EXP-089.

### Correction
EXP-089 said "Classification D — Unity/IL2CPP waiting for event SharpEmu never generates." **CORRECTED:** Classification A — missing HLE implementation (metadata hash table not populated). The trigger is not a timer or GC callback — it is the `_ThreadPoolWaitCallback` function pointer, which exists in the PRX but cannot be found because the hash table is empty.

### Updated Current State (after EXP-090)
**Solved:** Missing trigger identified = `_ThreadPoolWaitCallback` function pointer lookup. Lookup site at `0x804F055D6`. Result global at `0x808B53C48` (NULL when hash table empty).
**Still blocked:** Hash table is empty — lookups return NULL.
**Next debugging target:** What PRX function should populate the IL2CPP metadata hash table, and why doesn't it insert entries? (EXP-091)


---

## EXP-091 (added 2026-07-31)

### EXP-091 — Hash Table Never Populated: PRX DT_INIT Registration Missing
- **Date:** 2026-07-31
- **Commit:** [fd65963](https://github.com/Sh-TB/sharpemuT24/commit/fd65963)
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What PRX function should populate the IL2CPP metadata hash table at `0x801EF7610`, and why are entries missing?
- **Hypothesis:** `il2cpp_codegen_register` runs during PRX DT_INIT and should insert entries — SharpEmu may not call the PRX's DT_INIT.
- **Tools/Logs:** Exhaustive static analysis of reads/writes to `0x801EF7610` in EBOOT and PRX.
- **Finding:** Hash table at `0x801EF7610` is **created but never populated**. Hash table struct at `0x600103DB0`, entries array at `0x60053E990`, mask `0x7FFF8`, populated `0/100` (all `0xFFFFFFFF` sentinel). EBOOT: 1689 READ sites (all LOOKUP), 1 WRITE site (creator only, at `0x8007F928C`). PRX: 0 reads, 0 writes to `0x801EF7610`. The hash_table_writer (`0x8007F90A0`) only allocates and initializes the structure — it does NOT insert entries. Entries should be inserted by `il2cpp_codegen_register` during PRX module initialization (DT_INIT), which directly inserts entries WITHOUT using the lookup mechanism (breaking the chicken-and-egg).
- **Root Cause (FINAL):** SharpEmu likely doesn't call the PRX's DT_INIT, so `il2cpp_codegen_register` never runs, and the hash table stays empty.
- **Status:** CONFIRMED
- **Related:** EXP-040, EXP-083, EXP-085, EXP-088, EXP-090, EXP-092
- **Impact:** Single root cause identified that connects ALL prior findings. Fix = ensure the PRX's DT_INIT is called during module loading.

### Chicken-and-Egg
The IL2CPP runtime looks up function pointers (like `_ThreadPoolWaitCallback`) via the hash table. But the insert function is ALSO looked up via the hash table. Without initial entries (from DT_INIT), no lookups succeed — including the lookup for the insert function itself. DT_INIT breaks this cycle by directly inserting entries without using the lookup mechanism.

### Updated Current State (after EXP-091)
**Solved:** Single root cause identified — PRX DT_INIT not called → hash table empty → all lookups fail → deadlock.
**Still blocked:** DT_INIT not yet confirmed as called or not called.
**Next debugging target:** Does SharpEmu call the PRX's DT_INIT function during module loading, and does `il2cpp_codegen_register` run? (EXP-092)


---

## EXP-092 (added 2026-07-31)

### EXP-092 — DT_INIT_ARRAY Fix Applied (37 More Semaphores), Hash Table Still Empty
- **Date:** 2026-07-31
- **Commit:** [96d3285](https://github.com/Sh-TB/sharpemuT24/commit/96d3285)
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, **DT_INIT_ARRAY fix applied**
- **Path:** B
- **Question:** Does SharpEmu execute PRX DT_INIT during module loading?
- **Hypothesis:** SharpEmu's PRX loader skips DT_INIT_ARRAY, so module_start never runs.
- **Tools/Logs:** Code analysis of `RunPreloadedModuleInitializers` and `RunImageInitializers`; runtime evidence (37 more semaphores created, different stall handle).
- **Finding:** `RunPreloadedModuleInitializers` only called `InitFunctionEntryPoint` (DT_INIT), and DT_INIT on PS5 PRXs resolves to the ELF header (`imageBase+0x10`) which is `< 0x10000`, causing the entire module to be skipped via `continue`. `RunImageInitializers` (which calls DT_INIT_ARRAY) existed but was DEAD CODE — never called. Fix: modified `RunPreloadedModuleInitializers` to (1) not skip the module when DT_INIT is invalid (only skip the DT_INIT call), and (2) call `RunImageInitializers` for every module. After fix: PRX `module_start` (`0x804CD5010`) executes, 37 MORE semaphores created (stall moved from handle `0x81` to `0xA6`), but hash table STILL empty (`0/100`).
- **Root Cause:** `RunImageInitializers` was dead code → DT_INIT_ARRAY never ran → `module_start` never executed. Hash table population happens DURING `il2cpp_init` (in `real_init` → `call#7`), not during DT_INIT_ARRAY (which does C++ static init).
- **Status:** CONFIRMED — fix is correct and necessary but not sufficient
- **Related:** EXP-091, EXP-093
- **Impact:** DT_INIT_ARRAY fix is correct (module_start now runs, 37 more semaphores created). But hash table population is a separate code path — `il2cpp_codegen_register` is called during `il2cpp_init` and still doesn't insert entries.

### Updated Current State (after EXP-092)
**Solved:** DT_INIT_ARRAY now executes. `module_start` (`0x804CD5010`) runs. PRX static initializers execute. 37 more semaphores created.
**Still blocked:** Hash table STILL empty (`0/100`). `il2cpp_codegen_register` is called during `il2cpp_init` but doesn't insert entries.
**Next debugging target:** Trace `il2cpp_init → real_init → call#7 → il2cpp_codegen_register → hash insert function`. Why doesn't `il2cpp_codegen_register` insert entries? (EXP-093)


---

## EXP-093 (added 2026-07-31)

### EXP-093 — il2cpp_codegen_register Is a Stub: Saves 3 Pointers, Does NOT Populate Hash Table
- **Date:** 2026-07-31
- **Commit:** [649740c](https://github.com/Sh-TB/sharpemuT24/commit/649740c)
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied
- **Path:** B (real metadata path)
- **Question:** Why doesn't `il2cpp_codegen_register` insert entries into the hash table during `il2cpp_init`?
- **Hypothesis:** `il2cpp_codegen_register` is called during `real_init` and should insert entries into the hash table at `0x801EF7610`.
- **Tools/Logs:** Static disassembly (capstone) of the full call chain: `real_init` → `0x804D9C620` (wrapper) → `0x804FA60C0` (trampoline) → `0x804F23280` (impl). Plus existing EXP-041 tracer runtime evidence from EXP-092 log.
- **Finding:** `il2cpp_codegen_register` (at `0x804F23280`) is a **55-byte STUB**. It only: (1) calls `0x804F71390` (once_init/lock helper), (2) saves its 3 args to 3 globals at `0x808B542E8`, `0x808B542F0`, `0x808B542F8`, (3) returns. It does NOT iterate types, does NOT compute hashes, does NOT insert anything into the hash table at `0x801EF7610` — by design, not a SharpEmu bug. The wrapper `0x804D9C620` loads 3 hardcoded args that match EXP-054 (`Il2CppCodeRegistration @ 0x8086E9000 + 0x10 = 0x8086E9010`) and EXP-055 (`Il2CppMetadataRegistration @ 0x80885C580 + 0x18 = 0x80885C598`). The third arg `rdx = 0x8082AE0C0` is the method pointers array (new finding).
- **Root Cause:** Not a bug — `il2cpp_codegen_register` is designed to only save registration pointers for later use by `call#7` (`0x804F23320`), which reads those globals and processes them. Neither function writes to `0x801EF7610`.
- **Status:** CONFIRMED — corrects EXP-091 and EXP-092 assumptions
- **Related:** EXP-040, EXP-052, EXP-053, EXP-054, EXP-055, EXP-083, EXP-091, EXP-092
- **Impact:** Major pivot — the hash table at `0x801EF7610` may be a RED HERRING. The PRX doesn't use it by design (0 reads, 0 writes). The actual metadata lookup mechanism (used by `_ThreadPoolWaitCallback` lookup at `0x804F055D6` → `0x804F21D70`) likely uses a different structure — possibly `[0x808923D88]` or the sorted array at `0x808958230`. The entire EXP-040..092 hash table investigation may have been chasing the wrong structure.

### Corrections
- **EXP-091 CORRECTED:** Said `il2cpp_codegen_register` "should insert entries during PRX DT_INIT". Wrong on two counts: (1) it's called from `real_init`, not DT_INIT; (2) it's a stub that doesn't insert anything, by design.
- **EXP-092 CORRECTED:** Said "hash table is populated during `il2cpp_init` → `real_init` → `call#7`". Wrong: `call#7` doesn't write to `0x801EF7610` either.

### New Golden Rule
**Golden Rule 8 — Verify the Function Body Before Assuming Its Behavior.** EXP-091 assumed `il2cpp_codegen_register` "should insert entries" based on its name. EXP-093 proved by disassembly that the actual function is a 55-byte stub. Never assume a function's behavior from its name — always disassemble.

### Updated Current State (after EXP-093)
**Solved:** `il2cpp_codegen_register` located and disassembled. Call chain fully mapped. Confirmed it's a stub that only saves 3 pointers to globals.
**Still blocked:** Hash table at `0x801EF7610` is empty — but the PRX never writes to it by design. The actual metadata lookup mechanism is not yet identified. ThreadPool deadlock persists.
**Next debugging target:** Disassemble `il2cpp_class_get_method_from_name` (`0x804F21D70`) to find what structure it ACTUALLY searches. (EXP-094)


---

## EXP-094 (added 2026-07-31)

### EXP-094 — Hash Table at 0x801EF7610 Confirmed RED HERRING — Lookup Uses [0x808923D88]
- **Date:** 2026-07-31
- **Commit:** [dcccd39](https://github.com/Sh-TB/sharpemuT24/commit/dcccd39)
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied
- **Path:** B (real metadata path)
- **Question:** What data structure does `il2cpp_class_get_method_from_name` (`0x804F21D70`) actually search, and is THAT structure populated?
- **Hypothesis (from EXP-093):** The function reads `[0x808923D88]`, not `0x801EF7610`.
- **Tools/Logs:** Static disassembly (capstone) of `0x804F21D70` and `0x804EEE8D0`. Fast byte-pattern scan of PRX and EBOOT executable segments for RIP-relative accesses to `0x808923D88`. Runtime evidence from EXP-092 log (EXP-058 context dump).
- **Finding:** `il2cpp_class_get_method_from_name` (`0x804F21D70`) is a **1-instruction trampoline** (`jmp 0x804EEE8D0`). The actual implementation at `0x804EEE8D0` reads `[0x808923D88]` as its context pointer (**5 reads**) and **NEVER reads `0x801EF7610`** (0 reads). The wrapper at `0x804F21DC0` also reads `0x808923D88` (6 times). This **definitively confirms** EXP-093's hypothesis: the hash table at `0x801EF7610` was a RED HERRING across EXP-040..092. The actual lookup structure at `[0x808923D88]` IS populated at runtime (value = `0x7F113CED77E0`, host-side pointer to a SharpEmu-managed context structure containing stack canary guards `0xC0DEC0DECAFEBA00`). The method table pointer at `[context+0x30]` is non-NULL (`0x55FBF4A4E3A0`), but `_ThreadPoolWaitCallback` lookup still returns NULL — the method table is either incomplete or contains wrong data.
- **Root Cause:** NOT "hash table empty" — the hash table at `0x801EF7610` is irrelevant. The method table at `[context+0x30]` (where context = `[0x808923D88]`) does not contain `_ThreadPoolWaitCallback`.
- **Status:** CONFIRMED — confirms EXP-093 hypothesis, corrects EXP-040..092 direction
- **Related:** EXP-040, EXP-053, EXP-083, EXP-090, EXP-091, EXP-092, EXP-093, EXP-095
- **Impact:** Major pivot — the entire EXP-040..092 hash table investigation was chasing the wrong structure. The actual lookup uses `[0x808923D88]` which IS populated. The new blocker is understanding why the method table at `[context+0x30]` doesn't contain `_ThreadPoolWaitCallback`.

### PRX-wide Writer Scan
- 50 PRX functions READ `0x808923D88` (verified first 10 — all reads, classic "load context pointer at function entry" pattern)
- 0 PRX functions WRITE `0x808923D88` via RIP-relative addressing
- 0 EBOOT accesses to `0x808923D88`
- The write happens via indirect pointer (register-computed address, not RIP-relative) — likely during PRX module_start or DT_INIT_ARRAY

### EXP-040..092 Retrospective
The investigation was NOT wasted:
- EXP-054/055 correctly identified `Il2CppCodeRegistration` and `Il2CppMetadataRegistration`
- EXP-092's DT_INIT_ARRAY fix was correct and necessary (module_start now runs)
- EXP-093 correctly identified `il2cpp_codegen_register` as a stub
- But the core assumption (hash table at `0x801EF7610` is the lookup target) was wrong

**Lesson:** Always verify by disassembly which structure a function ACTUALLY reads before investigating that structure (Golden Rule 8).

### Updated Current State (after EXP-094)
**Solved:** Actual lookup structure identified as `[0x808923D88]` (not `0x801EF7610`). Context structure IS populated. Method table pointer at `[context+0x30]` IS non-NULL.
**Still blocked:** `_ThreadPoolWaitCallback` lookup still returns NULL despite populated context. The method table may be incomplete or contain wrong data.
**Next debugging target:** Runtime trace the `_ThreadPoolWaitCallback` lookup at `0x804F055D6` to dump args, return value, and method table contents. (EXP-095)


---

## EXP-095 (added 2026-08-01)

### EXP-095 — _ThreadPoolWaitCallback Lookup SUCCEEDS (rax=0x6007E64D0) — Deadlock Persists on WaitSema(0xA6)
- **Date:** 2026-08-01
- **Commit:** [e131ce7](https://github.com/Sh-TB/sharpemuT24/commit/e131ce7)
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied, EXP-095 tracer active
- **Path:** B (real metadata path)
- **Question:** What are the exact args and return value of the `_ThreadPoolWaitCallback` lookup at runtime, and what does the method table at `[context+0x30]` contain?
- **Hypothesis (from EXP-094):** The method table is incomplete or doesn't contain `_ThreadPoolWaitCallback`, causing the lookup to return NULL.
- **Tools/Logs:** New two-stage INT3 tracer (`_Exp095ThreadPoolLookupTracer.cs`): Stage 1 at call site `0x804F055D6` (captures args), Stage 2 at return site `0x804F055DB` (captures rax). Built SharpEmu with `dotnet publish`, ran with 120s timeout.
- **Finding:** The lookup **SUCCEEDED**. `rax = 0x6007E64D0` (non-NULL guest heap pointer to a valid `MethodInfo` structure). The method table at `[context+0x30]` IS populated and DOES contain `_ThreadPoolWaitCallback`. The MethodInfo at `0x6007E64D0` contains: `+0x00 = 0x60070B3A0` (Il2CppClass* matching rdi arg), `+0x10/+0x18/+0x20` = guest heap pointers (method name, signature, invoker). However, the deadlock **still occurs** — main thread blocks on `WaitSema(0xA6)` at `0x804F6E9EB` (ThreadPool dispatch), identical to EXP-092. The callback EXISTS but is never INVOKED because no work is submitted to the ThreadPool.
- **Root Cause:** NOT a missing callback — the lookup succeeds. The deadlock is caused by no work being submitted to the ThreadPool (re-confirms EXP-088/089).
- **Status:** CONFIRMED — corrects EXP-090 and EXP-094
- **Related:** EXP-040, EXP-085, EXP-088, EXP-089, EXP-090, EXP-091, EXP-092, EXP-093, EXP-094, EXP-096
- **Impact:** Major correction — the entire EXP-090..094 chain was based on the wrong assumption that `_ThreadPoolWaitCallback` lookup returns NULL. It does NOT. The lookup succeeds. The real blocker is that no work is submitted to the ThreadPool after the lookup. EXP-088/089's original classification was correct all along.

### Corrections
- **EXP-090 CORRECTED:** Claimed "_ThreadPoolWaitCallback lookup returns NULL → deadlock". Wrong: the lookup returns `0x6007E64D0` (non-NULL). The assumption was based on the hash table at `0x801EF7610` being empty, but EXP-094 proved the lookup doesn't use `0x801EF7610`, and EXP-095 proves the lookup succeeds.
- **EXP-094 CORRECTED:** Claimed "method table doesn't contain _ThreadPoolWaitCallback". Wrong: the method table DOES contain it, and the lookup succeeds.

### Tracer Bug (Minor)
`Exp095ReadCString` fails on guest heap addresses (`0x60...` range) — not identity-mapped to host addresses. The `method_name` string was read as `"??p"` instead of `"_ThreadPoolWaitCallback"`. The `namespace` string read correctly because it's in the PRX data segment (identity-mapped). This bug does NOT affect the key finding (rax was read from the register, not memory).

### Updated Current State (after EXP-095)
**Solved:** `_ThreadPoolWaitCallback` lookup traced at runtime. Lookup SUCCEEDS (rax=0x6007E64D0). Method info structure is valid and populated. Method table at `[context+0x30]` IS searchable. Deadlock is NOT caused by a missing callback.
**Still blocked:** Main thread blocks on `WaitSema(0xA6)` at `0x804F6E9EB` (ThreadPool dispatch). No work submitted to the ThreadPool after the lookup succeeds. The callback exists but is never invoked.
**Next debugging target:** Trace what the main thread does between `0x804F055DB` (lookup result stored) and `0x804F6E9EB` (WaitSema block). Look for a `QueueUserWorkItem` or similar work-submission call that should happen but doesn't. (EXP-096)


---

## EXP-096 (added 2026-08-01)

### EXP-096 — Work Submission Function NEVER Reached — Entire Call Chain Is Dead Code
- **Date:** 2026-08-01
- **Commit:** [8fc4ddc](https://github.com/Sh-TB/sharpemuT24/commit/8fc4ddc)
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied, EXP-095 + EXP-096 tracers active
- **Path:** B (real metadata path)
- **Question:** What code path should submit work to the ThreadPool after the `_ThreadPoolWaitCallback` lookup, and why doesn't it execute?
- **Hypothesis:** The work-submission function (`0x804F6EC20`) should be called during IL2CPP init to queue work. Deadlock occurs because it's never called (Case A), or called but skips (Case B), or submits but SignalSema fails (Case C).
- **Tools/Logs:** Static disassembly (capstone) of `0x804F6EC20` and its callers. PRX/EBOOT-wide `E8 rel32` scan for all callers. New INT3 tracer (`_Exp096WorkSubmissionTracer.cs`) at all 3 call sites. Runtime run with 120s timeout.
- **Finding:** **Case A confirmed.** The work-submission function (`0x804F6EC20`) is NEVER reached at runtime. All 3 call sites (`0x804F4571A`, `0x804F9FAAA`, `0x804FA14C8`) had ZERO INT3 hits. Static analysis proves the entire call chain is dead code: the containing functions (`0x804F456E0`, `0x804F9FA80`, `0x804FA1440`) have zero direct callers, and the one caller (`0x804FA2089` in `0x804FA1FE0`) also has zero direct callers. The work-submission path is only reachable via indirect function pointers (vtables, delegates, runtime callbacks) that are never set up.
- **Root Cause:** The work-submission call chain is dead code because the indirect function pointers that should reach it are never registered. SharpEmu likely doesn't implement the HLE function that performs this registration.
- **Status:** CONFIRMED — Case A (work submission never reached)
- **Related:** EXP-088, EXP-089, EXP-090, EXP-092, EXP-095, EXP-097
- **Impact:** Root cause of the ThreadPool deadlock identified at the call-chain level. The callback EXISTS (EXP-095) but the code that should INVOKE it is dead code. The fix must identify what indirect registration mechanism should set up the call chain and implement the missing HLE function.

### Work-Submission Call Chain (All Dead Code)

```
0x804F6EC20 (SignalSema(0xA6) caller — work submission)
  ← 0x804F4571A in 0x804F456E0  (0 direct callers — DEAD)
  ← 0x804F9FAAA in 0x804F9FA80  (1 caller: 0x804FA2089 in 0x804FA1FE0)
  ← 0x804FA14C8 in 0x804FA1440  (0 direct callers — DEAD)

0x804FA1FE0 (caller of 0x804F9FA80)
  ← 0 direct callers — DEAD
```

### Updated Current State (after EXP-096)
**Solved:** Work-submission function located (`0x804F6EC20`). 3 call sites identified. Runtime proof: NONE reached (Case A). Static proof: entire call chain is dead code (0 direct callers). Root cause: indirect function pointers never set up.
**Still blocked:** The indirect registration mechanism that should set up the call chain is not identified. SharpEmu likely doesn't implement the HLE function that performs this registration.
**Next debugging target:** Search PRX data segment for function pointers to the dead-code functions. Check IL2CPP registration data. Find what should populate the function pointer. (EXP-097)


---

## EXP-097 (added 2026-08-01)

### EXP-097 — Dead-Code Functions Not Registered Anywhere — Self-Registering Function 0x804FA1FE0 Never Called
- **Date:** 2026-08-01
- **Commit:** [dede8eb](https://github.com/Sh-TB/sharpemuT24/commit/dede8eb)
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied, EXP-095 + EXP-096 + EXP-097 tracers active
- **Path:** B (real metadata path)
- **Question:** What indirect call mechanism should reach the work-submission function `0x804F6EC20`, and why is the function pointer never set?
- **Hypothesis (from user):** The dead-code functions are reachable via indirect function pointers (vtable slots, delegate targets, callback tables) that are either static relocations or runtime-written values. Find the stored function pointer and determine if SharpEmu populates it.
- **Tools/Logs:** Exhived static search of PRX + EBOOT for stored qwords (byte-level scan). LEA instruction scan. movabs scan. New runtime tracer (`_Exp097FuncPtrGlobalTracer.cs`) that dumps 7 function pointer globals + 3 IL2CPP globals + once-init guard from the EXP-095 return-site handler.
- **Finding:** The 5 dead-code function addresses are **NOT registered as function pointers anywhere** — 0 stored qwords in data segments, 0 LEA instructions (except self-referential `0x804FA1FE0`), 0 movabs immediates. The 3 IL2CPP registration globals ARE populated at runtime but don't contain the dead-code addresses. The 7 runtime-set function pointer globals (called via `call [rip+disp]`) ARE populated but point to different functions (`0x804F09550`, `0x804FBF820`, etc.). The once-init guard `[0x808B418D8]` = `0xFFFFFFFFFFFFFFFF` (sentinel — never cleared). The self-registering function `0x804FA1FE0` (loads its own address via `lea rsi, [self]` and tail-jumps to `0x804F889D0`) is itself dead code with 0 callers.
- **Root Cause:** The registration mechanism that should set up the work-submission call chain is itself dead code. The self-registering function `0x804FA1FE0` was supposed to register the function pointers by calling `0x804F889D0`, but `0x804FA1FE0` has 0 callers and is never executed.
- **Status:** CONFIRMED — dead-code functions not registered anywhere
- **Related:** EXP-088, EXP-089, EXP-095, EXP-096, EXP-098
- **Impact:** The investigation traced the exact address (as the user instructed) rather than pattern-guessing. The root cause is now precisely identified: the self-registering function `0x804FA1FE0` is the missing link — it should register the work-submission path but is never called. Next step is to find what should call `0x804FA1FE0`.

### Self-Registering Function Pattern
```asm
0x804FA210F  lea  rsi, [rip+...]  ; -> 0x804FA1FE0 (its own address!)
0x804FA2127  jmp  0x804F889D0     ; tail jump to registration function
```

### Updated Current State (after EXP-097)
**Solved:** 5 dead-code functions NOT registered anywhere (0 stored qwords, 0 LEA except self-ref, 0 movabs). 7 runtime-set function pointer globals all populated but point elsewhere. 3 IL2CPP globals populated but don't contain dead-code addresses. Once-init guard never cleared. Self-registering function `0x804FA1FE0` identified as the registration entry point but is itself dead code.
**Still blocked:** What should call `0x804FA1FE0`? Is it in the init_array? Is it an IL2CPP icall? Is it called from EBOOT?
**Next debugging target:** Check the PRX's init_array at runtime for `0x804FA1FE0`. Trace the 25 call sites in real_init. (EXP-098)


---

## EXP-111 (added 2026-08-02)

### EXP-111 — UD2 Instructions Are Noreturn Markers, NOT Function Entry Stubs — Hypothesis REJECTED
- **Date:** 2026-08-02
- **Commit:** [c36ecdd](https://github.com/Sh-TB/sharpemuT24/commit/c36ecdd)
- **Configuration:** Static analysis only
- **Question:** Are the UD2 instructions at 0x801832489 and 0x8007F9093 function-entry stubs that fail because patching skips the prologue?
- **Hypothesis:** UD2 stubs at function entry fail because patching skips the original function prologue. A trampoline that preserves the function entry/prologue semantics may allow execution to continue.
- **Finding:** HYPOTHESIS REJECTED. Both UD2 instructions are noreturn markers AFTER calls, NOT at function entry. The function at 0x801832480 has prologue (push rbp; mov rbp, rsp) that executes BEFORE the call — prologue is NOT skipped. The UD2 is the compiler's safety net after a call to a noreturn imported function via PLT. The function has 67 callers in EBOOT but was NEVER reached during any emulator run. libSceApt does not exist anywhere in the codebase. EXP-108/109/110 do not exist — no previous UD2 patching was attempted.
- **Status:** CONFIRMED — hypothesis REJECTED
- **Related:** EXP-096, EXP-097
- **Impact:** The UD2 trampoline experiment is irrelevant to the current blocker (ThreadPool deadlock). The UD2 instructions are in error/panic paths that were never reached. The actual blocker remains the work-submission call chain being dead code (EXP-096/097).


---

## EXP-098 (added 2026-08-02)

### EXP-098 — Registration Function IS Reached — EXP-097 Corrected — Registration Helper May Fail
- **Date:** 2026-08-02
- **Commit:** [8eb4b19](https://github.com/Sh-TB/sharpemuT24/commit/8eb4b19)
- **Question:** Why is the IL2CPP ThreadPool initialization path never started?
- **Hypothesis:** The registration function 0x804FA20E0 (which registers callback 0x804FA1FE0) is never called — it's dead code.
- **Finding:** HYPOTHESIS REJECTED. 0x804FA20E0 IS REACHED at runtime. INT3 tracer fired at line 8492, caller=0x804F527F9 (inside 0x804F527C0, called from real_init at 0x804F0590B). The registration path IS executed AFTER the _ThreadPoolWaitCallback lookup. The deadlock persists because the registration helper 0x804F889D0 calls 0x804FC33B0 (once-init primitive) which may return failure.
- **Status:** CONFIRMED — EXP-097 corrected
- **Related:** EXP-095, EXP-096, EXP-097, EXP-099
- **Impact:** Major correction — the registration path IS reached, the issue is whether the registration helper succeeds. EXP-097's "dead code" conclusion was wrong due to a Golden Rule 8 violation (function boundary not verified).


---

## EXP-099 (added 2026-08-02)

### EXP-099 — Once-Init Primitive SUCCEEDS (eax=0) — Registration Works — Hypothesis REJECTED
- **Date:** 2026-08-02
- **Commit:** [see git log for EXP-099.md]
- **Question:** Does the once-init primitive 0x804FC33B0 succeed or fail?
- **Hypothesis:** 0x804FC33B0 returns failure, causing registration to be skipped.
- **Finding:** HYPOTHESIS REJECTED. 0x804FC33B0 SUCCEEDS (eax=0). Registration is NOT skipped. The callback IS registered. After registration, an unresolved import fires (nid=J3edELK4FvM at ret=0x804FC1635), then the same deadlock.
- **Status:** CONFIRMED — hypothesis rejected
- **Related:** EXP-098, EXP-100
- **Impact:** The registration mechanism works correctly. The issue is downstream — an unresolved HLE import may prevent the IL2CPP runtime from reaching work submission.
