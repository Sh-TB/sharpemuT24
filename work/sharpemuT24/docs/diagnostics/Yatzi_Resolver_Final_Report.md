# Yatzi IL2CPP Resolver — Final Report (Updated)

## Current Stage
Stage 2 — IL2CPP symbol resolver debugging

## Confirmed Facts (Updated)

1. ✅ register_symbols executes and creates 239 BST nodes
2. ✅ BST has 239 real nodes + 1 sentinel (verified by independent walker)
3. ✅ All 239 IL2CPP symbols present in tree
4. ✅ No cycles in BST
5. ✅ strcmp native intrinsic is correct AND IS being used (not HLE)
6. ✅ HLE strcmp is NOT called (0 STRCMP-TRACE lines)
7. ✅ SetupImportStubs processes ALL 3652 imports (eboot + all PRXs)
8. ✅ Native intrinsics applied silently (no log for intrinsic patching)
9. ✅ Resolver logic is correct (BST traversal with cmovns)
10. ❌ BST has 238/239 sorting violations
11. ❌ Resolver returns 0 for all 232 queries
12. ❌ GOT stays empty

## Rejected Hypotheses (Updated)

1. ❌ "Only 6 nodes" — WRONG (faulty walker)
2. ❌ "HLE stub is the problem" — FIXED (stub removed)
3. ❌ "Pointer mismatch" — WRONG (same global)
4. ❌ "strcmp intrinsic is buggy" — WRONG (disassembly correct)
5. ❌ "HLE strcmp fails for PRX data" — WRONG (HLE strcmp NOT called at all)
6. ❌ "TryRead fails for PRX addresses" — WRONG (native intrinsic used, not HLE)
7. ❌ "Calling convention issue" — WRONG
8. ❌ "Race condition" — WRONG
9. ❌ "Memory context separation" — WRONG

## Root Cause (Updated)

The BST insertion helper function (0x804EDACD0) produces an invalid tree structure.
strcmp IS working correctly (native intrinsic applied by SetupImportStubs).
The tree has all 239 nodes but 238 sorting violations.

The helper function 0x804EDACD0 is NOT a simple BST insert — it appears to be
a treap or splay tree implementation that restructures the tree. The restructuring
logic is NOT working correctly in SharpEmu.

Possible causes:
- Memory layout differences between SharpEmu and real PS5
- Missing CPU features or instruction emulation issues
- Execution context differences (stack alignment, register state)
- The helper function relies on behavior that SharpEmu doesn't replicate

## Next Debug Target

Trace the actual execution of helper function 0x804EDACD0 to find where
the tree goes wrong. Compare tree state before and after each insert call.
