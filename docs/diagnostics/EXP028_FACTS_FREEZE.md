# EXP-028 — Facts Freeze (Stage 0)

**Date:** 2026-07-29
**Status:** EXP-026 closed, EXP-027 Method A closed, EXP-027 Method B open → continued as EXP-028

## Frozen Facts (no more investigation in these areas)

### From EXP-026
1. ✅ Resolver algorithm is correct (synthetic Python CPU finds all 239/239 symbols)
2. ✅ BST is correct (239 nodes + 1 sentinel, 0 invariant violations)
3. ✅ strcmp reference is correct (strcmp(NODE,QUERY) in loop, strcmp(QUERY,CANDIDATE) in final)
4. ✅ List head struct IS the sentinel (root at [sentinel+0x08])

### From EXP-027 Method A
5. ✅ cmov logic is correct (all 16 conditions × 768 tests = 100% match Unicorn vs synthetic)
6. ✅ Host CPU == Unicorn engine == Synthetic Python CPU on test/lea/cmovns/cmovns sequence (10/10)
7. ✅ SF flag preservation across `lea` works correctly on real hardware
8. ✅ cmovns takes the correct branch based on SF in all tested cases

## Areas NO LONGER investigated

The user explicitly froze investigation into:
- ❌ `cmovns` instruction-level correctness (proven by T4 + T16)
- ❌ `test eax, eax` flag computation (proven by T4)
- ❌ `lea rcx, [rbx+0x10]` flag preservation (proven by T4 — real hardware confirms lea does NOT modify flags)
- ❌ BST algorithm (proven by EXP-026 synthetic + reference)
- ❌ strcmp semantics (proven by EXP-026)

## Areas STILL OPEN (EXP-028 scope)

Based on the user's priority assessment, the remaining hypotheses (in order):

1. ⭐⭐⭐⭐⭐ **Memory mapping / guest read** — does the resolver actually read the same bytes from `[rbx+0x19]`, `[rbx+0x20]`, `[rbx+0x10]`, `[rbx+0x00]`, `[rbx+0x28]` that the synthetic CPU read?
2. ⭐⭐⭐⭐ **TryCallGuestFunction register setup** — are RDI, RSP, RFLAGS correct at resolver entry?
3. ⭐⭐⭐ **Return propagation** — does the resolver's RAX correctly flow back to the caller?
4. ⭐ (almost rejected) **CPU instruction bug** — only if all above are confirmed correct

## Instrumentation Policy (CORRECTED per user)

The user explicitly corrected the previous policy:

| Old (wrong) | New (correct) |
|---|---|
| "No changes to SharpEmu" | "No **functional** changes to SharpEmu" |
| — | "No fix" |
| — | "Only temporary instrumentation" |

**Definition:** `Debug patch ≠ Code fix`

Allowed:
- Adding logging to existing functions
- Adding breakpoint handlers (INT3) that log state and resume
- Adding memory read trace hooks
- Adding branch decision trace hooks
- All of the above must NOT change the resolver's computed return value

NOT allowed:
- Modifying the resolver's algorithm
- Modifying flag computation
- Modifying memory access patterns
- Modifying return value propagation
- Any "fix" that changes observed behavior

## EXP-028 Test Order (USER APPROVED)

```
1) T12/T13 Boundary Trace        🔴  (return propagation check)
        ↓
2) Memory Read Trace             🔴  (guest memory mismatch check)  ← NEW
        ↓
3) Branch Trace                  🟠  (wrong path check)             ← NEW
        ↓
4) Per Instruction INT3          🟠  (first divergence)
        ↓
5) GDB Single Step               🟡  (lowest priority — SharpEmu is itself an emulator)
        ↓
6) Dreaming Sarah Compare        🟡  (regression / scope check)
        ↓
7) CPU Backend Fuzz              🟢  → renamed to EXP-029 (different question)
```

## EXP-028 Definition of Done

The first divergence between native SharpEmu execution and synthetic CPU is
identified with RAW EVIDENCE:
- RIP of divergent instruction
- Instruction bytes at that RIP
- Native register state (RAX/RBX/RCX/RDI/RSI/R12/R14/R15)
- Native RFLAGS (CF/PF/ZF/SF/OF bits)
- Synthetic register state (same set)
- Synthetic RFLAGS
- Diff showing which field diverged

Plus the Dreaming Sarah Golden Test still PASSES (proving the instrumentation
is diagnostic-only, no behavior change).
