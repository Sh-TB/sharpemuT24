# Yatzi IL2CPP Resolver — Final Report

## Current Stage
Stage 2 — IL2CPP symbol resolver debugging

## Confirmed Facts

1. ✅ register_symbols (0x804ED3AE0) executes and creates 239 BST nodes
2. ✅ BST has 239 real nodes + 1 sentinel (verified by independent walker)
3. ✅ All 239 IL2CPP symbols are present in the tree (il2cpp_init, il2cpp_shutdown, etc.)
4. ✅ No cycles in the BST (0 cycle hits)
5. ✅ strcmp native intrinsic is correct (verified by disassembly)
6. ✅ Resolver logic is correct (BST traversal with cmovns direction)
7. ✅ Offsets match between insert and resolver ([0x00]=right, [0x10]=left, [0x20]=name, [0x28]=func)
8. ✅ All 239 inserts complete before first resolver call (same thread, sequential)
9. ✅ Same memory space (register_symbols and resolver share address space)
10. ✅ rdi at resolver entry is valid (verified: 'il2cpp_init' string)
11. ❌ BST has 238/239 sorting violations (tree is NOT sorted)
12. ❌ Resolver returns 0 for all 232 queries
13. ❌ GOT stays empty (0/125 globals populated)

## Rejected Hypotheses

1. ❌ "Only 6 nodes created" — WRONG (faulty walker only followed RIGHT children)
2. ❌ "HLE stub is the problem" — FIXED (stub removed, register_symbols runs)
3. ❌ "Pointer mismatch" — WRONG (same global 0x808B53708)
4. ❌ "strcmp intrinsic is buggy" — WRONG (disassembly is correct)
5. ❌ "Calling convention issue" — WRONG (standard rdi in, rax out)
6. ❌ "Race condition" — WRONG (sequential, same thread)
7. ❌ "Memory context separation" — WRONG (same address space)

## Root Cause

**The PRX's strcmp goes through HLE dispatch instead of native intrinsic.**

### Chain of Events:

```
PRX's strcmp PLT (0x804FC2D40)
  → jmp [GOT slot at 0x808924090]
  → HLE trampoline (NOT native intrinsic)
  → Strcmp() in KernelMemoryCompatExports.cs
  → TryCompareStrings() reads bytes via ctx.TryRead
  → ctx.TryRead FAILS for PRX data section addresses (0x808xxxxxx)
  → TryCompareStrings returns false
  → Strcmp returns MEMORY_FAULT (negative)
  → BST insertion sees negative → always goes LEFT
  → BST is unsorted (238/239 violations)
  → Resolver can't find symbols → returns 0
  → GOT stays empty
  → NULL function pointers → crashes
```

### Why eboot's strcmp works but PRX's doesn't:

- **eboot**: SetupImportStubs applies native intrinsic → strcmp runs as native x86 code → reads memory directly → works
- **PRX**: SelfLoader.ResolveAndPatchImportStubs creates HLE trampoline → strcmp goes through C# dispatch → TryCompareStrings uses ctx.TryRead → fails for PRX data

### Evidence:

- BST sorting violations: 238/239 (verified by independent Python parser)
- HLE strcmp at KernelMemoryCompatExports.cs:493 returns MEMORY_FAULT when TryCompareStrings fails
- MEMORY_FAULT is negative → BST insertion always goes LEFT (cmovns not taken)
- Native intrinsic at DirectExecutionBackend.cs:1326 is correct but NOT applied to PRX

## Fix (Not Yet Applied)

**Option A (Recommended): Apply native intrinsic for PRX's strcmp**

In SelfLoader.ResolveAndPatchImportStubs (or wherever PRX imports are patched),
check if the NID has a native intrinsic (via TryCreateNativeImportIntrinsic)
and apply it instead of creating an HLE trampoline.

This would make the PRX's strcmp use the same fast native code as eboot's.

**Option B: Fix TryCompareStrings to handle PRX data**

Ensure ctx.TryRead can read from PRX mapped memory addresses.

## Regression Tests

After fix:
1. BST should have 0 sorting violations
2. Resolver should return non-zero for all 232 queries
3. GOT should be populated (125+ globals non-zero)
4. NULL execute faults should drop to 0
5. Game should progress past IL2CPP initialization

## Next Stage

Stage 3 — IL2CPP runtime initialization (after GOT is populated)
