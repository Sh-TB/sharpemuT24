# Yatzi Complete Diagnostic History

**Single source of truth for all Yatzi (PPSA17697) debugging experiments.**
**Coverage: EXP-026 through EXP-081 (56 experiments)**
**Last updated: 2026-07-31 (EXP-081)**

This file consolidates ALL diagnostic knowledge from every EXP report, git commit, and worklog entry. Future debugging MUST start from this file.

---

## Table of Contents

1. [EXP Timeline (EXP-026 through EXP-081)](#exp-timeline)
2. [Phase Summary](#phase-summary)
3. [Key Corrections and Superseded Theories](#key-corrections)
4. [Current State (after EXP-081)](#current-state)
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

