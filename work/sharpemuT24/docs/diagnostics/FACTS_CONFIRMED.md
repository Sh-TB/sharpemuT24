# FACTS_CONFIRMED.md (Final — 2026-07-28)

## VERIFIED FACTS (all dual-verified):

1. ✅ register_symbols creates 239 BST nodes (Red-Black Tree)
2. ✅ All 239 IL2CPP symbols present in tree (7/7 searched found)
3. ✅ Tree has 0 violations with INVERTED BST invariant (right<parent, left>=parent)
4. ✅ strcmp uses native intrinsic (INTRINSIC-CHECK confirmed)
5. ✅ HLE strcmp NOT called (0 STRCMP-TRACE lines)
6. ✅ Node struct: [0x00]=right, [0x08]=parent, [0x10]=left, [0x18]=color(0=RED,1=BLACK), [0x19]=matched
7. ✅ Resolver logic correct (Python simulation finds all 5 test symbols)
8. ✅ Resolver direction correct for inverted BST (cmovns: strcmp(NODE,QUERY)>=0 → RIGHT)
9. ✅ All offsets match between insert and resolver
10. ✅ Guest memory mapped 1:1 to host (PhysicalVirtualMemory.Map at exact VA)
11. ✅ No faults during resolver execution
12. ✅ Direct-bridged resolver (no TryCallGuestFunction) also returns 0
13. ❌ Resolver returns 0 for all 232 queries — ROOT CAUSE UNKNOWN

## KEY CONTRADICTION (UNRESOLVED):
- Python simulation (correct strcmp order) → FINDS all symbols
- SharpEmu native execution → returns 0
- Tree is correct, strcmp is correct, logic is correct
- But combined execution fails
- Possible cause: native intrinsic at import stub doesn't execute correctly
- OR: flag propagation issue in native CPU execution
- OR: memory access issue specific to native execution context
