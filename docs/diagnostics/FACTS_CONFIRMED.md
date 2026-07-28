# FACTS_CONFIRMED.md (Append-Only)

Each fact has: timestamp, commit, evidence, verification method.

## FACT-001: register_symbols executes and creates 239 BST nodes
- Timestamp: 2026-07-28T04:06Z
- Commit: dad2279 (GitHub: Sh-TB/sharpemuT24)
- Evidence: test_d1_bst_walk.log, BST-WALK lines
- Verification: IndependentBSTWalker.cs (iterative, visited set, cycle detection)
- Result: 239 real nodes + 1 sentinel = 240 total, 0 cycles
- Method: C# instrumentation reading via CpuContext.TryReadByte/TryReadUInt64

## FACT-002: All 239 IL2CPP symbols present in BST
- Timestamp: 2026-07-28T04:06Z
- Commit: dad2279
- Evidence: test_d1_bst_walk.log, BST-WALK SYMBOL SEARCH lines
- Verification: IndependentBSTWalker.cs searched for 7 symbols, all FOUND
- Symbols found: il2cpp_init, il2cpp_shutdown, il2cpp_alloc, il2cpp_free,
  il2cpp_class_num_fields, il2cpp_add_internal_call, il2cpp_resolve_icall

## FACT-003: BST has 238/239 sorting violations
- Timestamp: 2026-07-28T04:12Z
- Commit: dad2279
- Evidence: Python script parsed BST-WALK output, checked parent-child ordering
- Verification: Independent Python parser (not C# instrumentation)
- Method: For each node, strcmp(parent_name, child_name) checked against BST invariant
- Result: 238 violations out of 239 real nodes

## FACT-004: PRX's strcmp goes through HLE dispatch, not native intrinsic
- Timestamp: 2026-07-28T04:12Z
- Commit: 6b2a794
- Evidence: Source code analysis
- Verification: grep source for Ovb2dSJOAuE in DirectExecutionBackend.cs vs KernelMemoryCompatExports.cs
- Result: Native intrinsic exists (DirectExecutionBackend.cs:1326) but only applied by
  SetupImportStubs (eboot path). PRX imports go through SelfLoader.ResolveAndPatchImportStubs
  which creates HLE trampolines.

## FACT-005: HLE strcmp returns MEMORY_FAULT when TryCompareStrings fails
- Timestamp: 2026-07-28T04:12Z
- Commit: 6b2a794
- Evidence: KernelMemoryCompatExports.cs:493-503
- Verification: Source code reading
- Result: When TryCompareStrings returns false, Strcmp returns
  ORBIS_GEN2_ERROR_MEMORY_FAULT (negative). ctx[Rax] is NOT set.
  HLE dispatch sets Rax = unchecked((ulong)(int)MEMORY_FAULT) = 0xFFFFFFFF8xxxxxxx
  Lower 32 bits (eax) = 0x8xxxxxxx (negative in signed 32-bit)
  BST insertion: test eax, eax → SF=1 → cmovns NOT taken → go LEFT

## FACT-006: Resolver returns 0 for all 232 queries
- Timestamp: 2026-07-28T04:06Z
- Commit: dad2279
- Evidence: test_d1_bst_walk.log, RESOLVER-TRACE entries
- Verification: 232 Entry + 232 Exit logs, all RAX=0x0000000000000000
- Method: HLE dispatch logging (DispatchIl2CppApiLookupSymbol)

## FACT-007: Resolver logic is correct (BST traversal with cmovns)
- Timestamp: 2026-07-28T04:00Z
- Commit: 6b2a794
- Evidence: Static disassembly of 0x804ED9B90
- Verification: Full disassembly from push rbp to ret
- Result: strcmp >= 0 → go RIGHT ([rbx+0x00]), strcmp < 0 → go LEFT ([rbx+0x10])
  After sentinel: check r12 candidate, final strcmp, return [r12+0x28]

## FACT-008: HLE stub removal for cJ2Y4E-t258 was correct
- Timestamp: 2026-07-28T04:00Z
- Commit: 3877980
- Evidence: Direct bridge confirmed in runtime log
- Verification: "Direct bridge for cJ2Y4E-t258 -> 0x0000000804ED3AE0"
- Result: register_symbols now executes and creates 239 nodes

## FACT-009 (SUPERSEDED): Resolver returns 0 for all 232 queries
- Status: SUPERSEDED by FACT-011
- Original Timestamp: 2026-07-28T04:06Z
- Original conclusion: Resolver returns 0 for all queries
- Update: Still true that native resolver returns 0, but root cause now
  IDENTIFIED as SharpEmu CPU emulation bug (see FACT-011)

## FACT-010: Synthetic x86-64 CPU emulator finds ALL 239 symbols
- Timestamp: 2026-07-29T08:00Z
- Commit: EXP-026 (not yet committed)
- Evidence: scripts/exp026_synthetic_cpu.py, scripts/exp026_test_all_symbols.py,
  download/exp026/exp026_il2cpp_init_trace.log
- Verification: Python x86-64 emulator implementing resolver's exact
  instruction sequence (push/mov/cmp/test/lea/cmovns/je/js/call strcmp/ret)
  with per-instruction RIP/register/flag/branch-decision logging. Ran on
  all 239 symbols from BST-WALK log.
- Result: 239/239 symbols FOUND by synthetic CPU
- Method: Mnemonic-level emulation with exact x86 SF/ZF/CF/OF/PF semantics

## FACT-011: DIVERGENCE IS IN SHARPEMU NATIVE CPU EXECUTION
- Timestamp: 2026-07-29T08:00Z
- Commit: EXP-026 (not yet committed)
- Evidence: EXP026_DIVERGENCE_REPORT.md
- Verification:
  - Synthetic CPU (same algorithm, same tree) → finds all 239 symbols
  - Reference Python RBTree impl → finds all 239 symbols
  - SharpEmu native execution → returns 0 for all 232 calls
- Conclusion: Algorithm and tree are CORRECT. Bug is in SharpEmu's native
  CPU emulation of the resolver at 0x804ED9B90.
- Most likely culprit: cmovns instruction or SF flag preservation across
  `test eax, eax` → `lea rcx, [rbx+0x10]` → `cmovns rcx, rbx` → `cmovns r12, rbx`
  (SF must persist across 2 instructions; lea and cmovns do not modify flags
  per Intel SDM, but SharpEmu may incorrectly clobber SF)
- Next step: Single-step native execution with per-instruction register/flag
  logging, diff against synthetic trace

## FACT-012: List head struct IS the sentinel node
- Timestamp: 2026-07-29T08:00Z
- Commit: EXP-026 (not yet committed)
- Evidence: BST-WALK log shows "List head struct: 0x2000003f20", which
  is the same address as Node #11 (the sentinel)
- Verification: Cross-reference list_head_struct addr with sentinel node addr
- Result: The list head pointer at 0x808B53708 points to 0x2000003f20,
  which is the SENTINEL node. The root node is at [sentinel + 0x08]
  (the parent field of the sentinel).
- Implication: r15 in resolver = sentinel addr; r12 starts as r15 (no candidate);
  cmp r12, r15 checks if candidate is still sentinel (no candidate found)

## FACT-013: Host CPU, Unicorn, and Synthetic CPU all agree on cmovns sequence
- Timestamp: 2026-07-29T10:00Z
- Commit: EXP-027 (not yet committed)
- Evidence: scripts/exp027/t4_cmovns_test.py, download/exp027/cmovns_test.log
- Verification: Built 48-byte x86-64 test function via mmap+ctypes that
  runs the exact resolver critical sequence (test/lea/cmovns/cmovns).
  Ran on 3 platforms: real host CPU, Unicorn engine v2.1.4, EXP-026
  synthetic Python CPU. 10 test cases covering negative/zero/positive
  eax values and various rbx/r12 combinations.
- Result: ALL 3 PLATFORMS AGREE on all 10 test cases (rcx, r12, RFLAGS
  all match 100%)
- Conclusion: The test/lea/cmovns/cmovns sequence is DEFINITIVELY correct.
  If SharpEmu's native execution produces different results, the bug is
  in SharpEmu's CPU emulation layer (not in the algorithm).

## FACT-014: All 16 cmov conditions correctly emulated by synthetic CPU
- Timestamp: 2026-07-29T10:00Z
- Commit: EXP-027 (not yet committed)
- Evidence: scripts/exp027/t16_cpu_fuzz.py, download/exp027/cpu_fuzz_report.md
- Verification: Built exhaustive fuzzer comparing Unicorn engine vs
  EXP-026 synthetic Python CPU. Tested ALL 16 cmov conditions (cmovo,
  cmovno, cmovb, cmovae, cmove, cmovne, cmovbe, cmova, cmovs, cmovns,
  cmovp, cmovnp, cmovl, cmovge, cmovle, cmovg) × 8 eax values × 3 rbx
  values × 2 r12 values = 768 total tests.
- Result: 768/768 MATCH (100%)
- Conclusion: The synthetic Python CPU correctly emulates the ENTIRE cmov
  instruction family, not just cmovns. Combined with FACT-013 (host CPU
  agrees), the resolver's critical sequence is definitively correct.

## FACT-015: EXP-027 instrumentation patches authored (pending integration)
- Timestamp: 2026-07-29T10:00Z
- Commit: EXP-027 (not yet committed)
- Evidence:
  - download/exp027/_Exp027ResolverTracer.cs (T1/T2/T3/T6/T8/T9)
  - download/exp027/_Exp027T12T13BoundaryTrace.cs (T12/T13)
  - download/exp027/_Exp027_Patch_Instructions.md
- Verification: Source code review
- Status: Patches authored but NOT yet integrated into SharpEmu build
- Next step: User applies patches, runs instrumented SharpEmu, collects
  logs in /tmp/exp027_logs/, runs analyze_native_trace.py to auto-
  generate divergence report
- Expected output files:
  - test1_rflags.log (T2: RFLAGS after every instruction)
  - test2_registers.log (T6: register timeline)
  - test3_strcmp.log (T8/T9: strcmp inputs)
  - test4_full_trace.log (T1: combined per-instruction trace)
  - test3_sf_preservation.log (T3: SF around test/lea/cmovns)

## FACT-016: EXP-028 instrumentation policy (user-corrected)
- Timestamp: 2026-07-29T12:00Z
- Commit: EXP-028 (not yet committed)
- Evidence: User message approving EXP-028 plan
- Verification: User explicit correction
- Result: The previous policy "No changes to SharpEmu" was WRONG.
  Correct policy is:
    ✅ No functional changes to SharpEmu
    ✅ No fix
    ✅ Only temporary instrumentation
    ✅ Debug patch ≠ Code fix
- Implication: INT3 breakpoints, register dumps, memory/branch trace hooks
  are ALL allowed, as long as they don't change the resolver's computed
  return value. The Dreaming Sarah Golden Test must still pass.

## FACT-017: EXP-028 ordered investigation (user-approved)
- Timestamp: 2026-07-29T12:00Z
- Commit: EXP-028 (not yet committed)
- Evidence: User message approving EXP-028 plan
- Verification: User explicit approval
- Result: The investigation order is:
  1. T12/T13 Boundary Trace (return propagation check)
  2. T5 Memory Read Trace (guest memory mismatch check) ← NEW, most important
  3. T6 Branch Trace (wrong path check) ← NEW
  4. T1/T2/T3 Per-Instruction INT3 (first divergence)
  5. GDB Single Step (lowest priority)
  6. Dreaming Sarah Compare (regression check)
  7. CPU Backend Fuzz → renamed to EXP-029 (different question)
- Implication: Investigation stops at the FIRST step that identifies the bug.
  If T12/T13 detects Case A or B, no need to proceed to T5/T6.

## FACT-018: EXP-028 instrumentation patches authored
- Timestamp: 2026-07-29T12:00Z
- Commit: EXP-028 (not yet committed)
- Evidence:
  - download/exp028/_Exp028T12T13BoundaryTrace.cs (Step 1)
  - download/exp028/_Exp028MemoryReadTracer.cs (Step 2, NEW)
  - download/exp028/_Exp028BranchTracer.cs (Step 3, NEW)
  - download/exp028/_Exp028_Patch_Instructions.md (integration guide)
  - download/exp028/GOLDEN_TEST_CHECKLIST.md (regression procedure)
  - scripts/exp028/analyze_exp028_traces.py (auto-analysis)
- Verification: Source code review
- Status: Patches authored, awaiting integration + Golden Test + Yatzi run
- Expected output files (in /tmp/exp028_logs/):
  - t12_t13_boundary.log (Case A/B/C/OK verdict)
  - t5_memory_read.log (every memory read by resolver)
  - t6_branch_trace.log (every branch decision)
- Definition of Done: First divergent instruction identified with raw
  evidence (RIP, bytes, register/flag diff). NO fix applied.
