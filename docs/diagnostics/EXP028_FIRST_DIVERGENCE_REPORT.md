# EXP-028 — First Divergence Report

**Status:** AWAITING NATIVE TRACE DATA

This report will be auto-populated by `analyze_exp028_traces.py` once the
EXP-028 instrumentation patches are installed and the game is run with
tracing enabled.

---

## Investigation Order (per user-approved plan)

```
Step 1: T12/T13 Boundary Trace        🔴  (return propagation check)
Step 2: T5 Memory Read Trace          🔴  (guest memory mismatch check) ← MOST IMPORTANT
Step 3: T6 Branch Trace               🟠  (wrong path check)
Step 4: T1/T2/T3 Per-Instruction INT3 🟠  (first divergence)
Step 5: GDB Single Step               🟡  (lowest priority)
Step 6: Dreaming Sarah Compare        🟡  (regression check)
Step 7: EXP-029 CPU Backend Fuzz      🟢  (separate experiment)
```

Investigation STOPS at the FIRST step that identifies the bug.

---

## Step 1 Result: T12/T13 Boundary Trace

**Status:** PENDING — apply `_Exp028T12T13BoundaryTrace.cs` and run Yatzi.

### Three Possible Cases

**Case A: Bad input (TryCallGuestFunction register setup bug)**
- Symptom: RDI=0 or RSP=0 at resolver entry
- Root cause: `DirectExecutionBackend.cs::TryCallGuestFunction` does not
  correctly initialize RDI/RSP before jumping to the guest entry point
- Action: STOP — bug is in setup, not in resolver
- Fix location: `DirectExecutionBackend.cs:3459-3477` (context initialization)

**Case B: Return corruption (return propagation bug)**
- Symptom: `returnValue` (from TryCallGuestFunction) is non-zero, but
  `cpuContext.Rax` after the call is 0 (or different)
- Root cause: TryCallGuestFunction does not correctly extract RAX from
  the guest context after execution
- Action: STOP — bug is in return propagation, not in resolver
- Fix location: examine how TryCallGuestFunction reads back RAX

**Case C: Genuine zero (bug inside resolver)**
- Symptom: `returnValue` is 0, `cpuContext.Rax` is 0 — no corruption
- Root cause: The resolver's native execution genuinely computes 0
- Action: PROCEED to Step 2 (T5 Memory Read Trace)

**Case OK: Resolver works**
- Symptom: `returnValue` is non-zero, `cpuContext.Rax` matches
- Root cause: Resolver is fine — bug is elsewhere (Stage 7+)
- Action: STOP — bug is post-resolver

### How to Determine the Case

After running Yatzi with the T12/T13 patch, examine
`/tmp/exp028_logs/t12_t13_boundary.log`:

```bash
grep "EXP028-T13-CASE" /tmp/exp028_logs/t12_t13_boundary.log | sort | uniq -c
```

The output will show counts for each case. The dominant case is the verdict.

---

## Step 2 Result: T5 Memory Read Trace

**Status:** PENDING — apply `_Exp028MemoryReadTracer.cs` and run Yatzi.

Only runs if Step 1 returns Case C.

### What It Traces

For each memory read in the resolver, logs:
- RIP (which instruction)
- Source address (rbx+offset or r12+offset)
- Value read by native code
- Comparison with synthetic CPU's expected value (from BST-WALK log)

### Critical Reads to Verify

| RIP | Instruction | Source | Synthetic Expected | Native Actual | Match? |
|-----|-------------|--------|-------------------|---------------|--------|
| 0x804ED9B9B | mov r15, [rip+0x3c79b66] | list_head_ptr @ 0x808B53708 | 0x2000003f20 | ? | ? |
| 0x804ED9BA2 | mov rbx, [r15+8] | sentinel+8 (root ptr) | 0x2000027440 | ? | ? |
| 0x804ED9BA6 | cmp byte [rbx+0x19], 0 | root matched flag | 0 (real) | ? | ? |
| 0x804ED9BC0 | mov rdi, [rbx+0x20] | root symbol name ptr | 0x40000000 | ? | ? |
| 0x804ED9BDA | mov rbx, [rcx] | next node (left/right) | varies | ? | ? |
| 0x804ED9BDD | cmp byte [rbx+0x19], 0 | next matched flag | varies | ? | ? |
| 0x804ED9BE8 | mov rsi, [r12+0x20] | candidate name ptr | varies | ? | ? |
| 0x804ED9BF9 | mov rax, [r12+0x28] | func impl ptr | 0x804ed8770 | ? | ? |

### Decision Tree

- If ANY native value differs from synthetic → **BUG: Memory mapping or guest read**
  - Investigate: `VirtualMemory`, `TryReadByte`, `TryReadUInt64` paths
  - Check: page protection, address translation, memory aliasing
- If ALL native values match synthetic → PROCEED to Step 3 (T6 Branch Trace)

---

## Step 3 Result: T6 Branch Trace

**Status:** PENDING — apply `_Exp028BranchTracer.cs` and run Yatzi.

Only runs if Step 2 shows all memory reads match.

### What It Traces

For each branch instruction in the resolver, logs:
- RIP (which branch)
- RFLAGS (CF, PF, ZF, SF, OF)
- Branch decision: TAKEN or NOT_TAKEN
- Comparison with synthetic CPU's expected decision

### Critical Branches to Verify

| RIP | Instruction | Condition | Synthetic Decision | Native Decision | Match? |
|-----|-------------|-----------|-------------------|-----------------|--------|
| 0x804ED9BAA | je do_lookup | ZF=1 | TAKEN (root is real) | ? | ? |
| 0x804ED9BD2 | cmovns rcx, rbx | SF=0 | varies per strcmp | ? | ? |
| 0x804ED9BD6 | cmovns r12, rbx | SF=0 | varies per strcmp | ? | ? |
| 0x804ED9BE1 | je loop_start | ZF=1 | TAKEN (not sentinel) | ? | ? |
| 0x804ED9BE6 | je return_0 | ZF=1 | NOT_TAKEN (has candidate) | ? | ? |
| 0x804ED9BF7 | js return_0 | SF=1 | NOT_TAKEN (QUERY>=CANDIDATE) | ? | ? |

### Decision Tree

- If ANY native branch decision differs from synthetic → **BUG: Flag computation or preservation**
  - Investigate: how `test eax, eax` sets SF/ZF in native execution
  - Investigate: whether `lea rcx, [rbx+0x10]` clobbers SF (it shouldn't per Intel SDM)
  - Investigate: whether `cmovns` reads the correct SF
- If ALL native branch decisions match synthetic → PROCEED to Step 4

---

## Step 4 Result: T1/T2/T3 Per-Instruction INT3

**Status:** PENDING — apply `_Exp027ResolverTracer.cs` (from EXP-027) and run Yatzi.

Only runs if Step 3 shows all branch decisions match.

### What It Traces

31 breakpoints at EVERY instruction in the resolver. For each instruction:
- RIP
- Instruction bytes
- All GP registers (RAX, RBX, RCX, RDX, RSI, RDI, R12-R15, RBP, RSP)
- RFLAGS (CF, PF, AF, ZF, SF, OF, DF, TF, IF)

### Comparison with Synthetic

The synthetic CPU's trace is at:
`/home/z/my-project/download/exp026/exp026_il2cpp_init_trace.log`

Compare line by line. The FIRST step where native differs from synthetic
is the bug.

### Output

The analyzer script (`analyze_exp028_traces.py`) will auto-populate this
section with:
- First divergent RIP
- Instruction at that RIP
- Native register state
- Synthetic register state
- Diff showing which field diverged

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
4. ✅ This report auto-populated by `analyze_exp028_traces.py`
5. ✅ NO fix applied (per user policy — fix proposal is separate)

---

## How to Run the Analysis

After collecting logs from Yatzi:

```bash
python3 /home/z/my-project/scripts/exp028/analyze_exp028_traces.py
```

The script will:
1. Parse `/tmp/exp028_logs/t12_t13_boundary.log` → determine Case A/B/C/OK
2. If Case C, parse `t5_memory_read.log` → compare with synthetic
3. If no memory divergence, parse `t6_branch_trace.log` → compare with synthetic
4. If no branch divergence, parse `test4_full_trace.log` → find first divergence
5. Auto-populate this report
6. Write machine-readable summary to `exp028_summary.json`

---

## References

- EXP-026 divergence report: `/home/z/my-project/download/exp026/EXP026_DIVERGENCE_REPORT.md`
- EXP-027 first divergence report: `/home/z/my-project/download/exp027/EXP027_FIRST_DIVERGENCE_REPORT.md`
- EXP-028 facts freeze: `/home/z/my-project/download/exp028/EXP028_FACTS_FREEZE.md`
- EXP-028 execution plan: `/home/z/my-project/download/exp028/EXP028_EXECUTION_PLAN.md`
- Synthetic CPU trace: `/home/z/my-project/download/exp026/exp026_il2cpp_init_trace.log`
- BST tree JSON: `/home/z/my-project/scripts/exp026_tree.json`
- Patch instructions: `/home/z/my-project/download/exp028/_Exp028_Patch_Instructions.md`
- Golden Test checklist: `/home/z/my-project/download/exp028/GOLDEN_TEST_CHECKLIST.md`
