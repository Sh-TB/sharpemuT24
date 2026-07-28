# EXP-028 — Execution Plan

**Date:** 2026-07-29
**Status:** Active (EXP-026 closed, EXP-027 Method A closed, Method B continued as EXP-028)
**Approved by:** User (evidence-first approach per qwwwwwwwwwww)

---

## Goal

Identify the EXACT CPU-emulation divergence in SharpEmu's native execution
of the IL2CPP resolver at `0x804ED9B90`. The user has frozen investigation
into cmovns/test/lea (proven correct by EXP-027 T4 + T16). The remaining
hypotheses, in priority order:

1. ⭐⭐⭐⭐⭐ **Memory mapping / guest read** — does the resolver read the same bytes from the BST that the synthetic CPU read?
2. ⭐⭐⭐⭐ **TryCallGuestFunction register setup** — are RDI, RSP, RFLAGS correct at resolver entry?
3. ⭐⭐⭐ **Return propagation** — does the resolver's RAX correctly flow back to the caller?
4. ⭐ (almost rejected) **CPU instruction bug** — only if all above are confirmed correct

---

## Frozen Facts (NO more investigation)

From EXP-026:
- ✅ Resolver algorithm correct (synthetic finds 239/239 symbols)
- ✅ BST correct (239 nodes + 1 sentinel, 0 invariant violations)
- ✅ strcmp reference correct
- ✅ List head struct IS the sentinel (root at [sentinel+0x08])

From EXP-027 Method A:
- ✅ cmov logic correct (T4: 10/10, T16: 768/768)
- ✅ Host CPU == Unicorn == Synthetic on cmovns sequence
- ✅ SF flag preservation across `lea` works on real hardware

---

## Instrumentation Policy (USER CORRECTED)

```
✅ No functional changes to SharpEmu
✅ No fix
✅ Only temporary instrumentation
✅ Debug patch ≠ Code fix
```

Allowed: logging, breakpoint handlers, memory/branch trace hooks.
NOT allowed: any change that modifies the resolver's computed return value.

---

## Execution Order (USER APPROVED)

```
Step 1: T12/T13 Boundary Trace        🔴  (return propagation check)
    │
    ├─ Case A (bad input)? → BUG: TryCallGuestFunction register setup
    ├─ Case B (return corruption)? → BUG: Return value propagation
    ├─ Case C (genuine zero)? → continue to Step 2
    └─ Case OK (resolver works)? → bug is elsewhere (Stage 7+)
    │
    ↓
Step 2: T5 Memory Read Trace          🔴  (guest memory mismatch check) ← NEW
    │
    ├─ Native reads differ from synthetic? → BUG: Memory mapping or guest read
    └─ Native reads match synthetic? → continue to Step 3
    │
    ↓
Step 3: T6 Branch Trace               🟠  (wrong path check) ← NEW
    │
    ├─ Native branch decisions differ? → BUG: Flag computation or preservation
    └─ Native branch decisions match? → continue to Step 4
    │
    ↓
Step 4: T1/T2/T3 Per-Instruction INT3 🟠  (first divergence)
    │
    └─ Pinpoint exact divergent instruction
    │
    ↓
Step 5: GDB Single Step               🟡  (lowest priority)
    │
    └─ SharpEmu is itself an emulator; GDB may not show full guest CPU state
    │
    ↓
Step 6: Dreaming Sarah Compare        🟡  (regression / scope check)
    │
    └─ If Dreaming Sarah uses cmovns and works → bug is resolver-specific
    │
    ↓
Step 7: EXP-029 CPU Backend Fuzz      🟢  (separate experiment)
    │
    └─ Different question: is cmovns correct INSIDE SharpEmu's CPU backend?
```

---

## Files Produced

### C# Instrumentation Patches (for SharpEmu integration)

| File | Step | Purpose |
|------|------|---------|
| `_Exp028T12T13BoundaryTrace.cs` | 1 | Pre/post call register dump + return corruption check |
| `_Exp028MemoryReadTracer.cs` | 2 | INT3 breakpoints at memory-read instructions (8 reads) |
| `_Exp028BranchTracer.cs` | 3 | INT3 breakpoints at branch instructions (6 branches) |
| `_Exp027ResolverTracer.cs` (from EXP-027) | 4 | INT3 breakpoints at ALL 31 instructions |
| `_Exp028_Patch_Instructions.md` | 1-4 | Integration guide with exact diffs |
| `GOLDEN_TEST_CHECKLIST.md` | 1-4 | Dreaming Sarah regression test procedure |

### Analysis Scripts

| File | Purpose |
|------|---------|
| `scripts/exp028/analyze_exp028_traces.py` | Parses all EXP-028 logs, compares with synthetic, generates divergence report |

### Reports

| File | Purpose |
|------|---------|
| `EXP028_FACTS_FREEZE.md` | Frozen facts + scope + instrumentation policy |
| `EXP028_EXECUTION_PLAN.md` | This file — ordered steps + expected outcomes |
| `EXP028_FIRST_DIVERGENCE_REPORT.md` | Auto-populated after native trace collected |

---

## Expected Output per Step

### After Step 1 (T12/T13):

**Logs:** `/tmp/exp028_logs/t12_t13_boundary.log`

```
[EXP028-T12-PRE]  call=1 query='il2cpp_init' entry=0x804ed9b90 symAddr=0x...
  RAX=0x... RBX=0x... RCX=0x... RDX=0x...
  RSI=0x... RDI=0x... R8=0x... R9=0x...
  R12=0x... R13=0x... R14=0x... R15=0x...
  RBP=0x... RSP=0x...
  RFLAGS=0x... (CF=0 PF=0 AF=0 ZF=0 SF=0 OF=0 TF=0 IF=1)
[EXP028-T12-POST] call=1 query='il2cpp_init'
  returnValue=0x0 error=''
  cpuContext.Rax=0x0 ...
[EXP028-T13-CASE-C] Resolver genuinely returned 0 (no corruption detected)
  → Bug is INSIDE the resolver's native execution
  → Continue with T5 (Memory Read Trace)...
```

**Verdict:**
- If Case A: bug is in TryCallGuestFunction setup → STOP, investigate setup
- If Case B: bug is in return propagation → STOP, investigate propagation
- If Case C: continue to Step 2
- If Case OK: resolver works → bug is elsewhere

### After Step 2 (T5):

**Logs:** `/tmp/exp028_logs/t5_memory_read.log`

```
[EXP028-T5] call=1 step=1 rip=0x804ed9b9b mov r15, [rip+0x3c79b66]
  list_head_ptr=0x808b53708 src_addr=0x808b53708 size=8 value=0x2000003f20
[EXP028-T5] call=1 step=2 rip=0x804ed9ba2 mov rbx, [r15+8]
  r15=0x2000003f20 src_addr=0x2000003f20+8 size=8 value=0x2000027440
[EXP028-T5] call=1 step=3 rip=0x804ed9ba6 cmp byte [rbx+0x19], 0
  rbx=0x2000027440 src_addr=0x2000027459 size=1 value=0x0 (real node)
[EXP028-T5] call=1 step=4 rip=0x804ed9bc0 mov rdi, [rbx+0x20]
  rbx=0x2000027440 src_addr=0x2000027460 size=8 value=0x... name='il2cpp_class_num_fields'
...
```

**Comparison with synthetic:**

| Step | Native value | Synthetic value | Match? |
|------|--------------|-----------------|--------|
| 1 (list head struct ptr) | 0x2000003f20 | 0x2000003f20 | ✅ |
| 2 (root node ptr) | 0x2000027440 | 0x2000027440 | ✅ |
| 3 (root matched flag) | 0 (real) | 0 (real) | ✅ |
| 4 (root symbol name) | 'il2cpp_class_num_fields' | 'il2cpp_class_num_fields' | ✅ |
| ... | ... | ... | ... |

**Verdict:**
- If any value differs → bug is in memory mapping → STOP, investigate VirtualMemory
- If all values match → continue to Step 3

### After Step 3 (T6):

**Logs:** `/tmp/exp028_logs/t6_branch_trace.log`

```
[EXP028-T6] call=1 step=1 rip=0x804ed9baa instr='je 0x804ed9bb7' sentinel? skip lookup
  RFLAGS=0x... (CF=0 PF=1 AF=0 ZF=1 SF=0 OF=0)
  Branch: TAKEN
[EXP028-T6] call=1 step=2 rip=0x804ed9bd2 instr='cmovns rcx, rbx' if SF=0: rcx=rbx (go RIGHT)
  RFLAGS=0x... (CF=0 PF=1 AF=0 ZF=0 SF=0 OF=0)
  Branch: TAKEN
...
```

**Comparison with synthetic:**

| Step | RIP | Native SF | Native decision | Synthetic SF | Synthetic decision | Match? |
|------|-----|-----------|-----------------|--------------|--------------------|--------|
| 1 | 0x804ed9baa (je) | ZF=? | TAKEN/NOT | ZF=? | TAKEN/NOT | ? |
| 2 | 0x804ed9bd2 (cmovns) | SF=? | TAKEN/NOT | SF=? | TAKEN/NOT | ? |
| ... | ... | ... | ... | ... | ... | ... |

**Verdict:**
- If any branch decision differs → bug is in flag computation → STOP, investigate flag preservation
- If all decisions match → continue to Step 4

### After Step 4 (T1/T2/T3):

**Logs:** `/tmp/exp028_logs/test4_full_trace.log`, `test1_rflags.log`, `test2_registers.log`, `test3_strcmp.log`

Full per-instruction trace. Compare with synthetic trace at
`/home/z/my-project/download/exp026/exp026_il2cpp_init_trace.log`
line by line. The FIRST step where native differs from synthetic is the bug.

---

## Definition of Done

EXP-028 is complete when:

1. ✅ All steps executed in order (or stopped early due to Case A/B/OK)
2. ✅ Golden Test (Dreaming Sarah) passes after every patch
3. ✅ First divergent instruction identified with RAW EVIDENCE:
   - RIP
   - Instruction bytes
   - Native register state (RAX/RBX/RCX/RDI/RSI/R12/R14/R15)
   - Native RFLAGS (CF/PF/ZF/SF/OF bits)
   - Synthetic register state (same set)
   - Synthetic RFLAGS
   - Diff showing which field diverged
4. ✅ `EXP028_FIRST_DIVERGENCE_REPORT.md` auto-populated by analyzer
5. ✅ No fix applied (per user policy — fix proposal is separate)

After EXP-028 is complete, the fix proposal can be drafted based on the
identified root cause.

---

## Time Estimate

| Step | Time (approx) |
|------|----------------|
| 1: Apply T12/T13 patch + Golden Test + Yatzi run | 30 min |
| 2: Apply T5 patch + Golden Test + Yatzi run | 1 hour |
| 3: Apply T6 patch + Golden Test + Yatzi run | 1 hour |
| 4: Apply T1/T2/T3 patch + Golden Test + Yatzi run | 1 hour |
| Analysis + report | 30 min |
| **Total** | **~4 hours** |

(Steps 5-7 are optional / lower priority.)

---

## Rollback Plan

If any patch causes Golden Test failure:
1. Revert the patch
2. Investigate the patch for bugs (it's debug code, fixable)
3. Re-apply fixed patch
4. Re-run Golden Test
5. Only proceed once Golden Test passes

If all patches are applied and NO divergence is found:
- The bug may be in a code path not covered by the instrumentation
- Consider expanding T1/T2/T3 to cover more instructions
- Or fall back to GDB single-step (Step 5)
