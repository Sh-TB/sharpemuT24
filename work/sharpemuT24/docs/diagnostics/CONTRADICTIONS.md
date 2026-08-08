# CONTRADICTIONS.md (Final — 2026-07-28)

## RESOLVED:
1. "6 nodes" vs "239 nodes" → walker bug (missed left subtree)
2. "238 violations" vs "0 violations" → checker bug (wrong BST invariant)
3. "HLE strcmp fails" vs "strcmp not using HLE" → native intrinsic used
4. "L1-TRACE shows RIGHT" vs "resolver goes LEFT" → wrong strcmp arg order

## UNRESOLVED:
5. Everything correct but resolver returns 0
   - Tree: 0 violations (verified by Python + C#)
   - strcmp: native intrinsic, correct code
   - Logic: simulation finds all symbols
   - Memory: 1:1 mapped, no faults
   - But: resolver returns 0 in all execution modes (HLE + direct-bridge)
   - Cause: UNKNOWN — needs single-step trace of actual native execution
