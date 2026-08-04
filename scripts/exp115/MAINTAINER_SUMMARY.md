# SharpEmu Yatzi Bring-up — Consolidated Summary for Maintainers

**Game:** Yatzi (PPSA17697) — PS5 Unity 2022.3.5f1 / IL2CPP
**Repo:** https://github.com/Sh-TB/sharpemuT24
**Branch:** master
**Status after 117 EXPs:** Boot reaches IL2CPP init + GPU memory allocation, then stalls. No first frame.
**GitHub Issue:** #1 (open)

---

## ⚠️ UPDATE (EXP-117, 2026-08-03) — Asset verification completed

A previous checkpoint (2026-07-24) identified a "missing shader" abort at `rip=0x800B28A0D` caused by an empty `Media/Resources/unity_builtin_extra` file. **EXP-117 verified that the real `unity_builtin_extra` file IS now available** in `/home/z/my-project/upload/unity_builtin_extra` (820,024 bytes, Unity 2022.3.5f1 — exact version match). The "missing shader" theory was true at the time of the 2026-07-24 checkpoint but the file has since been obtained.

**This means:**
1. The "missing shader" abort may be resolvable by placing the real file in `Media/Resources/` — this is the cheapest next test
2. The callback-dispatch investigation's relevance is NOT invalidated by the missing-shader theory — they are separate issues
3. A fresh trace with the real file properly placed is required to determine whether the missing-shader abort is still the blocker, or whether the callback-dispatch issue is the real blocker (or both, or neither)

**The cheapest next test (before the FAST_PATH=0 trace below):** Reconstruct `/tmp/games/yatzi/Media/Resources/` with the real `unity_builtin_extra` (820KB) and `unity default resources` (859KB) files from `/home/z/my-project/upload/`, then run with `SHARPEMU_PIPELINE_COUNTERS=1` to check if the abort at `rip=0x800B28A0D` is gone.

**Additional correction from CHECKPOINT_v0.0.11.md section 14-15:** The prior EXP-078 conclusion "workers signal wrong handles" was WRONG. The odd/even handle pattern is Unity's normal paired-semaphore design (wait on EVEN, signal on ODD = handle+1). The actual deadlock is at handles 0x81-0x8D (Job.worker 0-12), and those workers are NOT deadlocked — they are IDLE, correctly waiting for the main thread to dispatch C# Job System work. The main thread is in a busy loop (calling `1D0H2KNjshE`, `hsi9drzHR2k`, `scePthreadMutexLock`, `sceKernelClockGettime`, `sceAudioOutOutput`), NOT in a semaphore wait.

---

## TL;DR

After 117 experiments, we have a comprehensive **negative-space map** (what the bug is NOT) and a clear **structural finding** (what's missing), but we have not identified the **specific missing HLE behavior**. The investigation has narrowed the search to a single question that the maintainers of the semaphore/threading HLE layer are best positioned to answer.

---

## What we've ruled out (negative-space map)

| Hypothesis | EXP(s) | Verdict | Evidence |
|------------|--------|---------|----------|
| Asset loading blocks first frame | 113 | REJECTED | Files present; game reaches real_init + AllocateDirectMemory; stall is in semaphore code, not file I/O |
| GPU init missing | 076, 077 | REJECTED | Main thread reaches `sceKernelAllocateDirectMemory` (GPU memory allocated); stall is downstream in semaphore spin |
| Hash table not populated | 040, 094 | REJECTED (red herring) | `il2cpp_class_get_method_from_name` reads `[0x808923D88]`, NOT the hash table at `0x801EF7610` we investigated |
| PLT218 is the missing link | 107 | REJECTED | All 3 addresses (`0x804F88AD0`, `0x804FA84E0`, `0x804FC3720`) have 0 runtime hits |
| Callback registration broken | 098-105 | REJECTED | Registration reaches completion; callback pointer stored correctly at `0x808B54898[+0x10]`; r14/r12 valid after EXP-103 tracer-offset fix |
| Once-init fails | 099 | REJECTED | `0x804FC33B0` returns `eax=0` (SUCCESS) |
| Unresolved NID blocks | 100 | REJECTED | NID `J3edELK4FvM` unresolved but code checks `cmp eax, 0x80020003` and continues |
| PLT stubs in registration return failure | 101 | REJECTED | `0x804FC33C0/D0/E0` all return `eax=0` |
| Wrong indirect-dispatch offset (`[reg+0x10]`) | 111 | REJECTED | 216 indirect-disp8 sites in PRX, 0 in known reachable cluster; the actual pattern is `mov r12, [rbx+8]; call r12` (not `+0x10`) |
| `mov r12,[rbx+8]; call r12` dispatch pattern missing | 111 | REJECTED (exists but unreachable) | Pattern exists in `0x804FA1FE0` (the registered callback), but that function is never invoked |
| real_init has a wrong-return HLE stub | 112 | REJECTED | real_init has 0 direct HLE/PLT calls; all 164 calls are to PRX-internal functions |
| real_init's gate-protected setup (#152) is skipped | 112 | REJECTED | Gate is BSS-zero-initialized; #152 runs on first call; gate is set to 1 only by #152 itself (the other writer is dead code with 0 callers) |
| `lock cmpxchg` / `lock xadd` emulation bug | 114 | REJECTED (correct by construction) | SharpEmu uses direct execution; guest atomics run natively on host CPU; no emulator-side handler exists to be buggy |
| Semaphore HLE opcode-level bug | 114 | PARTIALLY REJECTED | Source code looks correct (atomic acquire in WakePredicate, proper pulse on signal, spurious-wake handling); but prior runtime data was collected under FAST_PATH=1 bypass, making it unreliable |
| Odd/even handle split is a SharpEmu bug | 114 | REJECTED | Handle allocation is purely sequential (2, 3, 4, 5, ...); odd/even pattern is the game's own usage order, not a SharpEmu property |

---

## What we've confirmed (positive findings)

### Setup half of the dispatch subsystem WORKS

- **Registration chain runs to completion:** `real_init` → `0x804F527C0` → `0x804FA20E0` → `0x804F889D0` → `0x804FC33B0` (once-init, returns SUCCESS) → `xchg [r14], rax` stores the callback pointer
- **Callback structure correctly populated:** At global `0x808B54898`, `[+0x10] = 0x804FA1FE0` (the registered callback function pointer)
- **Dispatch subsystem setup function runs:** real_init's call #152 (`0x804F3DF90`) is gate-protected lazy-init; gate is BSS-zero; first real_init call runs #152; #152 allocates structures and calls `0x804FC2C80` (the same target the registered callback uses)
- **Workers are created:** 13 `AssetGarbageCollectorHelper` threads (trace lines 8550-8631)
- **144 semaphores created:** All named `Baselib_SystemSemaphore`, handles 0x02-0x91

### Trigger half of the dispatch subsystem NEVER FIRES

- **Registered callback `0x804FA1FE0` is never invoked:** 0 INT3 hits, 0 direct callers
- **Callback invoker `0x804F88AD0` is never reached:** 0 INT3 hits, 0 callers, 0 LEA references
- **Work submission `0x804F6EC20` is never reached:** 0 INT3 hits across all 3 call sites
- **No indirect-dispatch site in any reachable code path invokes the callback:** 216 candidate sites scanned across the 45.6 MB PRX, 0 fall inside the known reachable cluster

---

## The specific question for maintainers

**Under `SHARPEMU_SEMA_FAST_PATH=0` (clean run, no bypass), what HLE primitive should fire to invoke a registered IL2CPP callback that the runtime is expected to dispatch?**

### Context for the question

The registered callback `0x804FA1FE0` lives in `Il2cppUserAssemblies.prx`. It is registered correctly (pointer stored at `0x808B54898[+0x10]`). The callback's body uses `mov r12, [rbx+8]; …; call r12` to dispatch to a function pointer at offset 8 of a struct — this is the actual dispatch mechanism.

But **nothing ever invokes `0x804FA1FE0`**. Static analysis across 45.6 MB of PRX code found no caller. Runtime tracing across many EXPs found 0 INT3 hits.

The trigger must come from outside the PRX — likely from one of:

1. **A timer/event HLE primitive** that the runtime registers during init and that should fire periodically (or on a specific event) to dispatch pending callbacks
2. **A thread-pool work-item HLE primitive** that should pick up queued work and invoke the registered callback
3. **An IO-completion HLE primitive** that should fire when an async operation completes
4. **A cooperative-scheduler pump** that should run ready threads which then invoke the callback

### What we've checked in the semaphore/threading HLE

- `sceKernelCreateSema` / `sceKernelWaitSema` / `sceKernelSignalSema` / `sceKernelPollSema` / `sceKernelCancelSema` / `sceKernelDeleteSema` — all implemented in `KernelSemaphoreCompatExports.cs`; source looks correct in non-bypass paths
- `sem_init` / `sem_wait` / `sem_trywait` / `sem_post` / `sem_destroy` / `sem_timedwait` — POSIX semaphore wrappers, all implemented
- `pthread_create` — implemented; `Pump(creatorContext, "pthread_create")` runs to start new threads
- Cooperative scheduler: `Pump()` and `WakeBlockedDirectories()` are implemented; `WaitSema` calls `Pump()` before blocking

### What we have NOT checked (and would appreciate maintainer input on)

- **Is there a timer/event HLE primitive that should fire to dispatch pending IL2CPP callbacks?** (e.g., `sceKernelSetEventFlag`, `sceKernelCreateTimer`, `sceKernelWaitEventFlag` with a timer source)
- **Is there a thread-pool work-item HLE primitive that should pick up queued work?** (e.g., a Unity job system, a `sceKernelReadEvent` that should complete)
- **Is there an IO-completion HLE primitive that should fire when async file IO completes?** (The game does load `global-metadata.dat`; maybe an async read completion should trigger something?)
- **Is the cooperative scheduler's `Pump()` correctly giving all ready threads a chance to run?** Under `SHARPEMU_SEMA_FAST_PATH=1`, `Pump()` is called from `WaitSema` before the bypass returns — but the bypass means no real waiting happens, so `Pump()` may not be invoked at the right times.

---

## ⚠️ CRITICAL LIMITATION — Read Before Interpreting EXP-072..078 and EXP-096..115

**Nearly all prior semaphore runtime observations (EXP-072..078, which shaped the framing of EXP-096..115) were collected under `SHARPEMU_SEMA_FAST_PATH=1` + an 11-byte NOP gate.** Both bypasses change semaphore semantics in ways that would make downstream observations look like bugs when they are actually the bypass working as documented.

### What the bypasses do

- `SHARPEMU_SEMA_FAST_PATH=1` (line 108 of `KernelSemaphoreCompatExports.cs`): makes `WaitSema` return OK immediately **without decrementing count, blocking, or registering a waiter**
- `SignalSema` has NO such bypass — it always increments the count
- The 11-byte NOP gate was an experimental patch that enabled workers to reach `SignalSema` (otherwise they couldn't)

### What this means for the data

- The "5.3M SignalSema calls" observed in EXP-078 all incremented counts (signal works normally)
- Every `WaitSema` returned OK without decrementing → counts grew unboundedly (e.g., handle 0x73 went from 1 to 447,579)
- EXP-078's "Semaphore count keeps incrementing" is **exactly what `FAST_PATH=1` produces** — not a bug, but the documented behavior of the bypass
- The "workers signal wrong handles" observation is an artifact: workers signal whatever handle the game's code tells them to signal (`[rbx+0xB0]`), which happens to be odd because of allocation order, not because of any SharpEmu odd/even bifurcation (handle allocation is purely sequential: 2, 3, 4, 5, …)
- Handle `0x5C` was "never signaled" — but under `FAST_PATH=1`, no real blocking happens, so this observation cannot distinguish "the signal is genuinely missing" from "the signal would fire under real blocking semantics"

### The honest state of the investigation

**We do not yet know if the callback-dispatch / WaitSema deadlock even reproduces the same way under clean `FAST_PATH=0` conditions.** This affects how much weight the entire EXP-096..115 callback-dispatch chain should carry. Some of the "confirmed" observations feeding the later investigation may have been shaped by contaminated data.

### What we could not do

**Run a clean `FAST_PATH=0` trace.** The prior tracer infrastructure (the `_Exp*.cs` files from EXP-095..109) and the SharpEmu binary built with those tracers are not directly accessible in this session's filesystem. The runtime log at `/home/z/my-project/logs/devlog/app/debug.log` is empty (0 bytes). Re-running with `FAST_PATH=0` requires rebuilding SharpEmu with the tracers re-integrated — which is the natural next experiment, but we could not complete it in this session.

### What this means for the maintainer question above

The question "what HLE primitive should fire to invoke a registered IL2CPP callback" is **the right question to ask under `FAST_PATH=0`** — but it's possible that under `FAST_PATH=0`, the deadlock manifests differently (a different handle blocks, or the callback IS invoked, or the game progresses further). **If maintainers can run a clean `FAST_PATH=0` trace, that would be the single most valuable next data point.**

If that's not possible, the negative-space map and structural finding above still hold (registration works, dispatch mechanism exists in dead code, atomics are correct by construction, handle allocation is sequential), and the open question is worth outside input on.

---

## Important caveat about prior runtime data (additional notes)

- `WaitSema` returned OK immediately without waiting or decrementing count
- `SignalSema` worked normally (incremented count)
- Counts grew unboundedly (e.g., handle 0x73 went from 1 to 447,579)
- The "workers signal wrong handles" observation is an artifact of the bypass, not a real SharpEmu bug

**Any re-investigation of the semaphore layer should be done under `SHARPEMU_SEMA_FAST_PATH=0`** to get reliable data. We could not do this in our latest session because the tracer infrastructure from prior EXPs was not directly accessible.

---

## Reproduction

**Game files:** `/tmp/games/yatzi/` (eboot.bin, Il2cppUserAssemblies.prx, global-metadata.dat, Media/, etc.)
**PRX runtime base (in SharpEmu):** `0x804CD5000`
**Key addresses:**
- `real_init`: `0x804F04BA0`
- Registered callback (never invoked): `0x804FA1FE0`
- Callback structure global: `0x808B54898` (`[+0x10] = 0x804FA1FE0`)
- Work submission (never reached): `0x804F6EC20`
- Dispatch subsystem setup (runs): `0x804F3DF90` (real_init call #152)
- Gate global: `0x808B543A0` (BSS-zero; set to 1 by #152 on first run)

**Configuration that reaches the stall:** `SHARPEMU_SEMA_FAST_PATH=1` (without this, the game blocks earlier on `sceKernelWaitSema`)

**Stall location:** Main thread blocks on `WaitSema` in PRX code after `sceKernelAllocateDirectMemory`. Under FAST_PATH=1, this manifests as a tight spin (WaitSema returns immediately, game loops). Under FAST_PATH=0, this would be a permanent block.

---

## Full EXP history

114 EXPs documented in `/home/z/my-project/worklog.md` (2700+ lines). Key milestones:
- EXP-026-027: Synthetic CPU fuzzing against Unicorn (10/10, 768/768 instruction tests pass)
- EXP-035-040: IL2CPP init order investigation, hash table red herring
- EXP-050-065: Metadata struct verification against real Unity 2022.3.5f1 headers
- EXP-072-078: Worker thread / semaphore analysis (under FAST_PATH=1 — data unreliable)
- EXP-092-105: Callback registration chain verification (registration confirmed working)
- EXP-106-111: Callback invocation search (no invocation mechanism found in any reachable code)
- EXP-112: real_init 164-call audit (0 HLE calls; setup function #152 runs correctly)
- EXP-113: External claim validation + trajectory reassessment
- EXP-114: Synchronization layer validation (atomic ops correct by construction; semaphore HLE source correct; prior data unreliable due to FAST_PATH bypass)

---

## What we're asking for

1. **Review the question in "The specific question for maintainers"** — is there an HLE primitive we missed that should fire to dispatch pending IL2CPP callbacks?
2. **If possible, run the game under `SHARPEMU_SEMA_FAST_PATH=0`** with semaphore tracing enabled, and share what happens when `WaitSema` actually blocks. We believe this will reveal whether the trigger fires under normal semantics (and is just masked by FAST_PATH) or whether it's genuinely missing.
3. **If the trigger is genuinely missing**, guidance on what HLE primitive should be implemented to fire it.

We've spent 114 EXPs narrowing from the symptom (no first frame) down through IL2CPP init, registration, dispatch setup, and sync primitives. The negative-space map is comprehensive. The positive answer — "here is the one specific missing HLE behavior" — is what we're asking your help to identify.

---

*Prepared 2026-08-03. Full worklog and EXP reports in the SharpEmuT24 repository under `/home/z/my-project/worklog.md` and `/home/z/my-project/scripts/exp*/`.*
