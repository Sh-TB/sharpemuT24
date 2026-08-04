#!/usr/bin/env python3
"""Generate YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md from all EXP data."""

EXPS = [
    # (num, date, commit, status, question, finding, root_cause, related, impact)
    ("026", "2026-07-28", "08c0735", "CONFIRMED", 
     "Does the IL2CPP symbol resolver BST algorithm work correctly?",
     "Synthetic x86-64 CPU emulator finds all 239/239 IL2CPP symbols. Algorithm definitively correct. Reference RBTree agrees.",
     "None — resolver algorithm is correct",
     "EXP-028 (continued investigation)",
     "Closed: resolver algorithm verified correct. Mismatch was elsewhere."),

    ("027", "2026-07-28", "08c0735", "CONFIRMED",
     "Is CPU instruction emulation correct (test/lea/cmovns/cmov conditions)?",
     "Host CPU, Unicorn engine, and synthetic Python CPU all agree on test/lea/cmovns/cmovns sequence (T4: 10/10) and all 16 cmov conditions (T16: 768/768).",
     "None — CPU instruction emulation is correct",
     "EXP-028 (Method B continued)",
     "Closed: CPU emulation verified correct. Divergence was elsewhere."),

    ("028", "2026-07-29", "f1d0968", "CONFIRMED",
     "Find the first divergence between SharpEmu and reference CPU execution",
     "strcmp GOT slot points to freed memory — the GOT was being set up correctly but the target string was in a region that got freed/moved.",
     "strcmp GOT pointing to freed memory",
     "EXP-026, EXP-027",
     "Fixed GOT lifetime. Enabled IL2CPP resolver to work."),

    ("029", "2026-07-29", "13d7a4c", "CONFIRMED",
     "Why does the IL2CPP BST strcmp fail after resolver runs?",
     "strcmp GOT points to freed memory — the trampoline lifetime was too short.",
     "Trampoline/GOT lifetime management",
     "EXP-028, EXP-030",
     "Root cause of resolver crash identified."),

    ("030", "2026-07-29", "ee1ed98", "SUPERSEDED",
     "Fix trampoline lifetime to prevent GOT invalidation",
     "Trampoline lifetime fix attempted, root cause revised — the issue was deeper than just lifetime.",
     "Revised: see EXP-031/032",
     "EXP-029, EXP-031",
     "Superseded by EXP-031/032 findings."),

    ("031", "2026-07-29", "a8d5c09", "SUPERSEDED",
     "Narrow down the execution context issue in TryCallGuestFunction",
     "Root cause narrowed to TryCallGuestFunction execution context — return value not propagating correctly.",
     "Revised: see EXP-032",
     "EXP-030, EXP-032",
     "Led to EXP-032's definitive root cause."),

    ("032", "2026-07-29", "3c186a4", "CONFIRMED",
     "Why does the resolver return 0 (NULL) for IL2CPP function addresses?",
     "ROOT CAUSE FOUND: CpuContext.Rax never updated from nativeReturn — CallNativeEntry return value (int→long truncation + missing CpuContext update).",
     "CallNativeEntry int→long truncation + CpuContext.Rax not updated",
     "EXP-031, EXP-033",
     "Fixed: return value propagation. All 232 IL2CPP functions now resolve correctly."),

    ("033", "2026-07-29", "af7d8b8", "CONFIRMED",
     "Why does the game crash after the resolver completes?",
     "Post-resolver crash from NULL execute fault limit (100000) — guest code calls NULL function pointers.",
     "NULL function pointer calls in guest code (IL2CPP stubs)",
     "EXP-032, EXP-034",
     "Identified NULL execute as the next blocker."),

    ("034", "2026-07-29", "0e13c17", "SUPERSEDED",
     "Are IL2CPP globals populated after resolver runs?",
     "Globals ARE populated (all 232 real func_impl addresses found). But fake heap stubs still cause NULL calls — re-patching import stubs with real addresses fails (0/232 patched).",
     "Re-patching fails because NID-to-name lookup fails for eboot imports",
     "EXP-033, EXP-035, EXP-066",
     "Superseded: EXP-067 proved re-patching was unnecessary (resolver returns real addresses directly)."),

    ("035", "2026-07-29", "56bd06c", "SUPERSEDED",
     "Is the fake heap the cause of NULL executes?",
     "Fake heap disproven — root cause is uninitialized task descriptor. Workers call [rbx+0xF8]=NULL because task function pointer is never set.",
     "Uninitialized task descriptor [rbx+0xF8]=NULL",
     "EXP-034, EXP-064",
     "Superseded: EXP-081 found the real reason [rbx+0xF8] is NULL (FAST_PATH=1)."),

    ("036", "2026-07-29", "7986cbe", "CONFIRMED — REPEATED IN EXP-081",
     "Why is il2cpp_init never reached?",
     "SHARPEMU_SEMA_FAST_PATH=1 was causing il2cpp_init starvation — workers spin and starve the main thread.",
     "FAST_PATH=1 makes WaitSema return immediately, starving main thread",
     "EXP-062, EXP-063, EXP-068, EXP-081",
     "This finding was CORRECT but was overridden by EXP-063 which switched back to FAST_PATH=1. EXP-081 re-discovered this same root cause."),

    ("037", "2026-07-29", "5a5d782", "SUPERSEDED",
     "Are IL2CPP static initializers running?",
     "IL2CPP static initializers not running — empty init_array. No .init_array entries found.",
     "Missing init_array (later found to be a dump completeness issue)",
     "EXP-038, EXP-059, EXP-061",
     "Superseded: EXP-061 found the dump was mixed (Dreaming Sarah eboot, not Yatzi)."),

    ("038", "2026-07-30", "6f7a979", "SUPERSEDED",
     "Is the DT_INIT callback (rdx parameter) being passed correctly?",
     "DT_INIT callback (rdx) not passed — IL2CPP registration never runs. rdx=0 instead of callback address.",
     "Missing rdx parameter to DT_INIT",
     "EXP-037, EXP-039",
     "Superseded: EXP-039 disproved the rdx hypothesis."),

    ("039", "2026-07-30", "1e13915", "CONFIRMED",
     "Does passing rdx fix the IL2CPP registration?",
     "DT_INIT rdx hypothesis disproven — circular dependency in il2cpp_init. Passing rdx doesn't help because the registration code isn't reached.",
     "Circular dependency in il2cpp_init",
     "EXP-038, EXP-040",
     "Closed: rdx hypothesis rejected."),

    ("040", "2026-07-30", "f41736c", "CONFIRMED",
     "Are hash table entries being filled?",
     "Hash table entries never filled — workaround clears original crash but doesn't fix the root cause.",
     "Hash table not populated by IL2CPP registration",
     "EXP-039, EXP-041",
     "Identified hash table population as the issue."),

    ("041", "2026-07-30", "d76f7bf", "CONFIRMED",
     "What is the init order issue?",
     "Init order issue — il2cpp_init called BEFORE hash lookup sets 0x801E51240. The global metadata pointer is NULL when il2cpp_init runs.",
     "il2cpp_init runs before metadata global is set",
     "EXP-040, EXP-042",
     "Identified initialization ordering problem."),

    ("042", "2026-07-30", "813a5d2", "CONFIRMED",
     "Does metadata lookup return a valid object?",
     "Metadata lookup returns valid object — 0x801E51240 needs pre-init. The metadata global must be set before il2cpp_init.",
     "0x801E51240 (metadata global) needs pre-init",
     "EXP-041, EXP-043",
     "Confirmed metadata global needs initialization."),

    ("043", "2026-07-30", "7a7b4ad", "SUPERSEDED",
     "Is there a pre-init mechanism that's missing?",
     "Pre-init mechanism missing — PRX DT_INIT flag forces jump to INT3. The PRX module initialization doesn't run.",
     "PRX DT_INIT flag issue",
     "EXP-042, EXP-044",
     "Superseded: EXP-044 found INT3 is just ELF padding."),

    ("044", "2026-07-30", "7465613", "CONFIRMED",
     "Is the INT3 at PRX entry a module_start indicator?",
     "INT3 is ELF padding (not module_start) — fini_array has 11 entries. The INT3 is just alignment padding.",
     "None — INT3 is benign padding",
     "EXP-043, EXP-045",
     "Closed: INT3 hypothesis rejected."),

    ("045", "2026-07-30", "aedf782", "CONFIRMED",
     "Does eboot fini_array contain the pre-init mechanism?",
     "eboot fini_array found (20 entries) but not root cause — the entries are destructors, not initializers.",
     "None — fini_array is destructors only",
     "EXP-044, EXP-046",
     "Closed: fini_array hypothesis rejected."),

    ("046", "2026-07-30", "4721b59", "CONFIRMED",
     "Is the crash from call #7 or call #8?",
     "Crash is from call #8, not #7 — metadata lookup returns non-zero. The crash happens after call #7 returns.",
     "Call #8 crash after metadata lookup",
     "EXP-045, EXP-047",
     "Narrowed crash to call #8."),

    ("047", "2026-07-30", "3428a8f", "CONFIRMED",
     "Do three fixes prevent the callback crash?",
     "Three fixes prevent callback crash but cascade remains — fixing the immediate crash reveals more crashes downstream.",
     "Cascade of crashes after fixing each layer",
     "EXP-046, EXP-048",
     "Identified cascade pattern."),

    ("048", "2026-07-30", "538c4da", "CONFIRMED",
     "Does a callback stub allow il2cpp_init to progress?",
     "Callback stub-ret allows il2cpp_init to progress — workers created. The stub returns 0 for an unspecified callback.",
     "Missing callback HLE function",
     "EXP-047, EXP-049",
     "Enabled il2cpp_init to run. Workers created."),

    ("049", "2026-07-30", "db3d578", "CONFIRMED",
     "What is at 0x801E51220?",
     "NULL pointer at 0x801E51220 — same class as 0x801E51240. Systemic pattern of uninitialized metadata globals.",
     "Systemic uninitialized metadata globals",
     "EXP-048, EXP-050",
     "Identified pattern of NULL metadata globals."),

    ("050", "2026-07-30", "ea58673", "CONFIRMED",
     "Why is hash lookup skipped?",
     "Hash lookup skipped by 15+ conditional jumps — stub cleared first cascade. The lookup function returns early due to NULL inputs.",
     "Hash lookup returns early due to NULL inputs",
     "EXP-049, EXP-051",
     "Identified why hash lookup was being skipped."),

    ("051", "2026-07-30", "30e6215", "CONFIRMED",
     "Do buffer+NOP+loop fixes resolve the crash?",
     "Buffer+NOP+loop fix tested — all cause new crashes, reverted. None of the attempted fixes work.",
     "None — all fixes reverted",
     "EXP-050, EXP-052",
     "Closed: all attempted fixes failed."),

    ("052", "2026-07-30", "0f6db8d", "CONFIRMED",
     "What mechanism is missing for IL2CPP registration?",
     "Missing mechanism identified — wrapper 0x800805AE0 = il2cpp_codegen_register, called indirectly, never invoked on SharpEmu.",
     "il2cpp_codegen_register (0x800805AE0) never called",
     "EXP-051, EXP-053",
     "Identified il2cpp_codegen_register as the missing function."),

    ("053", "2026-07-30", "6b62771", "CONFIRMED",
     "Is wrapper 0x800805AE0 ever called?",
     "Wrapper 0x800805AE0 NEVER called — missing walker confirmed. Static table 0x1CC0080 is string fragment pool not Il2CppMetadataRegistration.",
     "Wrapper never called; static table misidentified",
     "EXP-052, EXP-054",
     "Confirmed wrapper is never invoked."),

    ("054", "2026-07-30", "a101e62", "CONFIRMED",
     "Where is Il2CppCodeRegistration?",
     "Il2CppCodeRegistration found at 0x8086E9000. Baseline crash chain captured. Stub now conditional.",
     "Il2CppCodeRegistration at 0x8086E9000",
     "EXP-053, EXP-055",
     "Found the CodeRegistration struct."),

    ("055", "2026-07-30", "5f89b31", "CONFIRMED",
     "Where is MetadataRegistration?",
     "MetadataRegistration found at 0x80885C580. PRX DT_INIT invalid (ELF header). Upstream has same unsolved issue.",
     "MetadataRegistration at 0x80885C580",
     "EXP-054, EXP-056",
     "Found the MetadataRegistration struct."),

    ("056", "2026-07-30", "d325f54", "CONFIRMED",
     "Why are structs populated but nothing works?",
     "Major pivot — structs already populated. Root cause is missing CONSUMER function that reads the metadata.",
     "Missing consumer function (not missing data)",
     "EXP-055, EXP-057",
     "Pivoted from 'missing data' to 'missing consumer'."),

    ("057", "2026-07-30", "77bd7dc", "CONFIRMED",
     "What is the consumer function?",
     "MetaReg access via metadataUsages indirection. Call #7 (0x804F23320) is consumer candidate with 0x38-byte stride loops.",
     "Call #7 (0x804F23320) is the consumer",
     "EXP-056, EXP-058",
     "Identified call #7 as the metadata consumer."),

    ("058", "2026-07-30", "d928189", "CONFIRMED",
     "Does call #7 execute successfully?",
     "Call #7 entered but returns early — metadata loader 0x804F04750 fails (missing metadata file). Root cause identified.",
     "Missing metadata file (global-metadata.dat)",
     "EXP-057, EXP-059",
     "Identified missing metadata file as root cause."),

    ("059", "2026-07-31", "efd65f5", "CONFIRMED",
     "What is the real structure at 0x8086E9000?",
     "Ground-truth diff with Unity 2022.3.5f1 source — struct at 0x8086E9000 is Il2CodeGenModule not CodeReg. Root cause is DUMP COMPLETENESS (missing PRX + metadata).",
     "Incomplete game dump (missing Il2cppUserAssemblies.prx + global-metadata.dat)",
     "EXP-058, EXP-060",
     "Identified that the game dump was incomplete."),

    ("060", "2026-07-31", "a915330", "CONFIRMED",
     "Does the complete dump fix IL2CPP init?",
     "Complete dump verified — IL2CPP init WORKS, metadata loaded, crash chain resolved. New blocker is AssetGarbageCollectorHelper semaphore stall.",
     "Complete dump fixes IL2CPP init",
     "EXP-059, EXP-061",
     "IL2CPP init works with complete dump."),

    ("061", "2026-07-31", "b28cce2", "CRITICAL CORRECTION",
     "Is the eboot.bin the correct Yatzi dump?",
     "MIXED DUMP DETECTED — old eboot (7.7MB) was Dreaming Sarah, not Yatzi! All EXP-035..058 addresses were invalid because they were from the wrong game.",
     "Wrong eboot.bin (Dreaming Sarah instead of Yatzi)",
     "EXP-035..058 ALL INVALID",
     "ALL EXP-035..058 conclusions invalidated. Re-investigation needed with correct dump."),

    ("062", "2026-07-31", "89ad82e", "SUPERSEDED BY EXP-081",
     "Does FAST_PATH=0 cause deadlock?",
     "Semaphore deadlock confirmed — SignalSema NEVER called. 14 threads blocked. FAST_PATH=0 reported as causing deadlock.",
     "Reported: deadlock from SignalSema never being called",
     "EXP-063, EXP-081",
     "Originally reported FAST_PATH=0 causes deadlock. EXP-081 challenges this — with current codebase (post-EXP-065), FAST_PATH=0 may work."),

    ("063", "2026-07-31", "6a1819d", "SUPERSEDED BY EXP-081",
     "Does FAST_PATH=1 resolve the deadlock?",
     "FAST_PATH=1 resolves semaphore deadlock — game reaches Unity game manager loading. New crash at RIP=0 (NULL execute).",
     "FAST_PATH=1 as workaround for deadlock",
     "EXP-062, EXP-064, EXP-081",
     "FAST_PATH=1 was adopted as workaround. EXP-081 proves this was wrong — it causes the NULL execute crash."),

    ("064", "2026-07-31", "202e54d", "CONFIRMED",
     "What causes the NULL execute crashes?",
     "NULL execute root cause = IL2CPP stubs return NULL. Host stack corruption after 1004 recoveries. Same as 3 other Unity/IL2CPP games.",
     "IL2CPP stubs return NULL → host stack corruption",
     "EXP-063, EXP-065",
     "Identified NULL execute + stack corruption pattern."),

    ("065", "2026-07-31", "47274be", "PARTIAL",
     "Does heap allocation fix the stack corruption?",
     "Heap allocation fix for POSIX signal handler context buffer (stackalloc → NativeMemory.AllocZeroed). Stack smashing persists from deeper source.",
     "Partial: stackalloc replaced, but deeper corruption remains",
     "EXP-064, EXP-066",
     "Partial fix applied. Stack smashing still occurs after many recoveries."),

    ("066", "2026-07-31", "137f3d7", "SUPERSEDED",
     "Does fixing EXP-034 re-patching fix the NULL executes?",
     "Root cause = EXP-034 re-patching fails (0/232). Stubs use INT3 not DecideIl2cppReturnValue. Host-side stack corruption confirmed.",
     "EXP-034 re-patching fails",
     "EXP-065, EXP-067",
     "Superseded: EXP-067 proved re-patching was unnecessary."),

    ("067", "2026-07-31", "45af2a2", "CONFIRMED",
     "Is re-patching necessary?",
     "Re-patching unnecessary — resolver returns real addresses directly. NULL executes are task-submission issue, NOT IL2CPP stubs.",
     "NULL executes are task-submission issue (dispatcher never sets [worker+0xF8])",
     "EXP-066, EXP-068",
     "Corrected EXP-066: re-patching is not the issue. Task submission is."),

    ("068", "2026-07-31", "936a53c", "CONFIRMED",
     "What is the FAST_PATH tension?",
     "FAST_PATH tension confirmed — SignalSema never called. Same root cause as EXP-036/062. Need proper semaphore scheduling.",
     "FAST_PATH=1 vs FAST_PATH=0 tension (both have issues)",
     "EXP-036, EXP-062, EXP-069",
     "Identified the fundamental tension between FAST_PATH settings."),

    ("069", "2026-07-31", "3c60edc", "CONFIRMED",
     "Is SignalSema imported and implemented?",
     "SignalSema IS imported and implemented but NEVER called — code path issue, not missing HLE.",
     "SignalSema code path never reached",
     "EXP-068, EXP-070",
     "Confirmed SignalSema HLE exists but is never invoked."),

    ("070", "2026-07-31", "9304030", "CONFIRMED",
     "Where is the gate that skips SignalSema?",
     "GATE FOUND — cmp byte [rbx+0x108], 0 + jne skips SignalSema. Flag=0x01 at runtime. FAST_PATH-independent.",
     "Gate at 0x800AA0207 skips SignalSema when [rbx+0x108]!=0",
     "EXP-069, EXP-071",
     "Found the gate instruction that skips SignalSema."),

    ("071", "2026-07-31", "a59f6a6", "SUPERSEDED BY EXP-079",
     "What is [rbx+0x108]?",
     "[rbx+0x108] is tagged pointer to unresolved dependency. CLEAR function never called. Dependency never resolved.",
     "Tagged pointer to unresolved dependency",
     "EXP-070, EXP-072",
     "Superseded: EXP-079 proved [rbx+0x108] is a byte flag (0x01), not a tagged pointer. Upper bytes are heap garbage."),

    ("072", "2026-07-31", "3511466", "CONFIRMED — DIAGNOSTIC PATCH",
     "Does NOPping the gate allow SignalSema to fire?",
     "NOP gate patch CONFIRMED — SignalSema fires, 0 NULL executes, 300x more execution, no crash. BUT: this is a diagnostic patch, not a fix.",
     "Diagnostic: NOPping gate allows SignalSema (but signals wrong handle)",
     "EXP-071, EXP-073",
     "Diagnostic patch confirmed. Not a permanent fix."),

    ("073", "2026-07-31", "d1a90df", "CONFIRMED — DIAGNOSTIC PATCH",
     "Does the 11-byte NOP (including jmp) fix the crash?",
     "11-byte NOP (includes jmp) — SignalSema fires 13141 times, 0 NULL executes, 0 crashes, game actively running. BUT: signals wrong sema handle.",
     "Diagnostic: 11-byte NOP prevents crash but signals wrong sema",
     "EXP-072, EXP-074",
     "Diagnostic patch. Created artificial execution path. Removed in EXP-080."),

    ("074", "2026-07-31", "1204062", "CONFIRMED",
     "Does the game reach rendering with the NOP?",
     "Game does NOT reach rendering — SignalSema fires on wrong handles, workers still spin on 0x5C. Rendering not reached.",
     "NOP doesn't fix the underlying issue",
     "EXP-073, EXP-075",
     "Confirmed NOP is insufficient for rendering."),

    ("075", "2026-07-31", "64b43b0", "SUPERSEDED BY EXP-079",
     "Should CLEAR function signal 0x5C?",
     "CLEAR function should signal 0x5C but async dependency never completes. NOP uses wrong handle (0x5F vs 0x5C).",
     "CLEAR never called; dependency never completes",
     "EXP-074, EXP-076",
     "Superseded: EXP-079 proved CLEAR is a C++ destructor, not a dependency callback."),

    ("076", "2026-07-31", "b0b641d", "CORRECTED BY EXP-077/079",
     "What is the dependency at [rbx+0x108]?",
     "Dependency is chain ptr to prev worker. [rbx+0xf8] set by PRX (170 sites, never reached). Root cause = missing GPU/graphics init.",
     "Missing GPU/graphics init (WRONG)",
     "EXP-075, EXP-077",
     "CORRECTED: EXP-077 proved GPU init is NOT the blocker. EXP-079 proved [rbx+0x108] is a byte flag, not a chain pointer."),

    ("077", "2026-07-31", "a2982c9", "CONFIRMED",
     "Is GPU init the blocker?",
     "GPU init is NOT the blocker — same semaphore spin class. Main thread reaches GPU memory alloc but stalls on PRX WaitSema. Correction to EXP-076.",
     "GPU init is downstream, not causal",
     "EXP-076, EXP-078",
     "Corrected EXP-076. GPU is downstream."),

    ("078", "2026-07-31", "c839ae3", "CONFIRMED — BUT NOP-CONTAMINATED",
     "Is handle 0x5C ever signaled?",
     "CASE 1 CONFIRMED — handle 0x5C NEVER signaled (0/5.7M). Workers signal wrong handles (odd vs even). Tight spin loop.",
     "0x5C never signaled (with NOP active)",
     "EXP-077, EXP-079",
     "Confirmed with NOP active. EXP-080 proved this finding was NOP-contaminated."),

    ("079", "2026-07-31", "d13b8c9", "CONFIRMED",
     "What does CLEAR (0x800A9F750) actually do? What is [rbx+0x108]?",
     "CLEAR is a C++ destructor (not a dependency callback). [rbx+0x108] is a byte flag (low byte 0x01), not a tagged pointer. Upper bytes are heap garbage.",
     "CORRECTED EXP-071/075/076: [rbx+0x108] is byte flag; CLEAR is destructor",
     "EXP-071, EXP-075, EXP-076, EXP-080",
     "Major correction to multiple prior EXPs."),

    ("080", "2026-07-31", "d13b8c9", "CONFIRMED",
     "Does the clean run (no NOP) reach il2cpp_init? Does it reach array_proc?",
     "Clean run NEVER reaches il2cpp_init. 100,000+ NULL execute faults. FAST_PATH=1 causes workers to race ahead of dispatcher. EXP-079's 'array_proc corrupted count' was NOP-contaminated and not reproducible.",
     "FAST_PATH=1 causes worker NULL crash before il2cpp_init",
     "EXP-079, EXP-081",
     "Proved NOP contamination. Retracted EXP-079's array_proc claim."),

    ("081", "2026-07-31", "97db9fc", "CONFIRMED — PENDING VALIDATION",
     "Why are worker task function pointers [worker+0xF8] NULL?",
     "SHARPEMU_SEMA_FAST_PATH=1 causes WaitSema to return immediately, making workers race ahead of the dispatcher and call [worker+0xF8]=NULL. FAST_PATH=0 eliminates this: 0 NULL executes, il2cpp_init called, Unity job system starts, graphics threads created.",
     "FAST_PATH=1 (pending full validation)",
     "EXP-036, EXP-062, EXP-063, EXP-068",
     "Root cause found. FAST_PATH=0 proposed as fix. Needs validation that EXP-062 deadlock doesn't recur."),
]

# Generate the EXP index table
print("Generating YATZI_EXP_INDEX.md...")
with open('/tmp/my-project/work/sharpemuT24/docs/diagnostics/YATZI_EXP_INDEX.md', 'w') as f:
    f.write("# Yatzi EXP Index\n\n")
    f.write("Quick-reference table of all EXP experiments.\n\n")
    f.write("| EXP | Date | Commit | Status | Key Finding | Next Dependency |\n")
    f.write("|-----|------|--------|--------|-------------|-----------------|\n")
    for num, date, commit, status, question, finding, root_cause, related, impact in EXPS:
        commit_url = f"[{commit}](https://github.com/Sh-TB/sharpemuT24/commit/{commit})"
        # Truncate finding for table
        short_finding = finding[:80] + "..." if len(finding) > 80 else finding
        f.write(f"| {num} | {date} | {commit_url} | {status} | {short_finding} | {related} |\n")
    f.write(f"\n**Total EXPs:** {len(EXPS)} (EXP-026 through EXP-081)\n")

print(f"Generated YATZI_EXP_INDEX.md with {len(EXPS)} entries")

# Generate the full knowledge base
print("Generating YATZI_KNOWLEDGE_BASE.md...")
with open('/tmp/my-project/work/sharpemuT24/docs/diagnostics/YATZI_KNOWLEDGE_BASE.md', 'w') as f:
    f.write("# Yatzi Debugging Knowledge Base\n\n")
    f.write("Complete index of all EXP experiments for the Yatzi (PPSA17697) game bringup.\n\n")
    f.write("---\n\n")
    
    for num, date, commit, status, question, finding, root_cause, related, impact in EXPS:
        f.write(f"## EXP-{num}\n\n")
        f.write(f"- **Date:** {date}\n")
        f.write(f"- **Commit:** [{commit}](https://github.com/Sh-TB/sharpemuT24/commit/{commit})\n")
        f.write(f"- **Status:** {status}\n")
        f.write(f"- **Question:** {question}\n")
        f.write(f"- **Finding:** {finding}\n")
        f.write(f"- **Root Cause:** {root_cause}\n")
        f.write(f"- **Related EXPs:** {related}\n")
        f.write(f"- **Current Impact:** {impact}\n\n")
    
    f.write("---\n\n")
    f.write("## Current True Blocker (after EXP-081)\n\n")
    f.write("**Pending validation:** FAST_PATH=0 eliminates the worker NULL [rbx+0xF8] crash, ")
    f.write("but must confirm the EXP-062 deadlock doesn't recur.\n\n")
    f.write("If FAST_PATH=0 is validated:\n")
    f.write("- New crash at 0x80080684D (NULL ptr in Unity metadata iteration) is the next blocker\n\n")
    f.write("If FAST_PATH=0 causes deadlock (as EXP-062 reported):\n")
    f.write("- SignalSema source must be investigated\n")
    f.write("- The semaphore synchronization chain needs proper implementation\n")

print(f"Generated YATZI_KNOWLEDGE_BASE.md with {len(EXPS)} entries")
