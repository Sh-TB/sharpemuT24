# EXP-113 — External Developer Claim Validation + Trajectory Reassessment

**Date:** 2026-08-03
**Purpose:** Validate 5 external developer claims against accumulated runtime/static evidence; preserve confirmed findings; honestly assess trajectory and propose a new direction that avoids repeating EXP-089's conclusion.
**Code changes:** NONE (analysis only, per request)

---

## Part 1 — Claim Validation

### Claim 1 — Asset Loading

**Claim:** "First frame blocked because game data files are missing."

**Verdict: REJECTED**

**Evidence (all from prior EXPs + this session's filesystem):**

| Check | Result |
|-------|--------|
| Are Yatzi Media files present? | YES — `/tmp/games/yatzi/Media/` exists; `eboot.bin`, `Il2cppUserAssemblies.prx`, `global-metadata.dat`, `libc.prx`, `Media/` all present (verified this session) |
| Does fopen/path resolution work? | YES — `global-metadata.dat` (10.6 MB) is loaded and parsed; IL2CPP magic bytes are read; the metadata registration loop runs (88 calls to `0x804F21D70` from real_init, see EXP-112) |
| Are Unity files loaded successfully? | YES — game reaches `il2cpp_init` (trace line ~1994 per EXP-077), hash table writer (~8542), real_init (~8600), `sceKernelAllocateDirectMemory` (~9360) |
| Is there evidence of missing assets causing the stall? | NO — the stall is in PRX semaphore code (WaitSema/SignalSema spin), NOT in file I/O. EXP-077 confirmed: "GPU init is NOT the direct blocker — main thread reaches sceKernelAllocateDirectMemory then stalls on WaitSema in PRX code" |

The external claim was already rejected in the prior conversation summary's validation table. The accumulated evidence is unambiguous: file loading succeeded all the way through IL2CPP metadata parsing and into the runtime init phase; the stall is in semaphore synchronization, not asset loading.

---

### Claim 2 — ThreadPool

**Claim:** "ThreadPool is working."

**Verdict: REJECTED**

The instruction says "Do not accept because threads exist." This is the correct stance — thread existence ≠ thread pool correctness. Five distinct failure modes:

| Check | Result | Source |
|-------|--------|--------|
| Are worker threads created? | YES — 13 `AssetGarbageCollectorHelper` threads created (trace lines 8550-8631) | EXP-077 |
| Is work submission reached? | **NO** — `0x804F6EC20` (work submission function) has **0 INT3 hits** across all 3 call sites | EXP-096 |
| Is the work queue receiving jobs? | **NO** — work submission never fires, so no jobs are enqueued | EXP-096 |
| Is SignalSema called? | YES, but on **wrong handles** — 5.3M SignalSema calls, all on odd handles (main thread's semaphores via `[rbx+0xB0]`); 0 calls on even handles (worker semaphores) | EXP-078 |
| Is WaitSema released? | **NO** — handle `0x5C` (the correct worker completion semaphore) is **never signaled** (0 out of 5.7M SignalSema calls); `WaitSema(0xA6)` blocks indefinitely | EXP-078, EXP-077 |

The pool exists structurally (13 threads, 144 semaphores created), but it is non-functional: no work is submitted, workers signal the wrong handles, the correct completion semaphore is never raised, and the main thread blocks forever waiting for it. The "ThreadPool is working" claim fails on every functional check except thread existence.

---

### Claim 3 — Callback Registration

**Claim:** "Callback registration is broken."

**Per instruction, separate Registration from Invocation. Do not combine them.**

#### Registration half

**Verdict: REJECTED (registration works correctly)**

| Check | Result | Source |
|-------|--------|--------|
| Registration function reached? | YES — `0x804FA20E0` IS reached; caller is `0x804F527F9` in `0x804F527C0`, which is called from real_init | EXP-098 |
| Registration helper reached? | YES — `0x804F889D0` IS reached; all PLT stubs return `eax=0` (success) | EXP-101 |
| Once-init primitive succeeds? | YES — `0x804FC33B0` returns `eax=0` (SUCCESS) | EXP-099 |
| Callback pointer stored? | YES — `xchg [r14], rax` at `0x804F88A76` IS reached; `r14=0x20337660` (valid guest heap); after the xchg, `r14` holds the previous value (NULL on first run, confirming the slot was empty before this registration) | EXP-101, EXP-103 |
| Global/context populated? | YES — callback structure at global `0x808B54898`, `[+0x10]=0x804FA1FE0` (the registered callback function pointer); `r12=0x7FCEC8EE0710` (IL2CPP context populated) | EXP-104, EXP-103 |

**Critical correction (EXP-103):** An earlier EXP-102 had claimed `r14=0` (NULL), suggesting broken registration storage. EXP-103 proved this was a **tracer bug** — wrong register offsets in the tracer (`CTX_R14=284` instead of `232`, `CTX_R12=276` instead of `216`). After correcting the offsets, `r14` and `r12` are both valid. Registration storage is NOT broken.

#### Invocation half

**Verdict: CONFIRMED (invocation is broken — never happens)**

| Check | Result | Source |
|-------|--------|--------|
| Is the stored callback function pointer ever invoked? | **NO** — `0x804FA1FE0` (the registered callback) has **0 INT3 hits**; 0 direct callers in static analysis | EXP-106 |
| Is the callback invoker reached? | **NO** — `0x804F88AD0` has **0 INT3 hits**; 0 callers, 0 LEA references, 0 stored qwords | EXP-107, EXP-108 |
| Are related dispatch sites reached? | **NO** — `0x804FA84E0` and `0x804FC3720` (PLT 218) both have **0 INT3 hits** | EXP-107 |
| Does the dispatch mechanism exist statically? | YES — the `mov r12, [rbx+8]; …; call r12` pattern IS present in `0x804FA1FE0` (confirmed via byte-pattern scan in EXP-111) — but it lives inside the very callback that is never invoked | EXP-111 |

#### Combined claim verdict

The claim "Callback registration is broken" conflates two distinct subsystems. **Registration is structurally sound and runs to completion.** **Invocation never happens.** If the claim is interpreted strictly as "registration is broken," it is REJECTED. If interpreted broadly to include invocation, it is PARTIAL.

The actionable conclusion: stop investigating the registration path (it works). The broken half is invocation.

---

### Claim 4 — PLT218

**Claim:** "PLT218 is the missing link."

**Verdict: REJECTED**

| Check | Result | Source |
|-------|--------|--------|
| Is `0x804F88AD0` executed at runtime? | **NO** — 0 INT3 hits | EXP-107 |
| Is `0x804FA84E0` executed at runtime? | **NO** — 0 INT3 hits | EXP-107 |
| Is `0x804FC3720` (PLT 218) executed at runtime? | **NO** — 0 INT3 hits | EXP-107 |

The instruction was explicit: "If runtime hits = 0, then reject." All three addresses in the PLT218 path have 0 runtime hits. PLT218 cannot be "the missing link" because it is never reached. The path was a hypothesis that runtime tracing definitively ruled out.

---

### Claim 5 — Import Resolution

**Claim:** "466/466 IL2CPP imports resolve."

**Verdict: PARTIAL**

| Check | Result | Source |
|-------|--------|--------|
| Does the IL2CPP resolver run? | YES — "resolver runs 232 functions" (per EXP-040); resolver runs early in il2cpp_init | EXP-040 |
| How many imports really resolve? | **Unknown from this session's filesystem** — the exact resolution count requires re-examining prior trace logs, which are not directly accessible in this session's working directory | — |
| Are unresolved imports blockers? | **NO** — at least one NID (`J3edELK4FvM`) is unresolved, but the code checks `cmp eax, 0x80020003` and SharpEmu returns 0, so the code continues | EXP-100 |
| Do unresolved functions appear before stall? | NO — the stall is in semaphore code (WaitSema/SignalSema spin in PRX), not in import resolution. Import resolution completed before real_init was entered | EXP-077 |

The specific "466/466" count cannot be confirmed or rejected from available evidence in this session. What CAN be confirmed: at least one NID is unresolved (so 466/466 is unlikely to be literally true), but the unresolved NID does not block (so the import resolution layer is not the stall's cause). The stall is downstream, in semaphore synchronization.

---

## Part 2 — Preserved Findings (Confirmed Facts)

These are confirmed facts from previous experiments and remain valid. They form the negative-space map accumulated across 113 EXPs.

### EXP-103 — Tracer register-offset bug (corrected)

- The EXP-102 tracer used wrong offsets: `CTX_R14=284` (should be `232`), `CTX_R12=276` (should be `216`)
- After correction: `r14 = 0x20337660` (valid guest heap address), `r12 = 0x7FCEC8EE0710` (valid IL2CPP context)
- **Conclusion:** Registration storage was NOT broken. The earlier "NULL r14" finding was a tracer artifact.

### EXP-104 / EXP-105 — Callback structure correctly allocated and stored

- Callback structure allocated correctly at global `0x808B54898`
- Function pointer `[+0x10] = 0x804FA1FE0` stored correctly
- **Conclusion:** Registration storage works. The invocation path is what's unproven.

### EXP-106 — Static call chain is valid

The static chain exists:
```
0x804FA1FE0  (registered callback)
      |
      v
0x804F9FA80  (called from 0x804FA1FE0 at offset 0x153)
      |
      v
0x804F6EC20  (work submission — never reached at runtime)
```

**But static chain does not prove runtime execution.** The chain exists in the binary, but `0x804FA1FE0` itself is never invoked, so the chain never fires.

### EXP-107 — Runtime validation of PLT218 path

- `0x804F88AD0` = 0 INT3 hits
- `0x804FA84E0` = 0 INT3 hits
- `0x804FC3720` = 0 INT3 hits

**Therefore:** PLT218 path is not executed at runtime. The hypothesis is definitively rejected.

### EXP-108 / EXP-109 — No dispatcher callers found

- Registered functions exist (verified in callback structure)
- But invocation mechanism is missing
- All 18 callers of the most promising dispatch site (`0x804F760B0`) themselves have 0 callers — entire subtree is dead code

### EXP-111 — Filtered indirect-dispatch scan (this session)

- 216 indirect-disp8 sites (`call [reg+0x08]` or `mov r,[reg+0x08]; call r`) found across the 45.6 MB PRX text
- **0 of these sites fall inside any of the 5 known reachable functions** (real_init, registration_parent, registration_func, registration_helper, once_init_primitive)
- The specific `mov r12, [rbx+8]; call r12` pattern IS real and lives inside `0x804FA1FE0` — but that function is never invoked
- **Conclusion:** The dispatch mechanism exists in the binary but is structurally absent from the live code path

### EXP-112 — real_init call audit (this session)

- real_init has 164 call instructions: 159 direct (PRX-internal), 1 indirect-mem (call #7 = eboot.bin callback), 4 to PRX-internal small stubs (no-op `ret` + abort)
- **0 direct HLE/PLT calls** — real_init does not directly call any HLE/libc function
- The tail has a gate-protected lazy-init pattern: call #151 reads a BSS global; if 0, call #152 runs and writes the global to 1
- Call #152 (`0x804F3DF90`) is the **dispatch subsystem setup function** — it allocates structures and calls `0x804FC2C80` (the same target the registered callback uses)
- The gate has exactly 2 writers in the entire binary: #152 itself, and `0x804F3E660` which has 0 callers (dead code)
- **Conclusion:** The setup half of the dispatch subsystem is structurally sound and runs. The trigger half is what's missing.

---

## Part 3 — Trajectory Reassessment

### The honest observation

EXP-089 (from ~20 EXPs ago) concluded: "no work is submitted… likely a GC trigger, timer/event, or callback SharpEmu doesn't implement."

EXP-112 (this session) concluded: "the trigger that should invoke the registered callback never fires, likely because SharpEmu doesn't properly signal the semaphore."

**These are the same conclusion with more supporting detail underneath.** The actionable positive answer — "here is the one specific missing HLE behavior" — has not moved in 20+ EXPs of narrowing from the symptom downward through IL2CPP callback machinery.

What HAS been accomplished in those 20 EXPs is valuable negative-space mapping:
- Registration is not broken (EXP-098 through EXP-105)
- PLT218 is not the missing link (EXP-107)
- Once-init succeeds (EXP-099)
- Unresolved NIDs are not blockers (EXP-100)
- All PLT stubs in the registration path return success (EXP-101)
- The dispatch mechanism exists in the binary but lives in unreachable code (EXP-111)
- real_init has 0 direct HLE calls; the gate-protected setup function runs (EXP-112)

This is real, hard-won elimination. But eliminating wrong answers is not the same as finding the right one, and the right one has not been found by narrowing from the symptom downward.

### Why EXP-113 as I originally proposed it would be EXP-089 v3

I originally proposed: "Set INT3 at `0x804F3DF90` (call #152 entry) and `0x804F05BA8` (return site) to confirm #152 completes; then identify which HLE function should trigger the callback invocation."

The reviewer is right to flag this. Even if #152 completes (which it likely does, given that the gate is set to 1 on first run and the registration chain succeeds), the conclusion would be: "the setup runs but the trigger is missing." That is EXP-089's conclusion with new function names attached. It does not move the positive answer.

### The three reframes (assessment)

#### Reframe 1 — Unity source dive for thread-pool bootstrap requirements

**Feasibility: HIGH.** Unity 2022.3.5f1 struct definitions are already in the project (per EXP-059, pulled from `nneonneo/Il2CppVersions`). EXP-059 successfully used them to verify struct layouts.

**What it would answer:** What does Unity's thread-pool bootstrap sequence actually require from the OS at this exact point (GC init → thread pool creation → first work item)? Specifically:
- Does it require a wakeable event object that SharpEmu doesn't implement?
- Does it require a specific kernel primitive (e.g., `kevent`, `kcondvar`) that maps imperfectly to PS5 semaphores?
- Does it require an actual OS thread to start a work-stealing loop, and if so, what's the wake-up mechanism?

**Limitation:** Unity's source/headers describe structure layouts and call signatures, not OS-level synchronization semantics. The headers can tell us *what* Unity calls, but not *what behavior* those calls should have on PS5. For behavior, we'd need PS5 SDK docs or SharpEmu maintainer input.

#### Reframe 2 — Low-level sync primitive correctness

**Feasibility: HIGH, and there's concrete surface area.** The PRX has:
- 71,857 `lock`-prefixed instructions across 45.6 MB (1 per 636 bytes)
- 188 `lock cmpxchg` (atomic compare-and-swap)
- 118 `lock xadd` (atomic fetch-and-add)

The registered callback `0x804FA1FE0` uses `lock cmpxchg dword ptr [rbx + 0x10], edx` (verified in EXP-111 disassembly). The worker code (per EXP-078) spins in a tight loop calling SignalSema on wrong handles — a spin pattern that could be caused by:
- A `lock cmpxchg` that always fails (emulator ZF-flag bug, since `cmpxchg` sets ZF based on whether the comparison matched)
- A `lock xadd` that doesn't atomically update memory (emulator memory-ordering bug)
- A spurious-wake handling issue in `WaitSema` (POSIX semaphores can spuriously wake; does SharpEmu?)
- A race condition in the worker startup sequence (workers start before the work queue is initialized?)

**What it would answer:** Is the bug at the IL2CPP layer (where 112 EXPs have been searching) or at the emulator's atomic-operation / semaphore-implementation layer (which has never been directly tested for correctness)?

**Why this is the most promising reframe:** It's the only one of the three that addresses a layer that hasn't been investigated at all. Every prior EXP has assumed the emulator's low-level primitives work correctly and looked for the bug in IL2CPP/game code. If the emulator's `lock cmpxchg` or `WaitSema` has a subtle correctness bug, every prior EXP's conclusions would still be technically correct (the IL2CPP code IS structurally sound) but the bug would be invisible to all of them.

#### Reframe 3 — Consolidated summary to SharpEmu maintainers

**Feasibility: HIGH.** GitHub Issue #1 is already open (per prior conversation). The negative-space map from 113 EXPs is exactly the kind of context maintainers need to answer a focused question.

**What it would answer:** "What does the PS5 job-system semaphore primitive actually need to do differently for Unity's thread-pool bootstrap to progress past GC init?" — this is the kind of question the people who wrote the semaphore/threading HLE layer could answer in one message, where it's taken 100+ EXPs to narrow down from the game side.

**Limitation:** Depends on maintainer responsiveness. But the alternative (more solo EXPs) has diminishing returns per the trajectory analysis above.

### Recommended direction

**Do both Reframe 2 and Reframe 3, in parallel.**

- **Reframe 2 (EXP-114):** Write a focused test that exercises SharpEmu's `lock cmpxchg` and `lock xadd` implementations directly, independent of any game code. If a correctness bug is found, that's the answer. If not, that's also a definitive negative result that narrows the search.

- **Reframe 3 (EXP-115):** Write a consolidated "unsolved after 113 EXPs" summary covering: (a) the negative-space map (what's been ruled out), (b) the structural finding (setup works, trigger is missing), (c) the specific question for maintainers (what does the PS5 job-system semaphore primitive need to do differently). Post to GitHub Issue #1.

**Do NOT do EXP-113 as originally proposed** (runtime trace of #152 completion). It would be EXP-089 v3.

---

## Part 4 — New Debugging Direction

### Direction A (Reframe 2): Low-level sync primitive correctness test

**Hypothesis:** The bug is in SharpEmu's implementation of `lock cmpxchg`, `lock xadd`, or `WaitSema`/`SignalSema` semantics, not in IL2CPP or game code.

**Test design (analysis only, no implementation yet):**

1. Identify all `lock cmpxchg` and `lock xadd` sites in the worker spin loop (the 13 workers spinning at return address `0x800AA0223` per EXP-078). The worker function is at `0x800AA0170` in eboot.bin.
2. For each site, determine what memory location is being atomically updated and what the expected semantics are.
3. Check SharpEmu's `DirectExecutionBackend` for the `lock cmpxchg` and `lock xadd` handlers — verify they:
   - Perform the locked memory access atomically (not just read-modify-write)
   - Set the ZF flag correctly based on whether the comparison matched (this is the most common emulator bug for `cmpxchg`)
   - Handle the REX.W prefix correctly for 64-bit operations
4. Check SharpEmu's `WaitSema`/`SignalSema` HLE for:
   - Spurious-wake handling (does it loop on the wait if woken without count?)
   - Count semantics (does decrement happen atomically with the wake?)
   - Handle validation (does it correctly distinguish even vs. odd handles, per EXP-078's finding that workers signal wrong handles?)

**Expected outcomes:**
- If a bug is found: that's the answer — the emulator's primitives are subtly wrong, and 112 EXPs of IL2CPP analysis were technically correct but investigating the wrong layer.
- If no bug is found: that's a definitive negative result that rules out the sync-primitive layer and points back to the runtime/HLE layer (which then justifies Reframe 3 / maintainer input).

### Direction B (Reframe 3): Consolidated summary to maintainers

**Hypothesis:** The maintainers can answer "what does the PS5 job-system semaphore primitive need to do differently" in one message, given the accumulated context.

**Deliverable design:**

1. Write a single consolidated summary document covering:
   - The negative-space map (112 EXPs of ruled-out hypotheses, summarized in a table)
   - The structural finding (setup works, trigger is missing)
   - The specific question: "What HLE behavior in SharpEmu's thread-pool/event-dispatch layer should trigger the invocation of a registered IL2CPP callback? Is there a known gap in semaphore/event handling that would explain why a registered callback is never invoked even though its registration completes successfully?"
2. Post to GitHub Issue #1 with the summary and a focused question.

**Expected outcomes:**
- If maintainers answer: the bug is identified without another solo EXP.
- If maintainers don't answer: Direction A's results are still useful and can be pursued solo.

### What NOT to do next

- Do NOT continue hunting for specific function addresses in the IL2CPP layer (E8/LEA/stored-qword lookups have failed 4+ times).
- Do NOT do EXP-113 as originally proposed (runtime trace of #152 completion) — it would be EXP-089 v3.
- Do NOT assume the bug is at the IL2CPP layer without first ruling out the emulator's low-level primitives (Reframe 2).

---

## Summary Table

| Claim | Verdict | Key Evidence |
|-------|---------|--------------|
| 1. Asset loading blocks first frame | **REJECTED** | Files present; game reaches real_init + AllocateDirectMemory; stall is in semaphore code, not file I/O |
| 2. ThreadPool is working | **REJECTED** | 0 INT3 hits on work submission; 5.3M SignalSema on wrong handles; 0x5C never signaled; WaitSema(0xA6) blocks |
| 3. Callback registration is broken | **PARTIAL** (registration works, invocation broken) | Registration: r14/r12 valid after EXP-103 tracer fix; callback stored at 0x808B54898[+0x10]. Invocation: 0 INT3 hits on 0x804FA1FE0, 0x804F88AD0, 0x804FA84E0, 0x804FC3720 |
| 4. PLT218 is the missing link | **REJECTED** | All 3 addresses have 0 runtime hits |
| 5. 466/466 imports resolve | **PARTIAL** | Resolver runs; ≥1 NID unresolved (J3edELK4FvM) but doesn't block; exact count unconfirmed from this session's filesystem |

**Next direction:** Reframe 2 (sync primitive correctness test) + Reframe 3 (consolidated summary to maintainers), in parallel. NOT EXP-113 as originally proposed.
