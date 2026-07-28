# CONTRADICTIONS.md (Updated 2026-07-28)

## CONTRADICTION-001: "6 nodes" vs "239 nodes" — RESOLVED (walker bug)
## CONTRADICTION-002: "238 violations" vs "0 violations" — RESOLVED (checker bug)
- Old: STANDARD BST invariant → 238 violations
- New: INVERTED BST invariant → 0 violations
- Resolution: Tree uses inverted BST (right=less, left=greater)
## CONTRADICTION-003: "HLE strcmp fails" vs "strcmp not using HLE" — RESOLVED
- Native intrinsic applied, HLE not called
## CONTRADICTION-004: "L1-TRACE shows RIGHT" vs "resolver goes LEFT" — RESOLVED
- L1-TRACE had wrong strcmp argument order
## CONTRADICTION-005: Everything correct but resolver returns 0 — UNRESOLVED
