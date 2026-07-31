# Yatzi Debugging Knowledge Base

Complete index of all EXP experiments for the Yatzi (PPSA17697) game bringup.

---

## EXP-026

- **Date:** 2026-07-28
- **Commit:** [08c0735](https://github.com/Sh-TB/sharpemuT24/commit/08c0735)
- **Status:** CONFIRMED
- **Question:** Does the IL2CPP symbol resolver BST algorithm work correctly?
- **Finding:** Synthetic x86-64 CPU emulator finds all 239/239 IL2CPP symbols. Algorithm definitively correct. Reference RBTree agrees.
- **Root Cause:** None — resolver algorithm is correct
- **Related EXPs:** EXP-028 (continued investigation)
- **Current Impact:** Closed: resolver algorithm verified correct. Mismatch was elsewhere.

## EXP-027

- **Date:** 2026-07-28
- **Commit:** [08c0735](https://github.com/Sh-TB/sharpemuT24/commit/08c0735)
- **Status:** CONFIRMED
- **Question:** Is CPU instruction emulation correct (test/lea/cmovns/cmov conditions)?
- **Finding:** Host CPU, Unicorn engine, and synthetic Python CPU all agree on test/lea/cmovns/cmovns sequence (T4: 10/10) and all 16 cmov conditions (T16: 768/768).
- **Root Cause:** None — CPU instruction emulation is correct
- **Related EXPs:** EXP-028 (Method B continued)
- **Current Impact:** Closed: CPU emulation verified correct. Divergence was elsewhere.

## EXP-028

- **Date:** 2026-07-29
- **Commit:** [f1d0968](https://github.com/Sh-TB/sharpemuT24/commit/f1d0968)
- **Status:** CONFIRMED
- **Question:** Find the first divergence between SharpEmu and reference CPU execution
- **Finding:** strcmp GOT slot points to freed memory — the GOT was being set up correctly but the target string was in a region that got freed/moved.
- **Root Cause:** strcmp GOT pointing to freed memory
- **Related EXPs:** EXP-026, EXP-027
- **Current Impact:** Fixed GOT lifetime. Enabled IL2CPP resolver to work.

## EXP-029

- **Date:** 2026-07-29
- **Commit:** [13d7a4c](https://github.com/Sh-TB/sharpemuT24/commit/13d7a4c)
- **Status:** CONFIRMED
- **Question:** Why does the IL2CPP BST strcmp fail after resolver runs?
- **Finding:** strcmp GOT points to freed memory — the trampoline lifetime was too short.
- **Root Cause:** Trampoline/GOT lifetime management
- **Related EXPs:** EXP-028, EXP-030
- **Current Impact:** Root cause of resolver crash identified.

## EXP-030

- **Date:** 2026-07-29
- **Commit:** [ee1ed98](https://github.com/Sh-TB/sharpemuT24/commit/ee1ed98)
- **Status:** SUPERSEDED
- **Question:** Fix trampoline lifetime to prevent GOT invalidation
- **Finding:** Trampoline lifetime fix attempted, root cause revised — the issue was deeper than just lifetime.
- **Root Cause:** Revised: see EXP-031/032
- **Related EXPs:** EXP-029, EXP-031
- **Current Impact:** Superseded by EXP-031/032 findings.

## EXP-031

- **Date:** 2026-07-29
- **Commit:** [a8d5c09](https://github.com/Sh-TB/sharpemuT24/commit/a8d5c09)
- **Status:** SUPERSEDED
- **Question:** Narrow down the execution context issue in TryCallGuestFunction
- **Finding:** Root cause narrowed to TryCallGuestFunction execution context — return value not propagating correctly.
- **Root Cause:** Revised: see EXP-032
- **Related EXPs:** EXP-030, EXP-032
- **Current Impact:** Led to EXP-032's definitive root cause.

## EXP-032

- **Date:** 2026-07-29
- **Commit:** [3c186a4](https://github.com/Sh-TB/sharpemuT24/commit/3c186a4)
- **Status:** CONFIRMED
- **Question:** Why does the resolver return 0 (NULL) for IL2CPP function addresses?
- **Finding:** ROOT CAUSE FOUND: CpuContext.Rax never updated from nativeReturn — CallNativeEntry return value (int→long truncation + missing CpuContext update).
- **Root Cause:** CallNativeEntry int→long truncation + CpuContext.Rax not updated
- **Related EXPs:** EXP-031, EXP-033
- **Current Impact:** Fixed: return value propagation. All 232 IL2CPP functions now resolve correctly.

## EXP-033

- **Date:** 2026-07-29
- **Commit:** [af7d8b8](https://github.com/Sh-TB/sharpemuT24/commit/af7d8b8)
- **Status:** CONFIRMED
- **Question:** Why does the game crash after the resolver completes?
- **Finding:** Post-resolver crash from NULL execute fault limit (100000) — guest code calls NULL function pointers.
- **Root Cause:** NULL function pointer calls in guest code (IL2CPP stubs)
- **Related EXPs:** EXP-032, EXP-034
- **Current Impact:** Identified NULL execute as the next blocker.

## EXP-034

- **Date:** 2026-07-29
- **Commit:** [0e13c17](https://github.com/Sh-TB/sharpemuT24/commit/0e13c17)
- **Status:** SUPERSEDED
- **Question:** Are IL2CPP globals populated after resolver runs?
- **Finding:** Globals ARE populated (all 232 real func_impl addresses found). But fake heap stubs still cause NULL calls — re-patching import stubs with real addresses fails (0/232 patched).
- **Root Cause:** Re-patching fails because NID-to-name lookup fails for eboot imports
- **Related EXPs:** EXP-033, EXP-035, EXP-066
- **Current Impact:** Superseded: EXP-067 proved re-patching was unnecessary (resolver returns real addresses directly).

## EXP-035

- **Date:** 2026-07-29
- **Commit:** [56bd06c](https://github.com/Sh-TB/sharpemuT24/commit/56bd06c)
- **Status:** SUPERSEDED
- **Question:** Is the fake heap the cause of NULL executes?
- **Finding:** Fake heap disproven — root cause is uninitialized task descriptor. Workers call [rbx+0xF8]=NULL because task function pointer is never set.
- **Root Cause:** Uninitialized task descriptor [rbx+0xF8]=NULL
- **Related EXPs:** EXP-034, EXP-064
- **Current Impact:** Superseded: EXP-081 found the real reason [rbx+0xF8] is NULL (FAST_PATH=1).

## EXP-036

- **Date:** 2026-07-29
- **Commit:** [7986cbe](https://github.com/Sh-TB/sharpemuT24/commit/7986cbe)
- **Status:** CONFIRMED — REPEATED IN EXP-081
- **Question:** Why is il2cpp_init never reached?
- **Finding:** SHARPEMU_SEMA_FAST_PATH=1 was causing il2cpp_init starvation — workers spin and starve the main thread.
- **Root Cause:** FAST_PATH=1 makes WaitSema return immediately, starving main thread
- **Related EXPs:** EXP-062, EXP-063, EXP-068, EXP-081
- **Current Impact:** This finding was CORRECT but was overridden by EXP-063 which switched back to FAST_PATH=1. EXP-081 re-discovered this same root cause.

## EXP-037

- **Date:** 2026-07-29
- **Commit:** [5a5d782](https://github.com/Sh-TB/sharpemuT24/commit/5a5d782)
- **Status:** SUPERSEDED
- **Question:** Are IL2CPP static initializers running?
- **Finding:** IL2CPP static initializers not running — empty init_array. No .init_array entries found.
- **Root Cause:** Missing init_array (later found to be a dump completeness issue)
- **Related EXPs:** EXP-038, EXP-059, EXP-061
- **Current Impact:** Superseded: EXP-061 found the dump was mixed (Dreaming Sarah eboot, not Yatzi).

## EXP-038

- **Date:** 2026-07-30
- **Commit:** [6f7a979](https://github.com/Sh-TB/sharpemuT24/commit/6f7a979)
- **Status:** SUPERSEDED
- **Question:** Is the DT_INIT callback (rdx parameter) being passed correctly?
- **Finding:** DT_INIT callback (rdx) not passed — IL2CPP registration never runs. rdx=0 instead of callback address.
- **Root Cause:** Missing rdx parameter to DT_INIT
- **Related EXPs:** EXP-037, EXP-039
- **Current Impact:** Superseded: EXP-039 disproved the rdx hypothesis.

## EXP-039

- **Date:** 2026-07-30
- **Commit:** [1e13915](https://github.com/Sh-TB/sharpemuT24/commit/1e13915)
- **Status:** CONFIRMED
- **Question:** Does passing rdx fix the IL2CPP registration?
- **Finding:** DT_INIT rdx hypothesis disproven — circular dependency in il2cpp_init. Passing rdx doesn't help because the registration code isn't reached.
- **Root Cause:** Circular dependency in il2cpp_init
- **Related EXPs:** EXP-038, EXP-040
- **Current Impact:** Closed: rdx hypothesis rejected.

## EXP-040

- **Date:** 2026-07-30
- **Commit:** [f41736c](https://github.com/Sh-TB/sharpemuT24/commit/f41736c)
- **Status:** CONFIRMED
- **Question:** Are hash table entries being filled?
- **Finding:** Hash table entries never filled — workaround clears original crash but doesn't fix the root cause.
- **Root Cause:** Hash table not populated by IL2CPP registration
- **Related EXPs:** EXP-039, EXP-041
- **Current Impact:** Identified hash table population as the issue.

## EXP-041

- **Date:** 2026-07-30
- **Commit:** [d76f7bf](https://github.com/Sh-TB/sharpemuT24/commit/d76f7bf)
- **Status:** CONFIRMED
- **Question:** What is the init order issue?
- **Finding:** Init order issue — il2cpp_init called BEFORE hash lookup sets 0x801E51240. The global metadata pointer is NULL when il2cpp_init runs.
- **Root Cause:** il2cpp_init runs before metadata global is set
- **Related EXPs:** EXP-040, EXP-042
- **Current Impact:** Identified initialization ordering problem.

## EXP-042

- **Date:** 2026-07-30
- **Commit:** [813a5d2](https://github.com/Sh-TB/sharpemuT24/commit/813a5d2)
- **Status:** CONFIRMED
- **Question:** Does metadata lookup return a valid object?
- **Finding:** Metadata lookup returns valid object — 0x801E51240 needs pre-init. The metadata global must be set before il2cpp_init.
- **Root Cause:** 0x801E51240 (metadata global) needs pre-init
- **Related EXPs:** EXP-041, EXP-043
- **Current Impact:** Confirmed metadata global needs initialization.

## EXP-043

- **Date:** 2026-07-30
- **Commit:** [7a7b4ad](https://github.com/Sh-TB/sharpemuT24/commit/7a7b4ad)
- **Status:** SUPERSEDED
- **Question:** Is there a pre-init mechanism that's missing?
- **Finding:** Pre-init mechanism missing — PRX DT_INIT flag forces jump to INT3. The PRX module initialization doesn't run.
- **Root Cause:** PRX DT_INIT flag issue
- **Related EXPs:** EXP-042, EXP-044
- **Current Impact:** Superseded: EXP-044 found INT3 is just ELF padding.

## EXP-044

- **Date:** 2026-07-30
- **Commit:** [7465613](https://github.com/Sh-TB/sharpemuT24/commit/7465613)
- **Status:** CONFIRMED
- **Question:** Is the INT3 at PRX entry a module_start indicator?
- **Finding:** INT3 is ELF padding (not module_start) — fini_array has 11 entries. The INT3 is just alignment padding.
- **Root Cause:** None — INT3 is benign padding
- **Related EXPs:** EXP-043, EXP-045
- **Current Impact:** Closed: INT3 hypothesis rejected.

## EXP-045

- **Date:** 2026-07-30
- **Commit:** [aedf782](https://github.com/Sh-TB/sharpemuT24/commit/aedf782)
- **Status:** CONFIRMED
- **Question:** Does eboot fini_array contain the pre-init mechanism?
- **Finding:** eboot fini_array found (20 entries) but not root cause — the entries are destructors, not initializers.
- **Root Cause:** None — fini_array is destructors only
- **Related EXPs:** EXP-044, EXP-046
- **Current Impact:** Closed: fini_array hypothesis rejected.

## EXP-046

- **Date:** 2026-07-30
- **Commit:** [4721b59](https://github.com/Sh-TB/sharpemuT24/commit/4721b59)
- **Status:** CONFIRMED
- **Question:** Is the crash from call #7 or call #8?
- **Finding:** Crash is from call #8, not #7 — metadata lookup returns non-zero. The crash happens after call #7 returns.
- **Root Cause:** Call #8 crash after metadata lookup
- **Related EXPs:** EXP-045, EXP-047
- **Current Impact:** Narrowed crash to call #8.

## EXP-047

- **Date:** 2026-07-30
- **Commit:** [3428a8f](https://github.com/Sh-TB/sharpemuT24/commit/3428a8f)
- **Status:** CONFIRMED
- **Question:** Do three fixes prevent the callback crash?
- **Finding:** Three fixes prevent callback crash but cascade remains — fixing the immediate crash reveals more crashes downstream.
- **Root Cause:** Cascade of crashes after fixing each layer
- **Related EXPs:** EXP-046, EXP-048
- **Current Impact:** Identified cascade pattern.

## EXP-048

- **Date:** 2026-07-30
- **Commit:** [538c4da](https://github.com/Sh-TB/sharpemuT24/commit/538c4da)
- **Status:** CONFIRMED
- **Question:** Does a callback stub allow il2cpp_init to progress?
- **Finding:** Callback stub-ret allows il2cpp_init to progress — workers created. The stub returns 0 for an unspecified callback.
- **Root Cause:** Missing callback HLE function
- **Related EXPs:** EXP-047, EXP-049
- **Current Impact:** Enabled il2cpp_init to run. Workers created.

## EXP-049

- **Date:** 2026-07-30
- **Commit:** [db3d578](https://github.com/Sh-TB/sharpemuT24/commit/db3d578)
- **Status:** CONFIRMED
- **Question:** What is at 0x801E51220?
- **Finding:** NULL pointer at 0x801E51220 — same class as 0x801E51240. Systemic pattern of uninitialized metadata globals.
- **Root Cause:** Systemic uninitialized metadata globals
- **Related EXPs:** EXP-048, EXP-050
- **Current Impact:** Identified pattern of NULL metadata globals.

## EXP-050

- **Date:** 2026-07-30
- **Commit:** [ea58673](https://github.com/Sh-TB/sharpemuT24/commit/ea58673)
- **Status:** CONFIRMED
- **Question:** Why is hash lookup skipped?
- **Finding:** Hash lookup skipped by 15+ conditional jumps — stub cleared first cascade. The lookup function returns early due to NULL inputs.
- **Root Cause:** Hash lookup returns early due to NULL inputs
- **Related EXPs:** EXP-049, EXP-051
- **Current Impact:** Identified why hash lookup was being skipped.

## EXP-051

- **Date:** 2026-07-30
- **Commit:** [30e6215](https://github.com/Sh-TB/sharpemuT24/commit/30e6215)
- **Status:** CONFIRMED
- **Question:** Do buffer+NOP+loop fixes resolve the crash?
- **Finding:** Buffer+NOP+loop fix tested — all cause new crashes, reverted. None of the attempted fixes work.
- **Root Cause:** None — all fixes reverted
- **Related EXPs:** EXP-050, EXP-052
- **Current Impact:** Closed: all attempted fixes failed.

## EXP-052

- **Date:** 2026-07-30
- **Commit:** [0f6db8d](https://github.com/Sh-TB/sharpemuT24/commit/0f6db8d)
- **Status:** CONFIRMED
- **Question:** What mechanism is missing for IL2CPP registration?
- **Finding:** Missing mechanism identified — wrapper 0x800805AE0 = il2cpp_codegen_register, called indirectly, never invoked on SharpEmu.
- **Root Cause:** il2cpp_codegen_register (0x800805AE0) never called
- **Related EXPs:** EXP-051, EXP-053
- **Current Impact:** Identified il2cpp_codegen_register as the missing function.

## EXP-053

- **Date:** 2026-07-30
- **Commit:** [6b62771](https://github.com/Sh-TB/sharpemuT24/commit/6b62771)
- **Status:** CONFIRMED
- **Question:** Is wrapper 0x800805AE0 ever called?
- **Finding:** Wrapper 0x800805AE0 NEVER called — missing walker confirmed. Static table 0x1CC0080 is string fragment pool not Il2CppMetadataRegistration.
- **Root Cause:** Wrapper never called; static table misidentified
- **Related EXPs:** EXP-052, EXP-054
- **Current Impact:** Confirmed wrapper is never invoked.

## EXP-054

- **Date:** 2026-07-30
- **Commit:** [a101e62](https://github.com/Sh-TB/sharpemuT24/commit/a101e62)
- **Status:** CONFIRMED
- **Question:** Where is Il2CppCodeRegistration?
- **Finding:** Il2CppCodeRegistration found at 0x8086E9000. Baseline crash chain captured. Stub now conditional.
- **Root Cause:** Il2CppCodeRegistration at 0x8086E9000
- **Related EXPs:** EXP-053, EXP-055
- **Current Impact:** Found the CodeRegistration struct.

## EXP-055

- **Date:** 2026-07-30
- **Commit:** [5f89b31](https://github.com/Sh-TB/sharpemuT24/commit/5f89b31)
- **Status:** CONFIRMED
- **Question:** Where is MetadataRegistration?
- **Finding:** MetadataRegistration found at 0x80885C580. PRX DT_INIT invalid (ELF header). Upstream has same unsolved issue.
- **Root Cause:** MetadataRegistration at 0x80885C580
- **Related EXPs:** EXP-054, EXP-056
- **Current Impact:** Found the MetadataRegistration struct.

## EXP-056

- **Date:** 2026-07-30
- **Commit:** [d325f54](https://github.com/Sh-TB/sharpemuT24/commit/d325f54)
- **Status:** CONFIRMED
- **Question:** Why are structs populated but nothing works?
- **Finding:** Major pivot — structs already populated. Root cause is missing CONSUMER function that reads the metadata.
- **Root Cause:** Missing consumer function (not missing data)
- **Related EXPs:** EXP-055, EXP-057
- **Current Impact:** Pivoted from 'missing data' to 'missing consumer'.

## EXP-057

- **Date:** 2026-07-30
- **Commit:** [77bd7dc](https://github.com/Sh-TB/sharpemuT24/commit/77bd7dc)
- **Status:** CONFIRMED
- **Question:** What is the consumer function?
- **Finding:** MetaReg access via metadataUsages indirection. Call #7 (0x804F23320) is consumer candidate with 0x38-byte stride loops.
- **Root Cause:** Call #7 (0x804F23320) is the consumer
- **Related EXPs:** EXP-056, EXP-058
- **Current Impact:** Identified call #7 as the metadata consumer.

## EXP-058

- **Date:** 2026-07-30
- **Commit:** [d928189](https://github.com/Sh-TB/sharpemuT24/commit/d928189)
- **Status:** CONFIRMED
- **Question:** Does call #7 execute successfully?
- **Finding:** Call #7 entered but returns early — metadata loader 0x804F04750 fails (missing metadata file). Root cause identified.
- **Root Cause:** Missing metadata file (global-metadata.dat)
- **Related EXPs:** EXP-057, EXP-059
- **Current Impact:** Identified missing metadata file as root cause.

## EXP-059

- **Date:** 2026-07-31
- **Commit:** [efd65f5](https://github.com/Sh-TB/sharpemuT24/commit/efd65f5)
- **Status:** CONFIRMED
- **Question:** What is the real structure at 0x8086E9000?
- **Finding:** Ground-truth diff with Unity 2022.3.5f1 source — struct at 0x8086E9000 is Il2CodeGenModule not CodeReg. Root cause is DUMP COMPLETENESS (missing PRX + metadata).
- **Root Cause:** Incomplete game dump (missing Il2cppUserAssemblies.prx + global-metadata.dat)
- **Related EXPs:** EXP-058, EXP-060
- **Current Impact:** Identified that the game dump was incomplete.

## EXP-060

- **Date:** 2026-07-31
- **Commit:** [a915330](https://github.com/Sh-TB/sharpemuT24/commit/a915330)
- **Status:** CONFIRMED
- **Question:** Does the complete dump fix IL2CPP init?
- **Finding:** Complete dump verified — IL2CPP init WORKS, metadata loaded, crash chain resolved. New blocker is AssetGarbageCollectorHelper semaphore stall.
- **Root Cause:** Complete dump fixes IL2CPP init
- **Related EXPs:** EXP-059, EXP-061
- **Current Impact:** IL2CPP init works with complete dump.

## EXP-061

- **Date:** 2026-07-31
- **Commit:** [b28cce2](https://github.com/Sh-TB/sharpemuT24/commit/b28cce2)
- **Status:** CRITICAL CORRECTION
- **Question:** Is the eboot.bin the correct Yatzi dump?
- **Finding:** MIXED DUMP DETECTED — old eboot (7.7MB) was Dreaming Sarah, not Yatzi! All EXP-035..058 addresses were invalid because they were from the wrong game.
- **Root Cause:** Wrong eboot.bin (Dreaming Sarah instead of Yatzi)
- **Related EXPs:** EXP-035..058 ALL INVALID
- **Current Impact:** ALL EXP-035..058 conclusions invalidated. Re-investigation needed with correct dump.

## EXP-062

- **Date:** 2026-07-31
- **Commit:** [89ad82e](https://github.com/Sh-TB/sharpemuT24/commit/89ad82e)
- **Status:** SUPERSEDED BY EXP-081
- **Question:** Does FAST_PATH=0 cause deadlock?
- **Finding:** Semaphore deadlock confirmed — SignalSema NEVER called. 14 threads blocked. FAST_PATH=0 reported as causing deadlock.
- **Root Cause:** Reported: deadlock from SignalSema never being called
- **Related EXPs:** EXP-063, EXP-081
- **Current Impact:** Originally reported FAST_PATH=0 causes deadlock. EXP-081 challenges this — with current codebase (post-EXP-065), FAST_PATH=0 may work.

## EXP-063

- **Date:** 2026-07-31
- **Commit:** [6a1819d](https://github.com/Sh-TB/sharpemuT24/commit/6a1819d)
- **Status:** SUPERSEDED BY EXP-081
- **Question:** Does FAST_PATH=1 resolve the deadlock?
- **Finding:** FAST_PATH=1 resolves semaphore deadlock — game reaches Unity game manager loading. New crash at RIP=0 (NULL execute).
- **Root Cause:** FAST_PATH=1 as workaround for deadlock
- **Related EXPs:** EXP-062, EXP-064, EXP-081
- **Current Impact:** FAST_PATH=1 was adopted as workaround. EXP-081 proves this was wrong — it causes the NULL execute crash.

## EXP-064

- **Date:** 2026-07-31
- **Commit:** [202e54d](https://github.com/Sh-TB/sharpemuT24/commit/202e54d)
- **Status:** CONFIRMED
- **Question:** What causes the NULL execute crashes?
- **Finding:** NULL execute root cause = IL2CPP stubs return NULL. Host stack corruption after 1004 recoveries. Same as 3 other Unity/IL2CPP games.
- **Root Cause:** IL2CPP stubs return NULL → host stack corruption
- **Related EXPs:** EXP-063, EXP-065
- **Current Impact:** Identified NULL execute + stack corruption pattern.

## EXP-065

- **Date:** 2026-07-31
- **Commit:** [47274be](https://github.com/Sh-TB/sharpemuT24/commit/47274be)
- **Status:** PARTIAL
- **Question:** Does heap allocation fix the stack corruption?
- **Finding:** Heap allocation fix for POSIX signal handler context buffer (stackalloc → NativeMemory.AllocZeroed). Stack smashing persists from deeper source.
- **Root Cause:** Partial: stackalloc replaced, but deeper corruption remains
- **Related EXPs:** EXP-064, EXP-066
- **Current Impact:** Partial fix applied. Stack smashing still occurs after many recoveries.

## EXP-066

- **Date:** 2026-07-31
- **Commit:** [137f3d7](https://github.com/Sh-TB/sharpemuT24/commit/137f3d7)
- **Status:** SUPERSEDED
- **Question:** Does fixing EXP-034 re-patching fix the NULL executes?
- **Finding:** Root cause = EXP-034 re-patching fails (0/232). Stubs use INT3 not DecideIl2cppReturnValue. Host-side stack corruption confirmed.
- **Root Cause:** EXP-034 re-patching fails
- **Related EXPs:** EXP-065, EXP-067
- **Current Impact:** Superseded: EXP-067 proved re-patching was unnecessary.

## EXP-067

- **Date:** 2026-07-31
- **Commit:** [45af2a2](https://github.com/Sh-TB/sharpemuT24/commit/45af2a2)
- **Status:** CONFIRMED
- **Question:** Is re-patching necessary?
- **Finding:** Re-patching unnecessary — resolver returns real addresses directly. NULL executes are task-submission issue, NOT IL2CPP stubs.
- **Root Cause:** NULL executes are task-submission issue (dispatcher never sets [worker+0xF8])
- **Related EXPs:** EXP-066, EXP-068
- **Current Impact:** Corrected EXP-066: re-patching is not the issue. Task submission is.

## EXP-068

- **Date:** 2026-07-31
- **Commit:** [936a53c](https://github.com/Sh-TB/sharpemuT24/commit/936a53c)
- **Status:** CONFIRMED
- **Question:** What is the FAST_PATH tension?
- **Finding:** FAST_PATH tension confirmed — SignalSema never called. Same root cause as EXP-036/062. Need proper semaphore scheduling.
- **Root Cause:** FAST_PATH=1 vs FAST_PATH=0 tension (both have issues)
- **Related EXPs:** EXP-036, EXP-062, EXP-069
- **Current Impact:** Identified the fundamental tension between FAST_PATH settings.

## EXP-069

- **Date:** 2026-07-31
- **Commit:** [3c60edc](https://github.com/Sh-TB/sharpemuT24/commit/3c60edc)
- **Status:** CONFIRMED
- **Question:** Is SignalSema imported and implemented?
- **Finding:** SignalSema IS imported and implemented but NEVER called — code path issue, not missing HLE.
- **Root Cause:** SignalSema code path never reached
- **Related EXPs:** EXP-068, EXP-070
- **Current Impact:** Confirmed SignalSema HLE exists but is never invoked.

## EXP-070

- **Date:** 2026-07-31
- **Commit:** [9304030](https://github.com/Sh-TB/sharpemuT24/commit/9304030)
- **Status:** CONFIRMED
- **Question:** Where is the gate that skips SignalSema?
- **Finding:** GATE FOUND — cmp byte [rbx+0x108], 0 + jne skips SignalSema. Flag=0x01 at runtime. FAST_PATH-independent.
- **Root Cause:** Gate at 0x800AA0207 skips SignalSema when [rbx+0x108]!=0
- **Related EXPs:** EXP-069, EXP-071
- **Current Impact:** Found the gate instruction that skips SignalSema.

## EXP-071

- **Date:** 2026-07-31
- **Commit:** [a59f6a6](https://github.com/Sh-TB/sharpemuT24/commit/a59f6a6)
- **Status:** SUPERSEDED BY EXP-079
- **Question:** What is [rbx+0x108]?
- **Finding:** [rbx+0x108] is tagged pointer to unresolved dependency. CLEAR function never called. Dependency never resolved.
- **Root Cause:** Tagged pointer to unresolved dependency
- **Related EXPs:** EXP-070, EXP-072
- **Current Impact:** Superseded: EXP-079 proved [rbx+0x108] is a byte flag (0x01), not a tagged pointer. Upper bytes are heap garbage.

## EXP-072

- **Date:** 2026-07-31
- **Commit:** [3511466](https://github.com/Sh-TB/sharpemuT24/commit/3511466)
- **Status:** CONFIRMED — DIAGNOSTIC PATCH
- **Question:** Does NOPping the gate allow SignalSema to fire?
- **Finding:** NOP gate patch CONFIRMED — SignalSema fires, 0 NULL executes, 300x more execution, no crash. BUT: this is a diagnostic patch, not a fix.
- **Root Cause:** Diagnostic: NOPping gate allows SignalSema (but signals wrong handle)
- **Related EXPs:** EXP-071, EXP-073
- **Current Impact:** Diagnostic patch confirmed. Not a permanent fix.

## EXP-073

- **Date:** 2026-07-31
- **Commit:** [d1a90df](https://github.com/Sh-TB/sharpemuT24/commit/d1a90df)
- **Status:** CONFIRMED — DIAGNOSTIC PATCH
- **Question:** Does the 11-byte NOP (including jmp) fix the crash?
- **Finding:** 11-byte NOP (includes jmp) — SignalSema fires 13141 times, 0 NULL executes, 0 crashes, game actively running. BUT: signals wrong sema handle.
- **Root Cause:** Diagnostic: 11-byte NOP prevents crash but signals wrong sema
- **Related EXPs:** EXP-072, EXP-074
- **Current Impact:** Diagnostic patch. Created artificial execution path. Removed in EXP-080.

## EXP-074

- **Date:** 2026-07-31
- **Commit:** [1204062](https://github.com/Sh-TB/sharpemuT24/commit/1204062)
- **Status:** CONFIRMED
- **Question:** Does the game reach rendering with the NOP?
- **Finding:** Game does NOT reach rendering — SignalSema fires on wrong handles, workers still spin on 0x5C. Rendering not reached.
- **Root Cause:** NOP doesn't fix the underlying issue
- **Related EXPs:** EXP-073, EXP-075
- **Current Impact:** Confirmed NOP is insufficient for rendering.

## EXP-075

- **Date:** 2026-07-31
- **Commit:** [64b43b0](https://github.com/Sh-TB/sharpemuT24/commit/64b43b0)
- **Status:** SUPERSEDED BY EXP-079
- **Question:** Should CLEAR function signal 0x5C?
- **Finding:** CLEAR function should signal 0x5C but async dependency never completes. NOP uses wrong handle (0x5F vs 0x5C).
- **Root Cause:** CLEAR never called; dependency never completes
- **Related EXPs:** EXP-074, EXP-076
- **Current Impact:** Superseded: EXP-079 proved CLEAR is a C++ destructor, not a dependency callback.

## EXP-076

- **Date:** 2026-07-31
- **Commit:** [b0b641d](https://github.com/Sh-TB/sharpemuT24/commit/b0b641d)
- **Status:** CORRECTED BY EXP-077/079
- **Question:** What is the dependency at [rbx+0x108]?
- **Finding:** Dependency is chain ptr to prev worker. [rbx+0xf8] set by PRX (170 sites, never reached). Root cause = missing GPU/graphics init.
- **Root Cause:** Missing GPU/graphics init (WRONG)
- **Related EXPs:** EXP-075, EXP-077
- **Current Impact:** CORRECTED: EXP-077 proved GPU init is NOT the blocker. EXP-079 proved [rbx+0x108] is a byte flag, not a chain pointer.

## EXP-077

- **Date:** 2026-07-31
- **Commit:** [a2982c9](https://github.com/Sh-TB/sharpemuT24/commit/a2982c9)
- **Status:** CONFIRMED
- **Question:** Is GPU init the blocker?
- **Finding:** GPU init is NOT the blocker — same semaphore spin class. Main thread reaches GPU memory alloc but stalls on PRX WaitSema. Correction to EXP-076.
- **Root Cause:** GPU init is downstream, not causal
- **Related EXPs:** EXP-076, EXP-078
- **Current Impact:** Corrected EXP-076. GPU is downstream.

## EXP-078

- **Date:** 2026-07-31
- **Commit:** [c839ae3](https://github.com/Sh-TB/sharpemuT24/commit/c839ae3)
- **Status:** CONFIRMED — BUT NOP-CONTAMINATED
- **Question:** Is handle 0x5C ever signaled?
- **Finding:** CASE 1 CONFIRMED — handle 0x5C NEVER signaled (0/5.7M). Workers signal wrong handles (odd vs even). Tight spin loop.
- **Root Cause:** 0x5C never signaled (with NOP active)
- **Related EXPs:** EXP-077, EXP-079
- **Current Impact:** Confirmed with NOP active. EXP-080 proved this finding was NOP-contaminated.

## EXP-079

- **Date:** 2026-07-31
- **Commit:** [d13b8c9](https://github.com/Sh-TB/sharpemuT24/commit/d13b8c9)
- **Status:** CONFIRMED
- **Question:** What does CLEAR (0x800A9F750) actually do? What is [rbx+0x108]?
- **Finding:** CLEAR is a C++ destructor (not a dependency callback). [rbx+0x108] is a byte flag (low byte 0x01), not a tagged pointer. Upper bytes are heap garbage.
- **Root Cause:** CORRECTED EXP-071/075/076: [rbx+0x108] is byte flag; CLEAR is destructor
- **Related EXPs:** EXP-071, EXP-075, EXP-076, EXP-080
- **Current Impact:** Major correction to multiple prior EXPs.

## EXP-080

- **Date:** 2026-07-31
- **Commit:** [d13b8c9](https://github.com/Sh-TB/sharpemuT24/commit/d13b8c9)
- **Status:** CONFIRMED
- **Question:** Does the clean run (no NOP) reach il2cpp_init? Does it reach array_proc?
- **Finding:** Clean run NEVER reaches il2cpp_init. 100,000+ NULL execute faults. FAST_PATH=1 causes workers to race ahead of dispatcher. EXP-079's 'array_proc corrupted count' was NOP-contaminated and not reproducible.
- **Root Cause:** FAST_PATH=1 causes worker NULL crash before il2cpp_init
- **Related EXPs:** EXP-079, EXP-081
- **Current Impact:** Proved NOP contamination. Retracted EXP-079's array_proc claim.

## EXP-081

- **Date:** 2026-07-31
- **Commit:** [97db9fc](https://github.com/Sh-TB/sharpemuT24/commit/97db9fc)
- **Status:** CONFIRMED — PENDING VALIDATION
- **Question:** Why are worker task function pointers [worker+0xF8] NULL?
- **Finding:** SHARPEMU_SEMA_FAST_PATH=1 causes WaitSema to return immediately, making workers race ahead of the dispatcher and call [worker+0xF8]=NULL. FAST_PATH=0 eliminates this: 0 NULL executes, il2cpp_init called, Unity job system starts, graphics threads created.
- **Root Cause:** FAST_PATH=1 (pending full validation)
- **Related EXPs:** EXP-036, EXP-062, EXP-063, EXP-068
- **Current Impact:** Root cause found. FAST_PATH=0 proposed as fix. Needs validation that EXP-062 deadlock doesn't recur.

---

## Current True Blocker (after EXP-081)

**Pending validation:** FAST_PATH=0 eliminates the worker NULL [rbx+0xF8] crash, but must confirm the EXP-062 deadlock doesn't recur.

If FAST_PATH=0 is validated:
- New crash at 0x80080684D (NULL ptr in Unity metadata iteration) is the next blocker

If FAST_PATH=0 causes deadlock (as EXP-062 reported):
- SignalSema source must be investigated
- The semaphore synchronization chain needs proper implementation
