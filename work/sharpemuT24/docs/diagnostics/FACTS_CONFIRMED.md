# FACTS_CONFIRMED.md (Updated 2026-07-28)

## FACT-001: register_symbols creates 239 BST nodes ✅
## FACT-002: All 239 symbols present in tree ✅  
## FACT-003: Tree is INVERTED Red-Black Tree — 0 violations with correct invariant ✅ CORRECTED
- Previous "238 violations" used STANDARD BST invariant → WRONG
- With INVERTED BST invariant (right<parent, left>=parent): 0 violations
- Verified by: Independent Python parser + C# IndependentBSTWalker
## FACT-004: strcmp uses native intrinsic (NOT HLE) ✅ CORRECTED
- HLE strcmp NOT called (0 STRCMP-TRACE lines)
- Native intrinsic IS applied (INTRINSIC-CHECK: stub 0x6FFFFD0005C0 → intrinsic)
## FACT-005: Node struct has PARENT pointer at [0x08] ✅ NEW
- [0x00]=right, [0x08]=parent, [0x10]=left, [0x18]=color(0=RED,1=BLACK), [0x19]=matched
## FACT-006: Resolver returns 0 for all 232 queries ❌ UNRESOLVED
## FACT-007: Resolver logic correct (simulation finds all 5 symbols) ✅
## FACT-008: HLE stub removal for cJ2Y4E-t258 correct ✅
## FACT-009: Direct-bridged resolver also returns 0 ❌ UNRESOLVED
## FACT-010: No faults during wrapper execution ✅
