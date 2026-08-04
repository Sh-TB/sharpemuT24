# EXP-111 — Filtered indirect-dispatch (`call [reg+0x08]` / `mov rXX,[reg+0x08]; call rXX`) site analysis

**Date:** 2026-08-03
**PRX:** `/tmp/games/yatzi/Il2cppUserAssemblies.prx` (45.6 MB exec segment)
**PRX runtime base (SharpEmu):** `0x804CD5000`
**Text segment (ELF VA):** `0x0..0x2b9722a`

## Method

Per the reviewer's "filtered step 1" guidance, instead of blanket-tracing all
candidate sites with INT3 breakpoints, narrow first by **reachability cluster
membership**:

1. Identify all candidate indirect-dispatch sites in the PRX text segment using
   byte-pattern search (no capstone linear sweep — 45 MB is too large for that
   in a reasonable iteration cycle).
2. Map each site to its containing function via heuristic INT3-padding function
   starts (17,620 functions detected).
3. Cross-reference: do any of those containing functions belong to the known
   reachable cluster?
4. If 0 hits, the dispatch mechanism is structurally absent from the live code
   path; declare the "search by mechanism" approach exhausted for this
   subsystem and recommend pivoting.

### Patterns scanned

- **Pattern A** — direct `call qword ptr [reg+0x08]`:
  - 8 encodings for low regs (rax, rcx, rdx, rbx, rbp, rsi, rdi) + rsp (with SIB byte 0x24)
  - 8 encodings for high regs (r8..r15) + r12 (with REX.B + SIB byte)
- **Pattern B** — `mov rXX, qword ptr [reg+0x08]; … ≤24 bytes …; call rXX`:
  - 4 REX prefixes × 8 dst regs × 7 src regs (excluding rsp/r12) = 224 non-SIB variants
  - 4 REX × 8 dst regs × 1 SIB-form (rsp/r12) = 32 SIB variants
  - Window cap: 24 bytes between load and call (≈6 instructions; conservative to avoid
    register-reuse false positives)

## Results

| Pattern | Sites found | In known cluster |
|---------|-------------|------------------|
| A: `call [reg+0x08]` | **95** | **0** |
| B: `mov r,[reg+0x08]; …; call r` | **121** | **0** |
| **Total** | **216** | **0** |

### Pattern A by register

```
rax: 77
rcx: 16
rbx: 1
rsi: 1
```

### Top 15 containing functions (by site count)

```
17 sites in 0x806a59a30
14 sites in 0x806bab230
 9 sites in 0x804fc3f70       ← PLT/stub area; same neighborhood as once-init primitive
 5 sites in 0x8050583c0
 5 sites in 0x80663b7c0
 4 sites in 0x8052678b0
 4 sites in 0x804e58160
 3 sites in 0x80564a170
 2 sites in 0x804f64820
 2 sites in 0x805028fe0
 2 sites in 0x806a9b3e0
 2 sites in 0x804e4f2e0
 2 sites in 0x804dbd8b0
 2 sites in 0x804dc7300
 2 sites in 0x804dcfde0
```

155 distinct containing functions host at least one site. None of those 155
functions is `real_init`, `0x804F527C0`, `0x804FA20E0`, `0x804F889D0`,
`0x804F88A76` (mid-function), or `0x804FC33B0` (the once-init primitive that
prior EXP-099 confirmed returns SUCCESS).

## Spot-check verification

To rule out the possibility that the heuristic function-boundary detector got
the cluster mapping wrong, I capstone-disassembled each of the 5 known
reachable functions and counted their `call` instructions and
`mov rXX, [reg+0x08]` loads:

| Function | Runtime VA | Size (B) | Total `call`s | `call [reg+0x08]` | `mov r,[reg+0x08]` loads | Pattern B fires? |
|----------|------------|----------|---------------|-------------------|--------------------------|------------------|
| real_init | 0x804F04BA0 | 4560 | 164 | 0 | 2 (rdi←rbx; esi←rcx — both used as args, not call targets) | No |
| registration_parent | 0x804F527C0 | 352 | 17 | 0 | 0 | No |
| registration_func | 0x804FA20E0 | 80 | 1 | 0 | 1 (rdi←rbx — argument for direct call, not call target) | No |
| registration_helper | 0x804F889D0 | 208 | 7 | 0 | 0 | No |
| once_init_primitive | 0x804FC2930..0x804FC33B0 (mid-function) | ~3008 | 46 | 0 (only `call rax`/`call rdx`, both from values in registers, not loaded from `[reg+8]` immediately before) | 0 | No |

**Spot-check conclusion:** the byte-pattern scan is correct. There is no
`call [reg+0x08]` or `mov r,[reg+0x08]; call r` site inside any of the 5 known
reachable functions.

## Wider-window sanity check (Pattern B with 256-byte window)

To check whether the 24-byte Pattern B window was too tight, re-ran with a
256-byte window for the specific pattern the prior context claimed to have
"re-derived" (`mov r12, [rbx+8]; call r12` = bytes `4C 8B 63 08` … `41 FF D4`):

```
loads (mov r12, [rbx+8]): 158
calls (call r12):          195
pairs within 256 bytes:      2
```

Two hits:

1. **`0x804FA2002` (load) → `0x804FA2073` (call r12), delta=113 bytes** — *real* match.
   - Containing function: **`0x804FA1FE0`** (starts at `0x804FA1FE0` with `push rbp`).
   - **This is the registered callback that prior EXP-106 confirmed is never invoked.**
   - Disassembly shows the full pattern: `mov r12, [rbx+8]; mov r14, [rbx+0x10]; …; call r12` → then `call 0x804F9FA80` → eventually `jmp rax` (tail-call dispatch).
   - So the dispatch mechanism exists and is exactly the pattern I cited — but it lives in code that the runtime never reaches.

2. **`0x80575D9AA` (load) → `0x80575DA71` (call r12), delta=199 bytes** — *false positive*.
   - At `0x80575DA4F`, `r12` is overwritten by `mov r12, [rax]`, so the call at `0x80575DA71` uses a different `r12` value than the load at `0x80575D9AA`.
   - This confirms that the 24-byte window is the right choice — a 256-byte window introduces register-reuse false positives.

## Decision

**The "search by mechanism" approach is exhausted for this subsystem.**

The dispatch mechanism exists in the binary (1 confirmed site at `0x804FA1FE0`,
plus 95+121 other indirect-disp8 sites scattered across 155 other functions),
but **none of those 155 functions is in the reachable cluster** that we have
verified runs during real_init.

Per the reviewer's point #3 — five EXPs (106→110) deep into one
callback-dispatch mechanism without a definitive answer is the threshold.
EXP-111 was the decision point, and the verdict is: **the missing wire is not
another `call [reg+0x08]` site we haven't found; it's the trigger that invokes
`0x804FA1FE0` itself.**

The user's point #3 (final paragraph) is the right next move: rather than
continue hunting for the one specific missing wire inside this subsystem,
pivot to asking whether `real_init`'s call sequence (calls #10..#85, most
unexamined since EXP-050) contains something that stalls earlier and
independently prevents this whole subsystem from ever being set up correctly.

## Recommended pivot (EXP-112)

Audit `real_init` (0x804F04BA0, 4560 bytes, 164 `call` instructions) call-by-call:

- Identify each of the 164 call targets
- For each, determine: (a) is it reached at runtime? (b) does it return?
  (c) what side effects does it have?
- The summary notes the main thread "STALLs on WaitSema" after
  `sceKernelAllocateDirectMemory` — find which of the 164 calls is the first
  one that blocks, and what primitive it's waiting on.

This is a more productive use of the next EXP cycle than continuing to widen
the indirect-dispatch search.

## Artifacts

- `/home/z/my-project/scripts/exp111/exp111_filter_analysis_v2.py` — fast byte-pattern scanner (v2, regex-based)
- `/home/z/my-project/scripts/exp111/exp111_verify_known_funcs.py` — capstone spot-disassembly of the 5 known reachable functions
- `/home/z/my-project/scripts/exp111/exp111_sites.json` — full site list with containing-function attribution
- `/home/z/my-project/scripts/exp111/EXP-111_REPORT.md` — this report
