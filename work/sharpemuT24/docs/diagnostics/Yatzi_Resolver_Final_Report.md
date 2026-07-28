# Yatzi IL2CPP Resolver — Final Report (Updated 2026-07-28)

## Current Stage: Stage 2 — Symbol Resolution

## Confirmed Facts
1. ✅ register_symbols creates 239 BST nodes (Red-Black Tree)
2. ✅ All 239 IL2CPP symbols present in tree
3. ✅ Tree has 0 violations with correct INVERTED BST invariant
4. ✅ strcmp uses native intrinsic (NOT HLE)
5. ✅ Node struct: [0x00]=right, [0x08]=parent, [0x10]=left, [0x18]=color, [0x19]=matched
6. ✅ Algorithm: Red-Black Tree with color flips and rotations
7. ✅ Resolver logic correct (simulation finds all 5 test symbols)
8. ❌ Resolver returns 0 for all 232 queries (UNRESOLVED)
9. ❌ GOT stays empty
10. ❌ Direct-bridged resolver also returns 0

## Rejected Hypotheses (10 total)
1. ❌ HLE stub blocking register_symbols — FIXED
2. ❌ Only 6 nodes — walker bug (missed left subtree)
3. ❌ 238 BST violations — checker bug (wrong invariant)
4. ❌ HLE strcmp fails for PRX data — strcmp not using HLE
5. ❌ Pointer mismatch — same global
6. ❌ strcmp intrinsic buggy — disassembly correct
7. ❌ Calling convention wrong — standard
8. ❌ Race condition — sequential
9. ❌ Memory context separation — same space
10. ❌ L1-TRACE direction correct — wrong strcmp arg order

## Root Cause: UNKNOWN
All individual components work correctly:
- Tree: correct (0 violations)
- strcmp: correct (native intrinsic)
- Resolver logic: correct (simulation works)
- Direct bridge: correct (resolver runs natively)

But the resolver returns 0 when executed in SharpEmu.
The combined execution of resolver + strcmp + tree traversal fails
even though each component works individually.

## Next Debug Target
Need to trace the ACTUAL execution of the resolver inside SharpEmu
to find where the mismatch occurs between simulation and reality.
Possible approaches:
1. Single-step the resolver for one query
2. Add memory watchpoint on the resolver's return value
3. Check if the native intrinsic at the stub address is actually executable
4. Check if TryCallGuestFunction affects the execution context
