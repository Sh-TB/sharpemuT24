# EXP-112 — Filtered audit of real_init's 164 calls (cross-referenced with prior EXP findings)

**Date:** 2026-08-03
**PRX:** `/tmp/games/yatzi/Il2cppUserAssemblies.prx` (45.6 MB exec segment)
**PRX runtime base:** `0x804CD5000`
**real_init:** `0x804F04BA0` (4560 bytes, 838 instructions, 164 call instructions)

## Method

Per the reviewer's three-point guidance:

1. **Don't audit all 164 blind** — cross-reference against prior EXP runtime logs.
   I don't have direct access to the prior trace files (they lived in the prior
   session context), but the EXP-040 / EXP-077 / EXP-098 md files give enough
   timeline data to identify which of real_init's calls have already been
   confirmed reached.

2. **Position-prioritize** — focus on the tail of real_init, where the stall
   approaches. Per EXP-077: real_init enters at trace line ~8600, AllocateDirectMemory
   fires at ~9360, stall begins immediately after. So the calls in the last
   ~700 lines of trace are the suspects.

3. **Ask a different-level question** — instead of "look inside the callback
   subsystem for its own trigger," ask: "is there a call in real_init's short-list
   whose wrong return value would explain why the callback dispatch subsystem
   never gets triggered from outside?"

## Step 1 — Statically extract all 164 call targets from real_init

| Call type | Count | Notes |
|-----------|-------|-------|
| Direct (PRX-internal) | 159 | All target well within the PRX text segment |
| Indirect via memory | 1 | Call #7 at `0x804F04C5C`: `call [rax]` — the eboot.bin callback (per EXP-040) |
| "Low address" small functions | 4 | Calls #3, #9 → `0x230` (1-byte `ret`); call #160 → `0x280` (abort/unreachable stub) |
| **Actual HLE/PLT calls** | **0** | **real_init does not directly call any HLE/libc function** |

**Critical correction to my initial scan:** I had classified the 4 "low address"
calls as PLT stubs (heuristic: `target_elf < 0x10000`). Spot-disassembly proved
this wrong — `0x230` is a 1-byte `ret` instruction (a no-op stub), and `0x280`
is a 12-byte abort stub (`push rax; call <helper>; call <helper>; ud2`). These
are PRX-internal small functions, not HLE imports. **real_init has 0 HLE calls.**

### Dominant call target

`0x804F21D70` is called **88 times** from real_init (calls #18 through ~#117).
This is the metadata registration loop body — each call registers one metadata
entry. (EXP-040 referenced this as "calls #8-80, the 63+ calls to 0x804EEE8D0";
the address differs slightly, probably because EXP-040 was on an earlier
build of the binary, but the structural role is the same.)

## Step 2 — Position-prioritized short-list (real_init's tail)

The normal execution path through real_init's tail is calls **#147 through #156**
(calls #157-#164 are in error/loop-back paths — see Step 4):

| # | Site (runtime VA) | Target | Notes |
|---|-------------------|--------|-------|
| #147 | `0x804F05B55` | `0x804F70D30` | Setup; calls `0x804F21D70` (dominant target), `0x804F47720`, `0x804FC31E0` (once-init) |
| #148 | `0x804F05B5F` | `0x804F70D80` | Setup; calls `0x804FC31E0` (once-init) |
| #149 | `0x804F05B68` | `0x804FA8120` | Setup |
| #150 | `0x804F05B71` | `0x804F05D70` | **Function immediately after real_init** — string/metadata consumer |
| **#151** | `0x804F05B76` | **`0x804F3E700`** | **GATE function** — 6 bytes: `mov eax, [rip+disp]; ret` |
| **#152** | `0x804F05BA3` | **`0x804F3DF90`** | **CONDITIONAL** — only runs if gate==0; called with `rsi=1` |
| #153 | `0x804F05BA8` | `0x804F239B0` | Setup |
| #154 | `0x804F05BAD` | `0x804F23A40` | Setup |
| #155 | `0x804F05BB2` | `0x804EE5C70` | Setup |
| #156 | `0x804F05BD7` | `0x804FC2C80` | **Shared with the registered callback `0x804FA1FE0`** |

The gate-check pattern at site `0x804F05B76`:

```asm
0x804f05b76: call 0x269700         ; #151 — gate function: returns global flag
0x804f05b7b: test eax, eax
0x804f05b7d: jne  0x230ba8         ; if non-zero, skip #152
0x804f05b9e: mov  esi, 1
0x804f05ba3: call 0x268f90         ; #152 — only runs if gate==0
0x804f05ba8: call 0x24e9b0         ; #153 — continues regardless
```

## Step 3 — The GATE function and its writers

The gate function `0x804F3E700` is just 6 bytes:

```asm
0x804f3e700: mov eax, [rip + 0x3c15c9a]   ; load global at 0x808B543A0
0x804f3e706: ret
```

The global lives in the BSS section of the second RW PT_LOAD segment
(p_vaddr=`0x3C50000`, p_memsz=`0x444778` > p_filesz=`0x21CBC8`). It is
**zero-initialized** at program start.

### Writers to the gate global

A byte-pattern search of the entire 45.6 MB text segment found exactly **2 writers**:

| Site | Containing function | Instruction |
|------|---------------------|-------------|
| `0x804F3DFC3` | **`0x804F3DF90`** (= call #152 target) | `mov [rip+0x3c163d7], esi` (writes the function's `esi` arg) |
| `0x804F3E674` | `0x804F3E660` | `mov [rip+0x3c15d26], esi` (writes the function's `esi` arg) |

### Caller analysis

| Function | Callers | Verdict |
|----------|---------|---------|
| `0x804F3DF90` (call #152 target) | **1 caller**: real_init (`0x804F04BA0`) at site `0x804F05BA3` | Only entry point is real_init's #152 |
| `0x804F3E660` (second writer) | **0 callers** | **DEAD CODE** — never invoked from anywhere in the PRX |
| `0x804F3E450` (called by both writers) | 2 callers: the two writers above | Only reachable via #152 (since `0x804F3E660` is dead) |

**Conclusion:** The gate global is set **only** by call #152. There is no other
code path that could pre-set the gate to non-zero before real_init runs.

### Lazy-init pattern

- BSS initializes gate to 0
- First real_init call: #151 returns 0 → #152 runs → #152 writes gate=1 (early in its body, at offset 0x33) → #152 does its work
- Subsequent real_init calls: #151 returns 1 → #152 skipped

This is textbook lazy initialization. The gate is **not** the blocker — #152
runs on the first real_init call.

## Step 4 — Error/loop-back paths (calls #157-#164)

Calls #157-#164 are NOT in the normal execution path:

| # | Site | Target | Path |
|---|------|--------|------|
| #157 | `0x804F05C82` | `0x804FC1C60` (helper_1) | Loop-back path — `mov rdi, [rip+...]; call helper_1; jmp 0x22FBFD` (jumps back to early real_init) |
| #158 | `0x804F05C9D` | `0x804FC1CE0` (helper_2) | Stack-canary-fail path (`0x804F05C57: jne 0x230CA4` if canary corrupted) |
| #159 | `0x804F05CA4` | `0x804FC2990` | `__stack_chk_fail` (no-return) — only reached if canary corrupted |
| #160 | `0x804F05CAE` | `0x280` (abort stub) | Dead code after `__stack_chk_fail` |
| #161-#164 | `0x804F05CF5..0x804F05D5B` | `0x804FC2C80` (×2), `0x804EBECC0`, `0x804FC29C0` | Cleanup path ending in `ud2` at `0x804F05D60` |

So the actual call sequence executed in a normal real_init run is **calls #1
through #156** (with #152 conditional on the gate). #157-#164 only fire on
error paths or iterations.

## Step 5 — What call #152 actually does

`0x804F3DF90` is a 1216-byte function (292 instructions, 6 internal calls):

| Internal call | Target | Purpose |
|---------------|--------|---------|
| 1 | `0x804F3E450` | Vector/array resize — grows an array by stride 0x28 (40 bytes, typical IL2CPP struct size) |
| 2 | `0x804FC2BE0` | Allocator (called with size 0x18 = 24 bytes) |
| 3 | `0x804F3F0C0` | Vector operation (SIMD: `vmovups`, `vxorps` — likely zeroing/initialization) |
| 4, 5 | `0x804FC2C80` | **The shared target with the registered callback** — called twice per loop iteration |
| 6 | `0x804FC2990` | `__stack_chk_fail` (only on canary-fail error path) |

The body iterates with `r13` from 0 to a count passed in `rbx` (sign-extended
from `rsi=1` from real_init, so the loop runs at least once). For each
iteration, it:
1. Calls the allocator to create a structure
2. Writes to `[r12+0x18]` and `[r12+0x20]` (struct fields at offsets 0x18 and 0x20)
3. Advances `r14`, `r15`, `r12`, `rbx` by stride 0x28
4. Calls `0x804FC2C80` (the shared target)

**This is the dispatch subsystem setup function.** It allocates an array of
structures and populates fields that the registered callback `0x804FA1FE0`
later reads via `[rbx+8]` and `[rbx+0x10]` (per the EXP-111 disassembly of
the callback).

## Step 6 — Answer to the user's point #3

> "is there a call in that short list which, if it returned differently
> (an unimplemented/wrong-behavior HLE stub), would explain why the whole
> callback/dispatch subsystem never gets triggered from outside?"

**Direct answer: No, not at the real_init level.** real_init has 0 direct
HLE/PLT calls — every call is to a PRX-internal function. The "wrong-behavior
HLE stub" hypothesis does not apply to real_init's own call list.

**However, the structural answer points to call #152 (`0x804F3DF90`) as the
critical setup function for the dispatch subsystem.** If #152 fails internally
— e.g., one of its callees (`0x804F3E450`, `0x804FC2BE0`, `0x804F3F0C0`,
`0x804FC2C80`) blocks on a semaphore or returns wrong — the dispatch
subsystem would not be set up correctly, even though the gate would still be
set to 1 (since #152 writes the gate early, at offset 0x33, before any
internal calls).

### The deeper question

The dispatch subsystem has two halves:
1. **Setup** (call #152 + the registration chain via 0x804F527C0 → 0x804FA20E0
   → 0x804F889D0 → 0x804FC33B0) — **structurally sound, all reached per prior EXPs**
2. **Trigger** (whatever invokes the registered callback `0x804FA1FE0`) —
   **never fires** (EXP-106 confirmed 0 direct callers, 0 INT3 hits)

EXP-106 through EXP-111 spent five rounds hunting for the trigger inside the
callback/dispatch subsystem itself and proved it doesn't exist there.

**The trigger must come from the runtime/HLE layer** — likely a semaphore
signal that should fire when some condition is met, causing the runtime to
invoke the registered callback. EXP-078 already established that semaphore
handle `0x5C` is never signaled (0 out of 5.7M SignalSema calls). The
connection:

- Call #152 sets up the dispatch state
- The registered callback waits to be invoked
- The invocation should be triggered by a semaphore signal
- SharpEmu either signals the wrong handle (per EXP-078: workers signal odd
  handles instead of even ones) or doesn't fire the signal at all
- Therefore the callback is never invoked

## Verdict

Per the reviewer's point #3, **EXP-112 is the decision point**. The verdict:

- The "search for a wrong-return-value HLE stub inside real_init" approach is
  **exhausted at the static level** — real_init has 0 HLE calls.
- The critical setup function (#152) is structurally correct and is reached
  (the gate ensures it runs on the first real_init call).
- The missing piece is **runtime-side**: the trigger that should invoke the
  registered callback never fires, likely because SharpEmu doesn't properly
  signal the semaphore that the runtime uses for callback dispatch.

## Recommended next step (EXP-113)

Stop static analysis of real_init. Pivot to **runtime tracing of call #152's
execution** to confirm:

1. Does #152 actually run to completion? (Set INT3 at its entry `0x804F3DF90`
   and at its return site in real_init `0x804F05BA8` — if both fire, #152
   completed.)
2. If #152 completes, does the registered callback `0x804FA1FE0` ever get
   invoked? (EXP-106 already showed 0 INT3 hits — re-confirm.)
3. If the callback is never invoked, identify which HLE function in the
   runtime's thread-pool / event-dispatch layer should be triggering the
   invocation, and check whether SharpEmu implements it.

This requires the runtime tracer infrastructure from prior EXPs (which lived
in the prior session context and isn't directly accessible here). The
recommendation is to set up EXP-113 as a runtime trace experiment, not a
static analysis.

## Artifacts

- `/home/z/my-project/scripts/exp112/extract_real_init_calls.py` — static call-target extractor
- `/home/z/my-project/scripts/exp112/real_init_calls.json` — full 164-call list with classification
- `/home/z/my-project/scripts/exp112/investigate_plt_and_tail.py` — PLT-stub and tail-call disassembler
- `/home/z/my-project/scripts/exp112/investigate_gate_and_cond_call.py` — gate function and #152 target disassembler
- `/home/z/my-project/scripts/exp112/find_gate_writers.py` — byte-pattern search for writers to the gate global
- `/home/z/my-project/scripts/exp112/find_callers_of_writers.py` — caller analysis for both gate-writer functions
- `/home/z/my-project/scripts/exp112/EXP-112_REPORT.md` — this report
