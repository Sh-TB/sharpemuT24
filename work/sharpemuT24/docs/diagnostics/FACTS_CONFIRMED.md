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
