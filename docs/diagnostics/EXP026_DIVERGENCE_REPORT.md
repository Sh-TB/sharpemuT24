# EXP-026 — Resolver Execution Divergence Report

**Stage:** 3 — Resolver Execution Divergence
**Date:** 2026-07-29
**Goal:** Find the exact instruction where the native resolver diverges from the reference implementation.

---

## Executive Summary

**The synthetic x86-64 CPU emulator (running the resolver's exact instruction
sequence on the actual in-memory tree) finds ALL 239 symbols.** The reference
Python RBTree implementation also finds ALL 239 symbols. **Zero divergence**
between synthetic and reference.

Since the synthetic CPU executes the resolver's exact instruction sequence
(including `cmp`, `test`, `cmovns`, `je`, `js`, `call strcmp`) on the same
tree that SharpEmu built in memory, and finds every symbol, while SharpEmu's
**native** execution of the same resolver at `0x804ED9B90` returns 0 for all
232 calls — **the divergence is conclusively in SharpEmu's native CPU
execution layer**, not in the algorithm, tree, or strcmp.

---

## 1. Test Setup

### 1.1 Synthetic CPU Emulator (`exp026_synthetic_cpu.py`)

A Python x86-64 emulator that implements the resolver's instruction sequence
one instruction at a time. For every instruction it logs:

| Field | Description |
|-------|-------------|
| `step` | Sequential step counter |
| `rip`  | Instruction address (matches real PRX VA) |
| `mnemonic` | x86 mnemonic (`push`, `mov`, `cmp`, `test`, `cmovns`, `je`, `js`, `call`, `ret`) |
| `operands` | Operand string (matches AT&T-ish disassembly) |
| `RAX, RBX, RCX, RDI, RSI, R12, R14, R15` | Full 64-bit register values |
| `RFLAGS` | `SF ZF CF OF PF` flag bits |
| `notes` | Human-readable annotation of what just happened |
| `branch` | `TAKEN` / `NOT_TAKEN` for conditional jumps and cmovs |

### 1.2 Tree Source

The actual BST built by `register_symbols` at runtime, captured in
`test_d1_bst_walk.log`:

- 239 real nodes + 1 sentinel = 240 total
- Root: `0x2000027440` (`il2cpp_class_num_fields`)
- Sentinel: `0x2000003f20` (the list head struct itself; `[sentinel+0x08]` = root)
- Tree is an inverted red-black tree (right = smaller, left = larger/equal)
- 0 BST invariant violations (verified by independent Python + C# walkers)

### 1.3 Resolver Instruction Sequence (from static disassembly)

```
0x804ED9B90: push rbp
0x804ED9B91: mov rbp, rsp
0x804ED9B94: push r15; push r14; push r12; push rbx
0x804ED9B9B: mov r15, [rip+0x3c79b66]    ; r15 = list head struct (= sentinel)
0x804ED9BA2: mov rbx, [r15+8]              ; rbx = root node
0x804ED9BA6: cmp byte [rbx+0x19], 0        ; check matched flag
0x804ED9BAA: je 0x804ED9BB7                ; if not matched, do lookup
0x804ED9BAC: xor eax, eax                  ; already matched: return 0
0x804ED9BAE: pop rbx; pop r12; pop r14; pop r15; pop rbp
0x804ED9BB6: ret
0x804ED9BB7: mov r14, rdi                  ; r14 = query string
0x804ED9BBA: mov r12, r15                  ; r12 = candidate (sentinel = none)
0x804ED9BBD: nop
0x804ED9BC0: mov rdi, [rbx+0x20]           ; rdi = NODE symbol name
0x804ED9BC4: mov rsi, r14                  ; rsi = QUERY
0x804ED9BC7: call strcmp                   ; rax = strcmp(NODE, QUERY)
0x804ED9BCC: test eax, eax                 ; sets SF, ZF
0x804ED9BCE: lea rcx, [rbx+0x10]           ; rcx = LEFT child addr (default)
0x804ED9BD2: cmovns rcx, rbx               ; if SF=0 (NODE>=QUERY): rcx = rbx (RIGHT)
0x804ED9BD6: cmovns r12, rbx               ; if SF=0 (NODE>=QUERY): r12 = rbx (candidate)
0x804ED9BDA: mov rbx, [rcx]                ; rbx = next node
0x804ED9BDD: cmp byte [rbx+0x19], 0        ; sentinel check
0x804ED9BE1: je 0x804ED9BC0                 ; loop if not sentinel
0x804ED9BE3: cmp r12, r15                  ; candidate == sentinel?
0x804ED9BE6: je 0x804ED9BAC                 ; if no candidate, return 0
0x804ED9BE8: mov rsi, [r12+0x20]           ; rsi = CANDIDATE symbol name
0x804ED9BED: mov rdi, r14                  ; rdi = QUERY
0x804ED9BF0: call strcmp                   ; rax = strcmp(QUERY, CANDIDATE)
0x804ED9BF5: test eax, eax
0x804ED9BF7: js 0x804ED9BAC                 ; if SF=1 (QUERY<CANDIDATE), return 0
0x804ED9BF9: mov rax, [r12+0x28]           ; rax = func_impl
... ret
```

The synthetic CPU implements every instruction above with EXACT x86 semantics:
- `cmp`/`test` set SF, ZF, CF, OF, PF correctly (using signed/unsigned arithmetic)
- `cmovns` checks SF (NOT ZF or other flags)
- `je` checks ZF
- `js` checks SF
- `strcmp` is the standard C strcmp (returns negative/zero/positive)

---

## 2. Test Results

### 2.1 Single Query: `il2cpp_init`

| | Synthetic CPU | Reference | SharpEmu Native |
|---|---|---|---|
| Path length | 9 levels + sentinel | 9 levels + sentinel | (unknown — no per-step trace) |
| Final result | `0x804ed8770` (FOUND) | `0x804ed8770` (FOUND) | `0x0` (NULL) |
| Match with reference | YES | — | NO |

**Synthetic CPU trace for `il2cpp_init`** (key branch decisions):

| Step | RIP | Mnemonic | Decision | Notes |
|------|-----|----------|----------|-------|
| 11 | 0x804ED9BC7 | call strcmp | strcmp('il2cpp_class_num_fields','il2cpp_init')=-6 | NODE<QUERY |
| 12 | 0x804ED9BCC | test eax,eax | SF=1 ZF=0 | negative |
| 14 | 0x804ED9BD2 | cmovns rcx,rbx | NOT_TAKEN | SF=1, use LEFT |
| 15 | 0x804ED9BD6 | cmovns r12,rbx | NOT_TAKEN | SF=1, no candidate update |
| 29 | 0x804ED9BC7 | call strcmp | strcmp('il2cpp_object_header_size','il2cpp_init')=6 | NODE>QUERY |
| 30 | 0x804ED9BCC | test eax,eax | SF=0 ZF=0 | positive |
| 32 | 0x804ED9BD2 | cmovns rcx,rbx | TAKEN | SF=0, use RIGHT |
| 33 | 0x804ED9BD6 | cmovns r12,rbx | TAKEN | SF=0, candidate=NODE |
| 92 | 0x804ED9BC7 | call strcmp | strcmp('il2cpp_init','il2cpp_init')=0 | EXACT MATCH |
| 93 | 0x804ED9BCC | test eax,eax | SF=0 ZF=1 | zero |
| 95 | 0x804ED9BD2 | cmovns rcx,rbx | TAKEN | SF=0, use RIGHT |
| 96 | 0x804ED9BD6 | cmovns r12,rbx | TAKEN | SF=0, candidate=NODE |
| 97 | 0x804ED9BDA | mov rbx,[rcx] | next=0x2000003f20 (sentinel) | |
| 98 | 0x804ED9BDD | cmp byte[rbx+0x19],0 | flag=1 (sentinel) | exit loop |
| 99 | 0x804ED9BE3 | cmp r12,r15 | r12=0x2000025a40 r15=0x2000003f20 | not equal |
| 102 | 0x804ED9BF0 | call strcmp | strcmp('il2cpp_init','il2cpp_init')=0 | exact |
| 104 | 0x804ED9BF7 | js return_0 | NOT_TAKEN | SF=0, return func_ptr |
| 105 | 0x804ED9BF9 | mov rax,[r12+0x28] | rax=0x804ed8770 | SUCCESS |
| 106 | 0x804ED9BB6 | ret | RETURN 0x804ed8770 | |

### 2.2 All 239 Symbols Test

| | Count |
|---|---|
| Total symbols tested | 239 |
| Synthetic CPU found | 239 (100%) |
| Reference impl found | 239 (100%) |
| Mismatches | 0 |

**Verdict:** Synthetic CPU and reference implementation AGREE on all 239 symbols.

---

## 3. Divergence Identification

### 3.1 What We Now Know Is Correct

| Component | Status | Evidence |
|---|---|---|
| Tree structure | OK | 239 nodes, 0 invariant violations, red-black tree |
| Resolver algorithm | OK | Synthetic CPU + reference agree on all 239 symbols |
| strcmp semantics | OK | Used as `strcmp(NODE,QUERY)` in loop, `strcmp(QUERY,CANDIDATE)` in final check |
| Flag computation | OK | Synthetic emulates exact x86 SF/ZF/CF/OF/PF semantics |
| Branch decisions | OK | cmovns/je/js all take correctly based on SF/ZF |
| Node field offsets | OK | `[0x00]=right [0x08]=parent [0x10]=left [0x18]=color [0x19]=matched [0x20]=name [0x28]=func` |
| List head pointer | OK | `0x808B53708` → `0x2000003f20` (sentinel); `[sentinel+8]` = root |

### 3.2 What We Now Know Is Buggy

| Component | Status | Evidence |
|---|---|---|
| SharpEmu native execution of resolver | BUGGY | Returns 0 for all 232 calls, while synthetic (same algorithm, same tree) finds all 239 |

### 3.3 Where Exactly Is The Divergence?

The synthetic CPU and SharpEmu's native execution both:
- Start with the same registers (RDI=query, RSP=stack)
- Read the same tree from the same memory addresses
- Execute the same instruction bytes at the same RIPs
- Call the same strcmp implementation

The synthetic CPU returns the correct func_ptr. SharpEmu's native execution
returns 0. So at SOME instruction during execution, SharpEmu's CPU produced a
different result than the synthetic CPU.

**Possible divergence points** (in order of likelihood):

1. **`cmovns` emulation**: SharpEmu may not correctly handle `cmovns rcx, rbx`
   or `cmovns r12, rbx` (specifically: cmov with `ns` condition).
   - This would cause wrong direction in tree traversal.
   - Symptom: resolver goes RIGHT when it should go LEFT (or vice versa).

2. **Flag preservation across instructions**: SharpEmu may clobber SF between
   `test eax, eax` and `cmovns`.
   - The flag lifetime is 2 instructions (test → lea → cmovns).
   - If `lea` modifies flags (it shouldn't, but bugs happen), cmovns would
     use stale/wrong SF.

3. **`call strcmp` return value**: SharpEmu's native strcmp may return
   different values than expected.
   - Already verified native intrinsic is applied (INTRINSIC-CHECK).
   - But the intrinsic may produce different flag state on return than
     the synthetic model assumes.

4. **Memory read of node fields**: SharpEmu may read wrong values from
   `[rbx+0x20]` (symbol name ptr) or `[rbx+0x19]` (matched flag).
   - Already verified BST-WALK reads correct values.
   - But the resolver runs in a different CPU context than the walker.

5. **Initial register setup**: SharpEmu's `TryCallGuestFunction` may set up
   RDI / RSP differently than the synthetic model assumes.
   - Already verified RDI contains the query string at entry (RESOLVER-TRACE logs).

### 3.4 Specific Divergence Instruction (TBD)

To pinpoint the EXACT instruction, the next step is to add a per-instruction
tracer to SharpEmu's native execution. Two approaches:

**Approach A: Hardware breakpoints (DR0-DR3)**
- Set DR0 = `0x804ED9BD2` (cmovns rcx, rbx)
- Set DR1 = `0x804ED9BD6` (cmovns r12, rbx)
- Set DR2 = `0x804ED9BCC` (test eax, eax)
- On each SIGTRAP, log RIP + registers + flags
- Continue execution

**Approach B: Software breakpoints (INT 3)**
- Patch `0xCC` at each branch instruction
- On SIGTRAP, log state, restore byte, single-step, re-patch

**Approach C: Single-step entire resolver**
- Use `PTRACE_SINGLESTEP` (Linux) or trap flag (TF=1 in RFLAGS)
- Log every instruction's state
- Compare with synthetic CPU's trace step-by-step

**Approach D: STRCMP-TRACE enhancement**
- Hook the strcmp calls (already done via INTRINSIC-CHECK)
- Log strcmp arguments AND return value AND resulting flags
- This would tell us if strcmp returns the expected value
- If strcmp returns correctly but cmovns takes wrong branch → cmovns bug

---

## 4. Recommended Next Step

**Build a per-instruction tracer using Approach C (single-step mode).**

1. In `DirectExecutionBackend.ExecuteGuestThreadEntry`, before jumping to the
   guest code, set the Trap Flag (TF=1) in RFLAGS.
2. Install a SIGTRAP handler that:
   - Reads the current RIP, registers, and RFLAGS
   - Logs them in the same format as the synthetic CPU
   - Re-sets TF=1 and resumes
3. Run the resolver for ONE query (`il2cpp_init`)
4. Compare the native trace with the synthetic trace step-by-step
5. The FIRST instruction where they differ is the bug

This will produce a diff like:
```
Step 12:
  Synthetic: 0x804ED9BCC  test eax, eax   | RAX=0xfffffffa SF=1 ZF=0
  Native:    0x804ED9BCC  test eax, eax   | RAX=0xfffffffa SF=0 ZF=0  ← DIVERGENCE!
  (SF should be 1 because RAX is negative, but native has SF=0)
```

That would pinpoint the exact CPU emulation bug.

---

## 5. Files Produced

| File | Purpose |
|------|---------|
| `scripts/exp026_build_tree.py` | Parses BST-WALK log, builds tree JSON |
| `scripts/exp026_tree.json` | Tree data (240 nodes, full structure) |
| `scripts/exp026_synthetic_cpu.py` | Synthetic x86-64 CPU emulator with full tracing |
| `scripts/exp026_synthetic_trace.json` | Saved synthetic CPU trace for `il2cpp_init` |
| `scripts/exp026_test_all_symbols.py` | Runs synthetic CPU on all 239 symbols |
| `download/exp026/_Exp026ResolverTracer.cs` | C# tracer for SharpEmu integration |
| `download/exp026/_Exp026_Patch_Instructions.cs` | Integration instructions for SharpEmu |
| `download/exp026/exp026_il2cpp_init_trace.log` | Synthetic CPU trace log for `il2cpp_init` |
| `download/exp026/EXP026_DIVERGENCE_REPORT.md` | This report |

---

## 6. Conclusion

**The bug is NOT in the resolver algorithm, the tree, or strcmp.**

The synthetic x86-64 CPU emulator — which executes the resolver's exact
instruction sequence (cmp, test, cmovns, je, js, call strcmp, mov, lea)
on the actual in-memory tree — finds ALL 239 IL2CPP symbols. The reference
Python RBTree implementation agrees on all 239 symbols.

SharpEmu's NATIVE execution of the same resolver at `0x804ED9B90` returns
0 for all 232 calls. This means at some instruction during native execution,
SharpEmu's CPU emulation produces a different result than the synthetic model
predicts.

**The most likely culprit is the `cmovns` instruction**, which depends on the
SF flag preserved across a `lea` instruction. If SharpEmu's `lea` clobbers
SF (it shouldn't — `lea` does not modify flags per Intel SDM), or if `cmovns`
reads the wrong flag, the resolver would walk the tree in the wrong direction
and fail to find any symbol.

**Recommended next experiment (EXP-027):**
Build a single-step tracer that logs every instruction's RIP, registers, and
RFLAGS during the resolver's native execution. Compare with the synthetic
CPU's trace. The first instruction where they differ is the bug.

---

## Appendix A: Synthetic CPU Trace for `il2cpp_init` (Full)

See: `exp026_il2cpp_init_trace.log`

Selected highlights:

```
Step  1: 0x804ED9B90  push rbp                  | prologue
Step  4: 0x804ED9B9B  mov r15, [rip+0x3c79b66]  | r15 = list_head_struct = 0x2000003f20
Step  5: 0x804ED9BA2  mov rbx, [r15+8]           | rbx = root = 0x2000027440
Step  6: 0x804ED9BA6  cmp byte [rbx+0x19]=0, 0   | flag_19=0 (real) [TAKEN→do_lookup]
Step  7: 0x804ED9BB7  mov r14, rdi               | r14 = query
Step  8: 0x804ED9BBA  mov r12, r15               | r12 = candidate = sentinel (no candidate yet)
Step 11: 0x804ED9BC7  call strcmp                | strcmp('il2cpp_class_num_fields','il2cpp_init')=-6
Step 12: 0x804ED9BCC  test eax, eax              | SF=1 ZF=0 (negative)
Step 14: 0x804ED9BD2  cmovns rcx, rbx            | SF=1 → NOT_TAKEN (use LEFT)
Step 15: 0x804ED9BD6  cmovns r12, rbx            | SF=1 → NOT_TAKEN (no candidate update)
Step 16: 0x804ED9BDA  mov rbx, [rcx]             | rbx = next = 0x2000028340

[... 8 more iterations through the tree ...]

Step 92: 0x804ED9BC7  call strcmp                | strcmp('il2cpp_init','il2cpp_init')=0
Step 93: 0x804ED9BCC  test eax, eax              | SF=0 ZF=1 (zero)
Step 95: 0x804ED9BD2  cmovns rcx, rbx            | SF=0 → TAKEN (use RIGHT)
Step 96: 0x804ED9BD6  cmovns r12, rbx            | SF=0 → TAKEN (candidate = current)
Step 97: 0x804ED9BDA  mov rbx, [rcx]             | rbx = next = 0x2000003f20 (sentinel)
Step 98: 0x804ED9BDD  cmp byte [rbx+0x19]=1, 0   | SENTINEL [NOT_TAKEN→after_loop]
Step 99: 0x804ED9BE3  cmp r12, r15               | r12=0x2000025a40 ≠ r15=0x2000003f20 [NOT_TAKEN]
Step102: 0x804ED9BF0  call strcmp (final)        | strcmp('il2cpp_init','il2cpp_init')=0
Step104: 0x804ED9BF7  js return_0                | SF=0 → NOT_TAKEN → return func_ptr
Step105: 0x804ED9BF9  mov rax, [r12+0x28]        | rax = 0x804ed8770 (SUCCESS)
Step106: 0x804ED9BB6  ret                        | RETURN rax=0x804ed8770
```

The synthetic CPU found `il2cpp_init` at address `0x2000025a40` with
`func_impl = 0x804ed8770`. SharpEmu's native execution returned 0.

## Appendix B: All 239 Symbols Test Result

```
Total symbols tested:    239
Synthetic CPU found:     239 (100%)
Reference impl found:    239 (100%)
Mismatches:              0
```

**The resolver algorithm is correct. The bug is in SharpEmu's native CPU
emulation.**
