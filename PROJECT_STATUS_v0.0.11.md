# SharpEmuT24 — Project Status v0.0.11

**Release date:** 2026-08-04
**Tag:** `v0.0.11`
**Release title:** v0.0.11 — Complete EXP-000..135 Investigation Archive + Runtime Debug Milestone

## Purpose of this release

This is a **knowledge-preservation release**. It does NOT claim:
- full game execution
- first rendered frame
- Yatzi completion
- final emulator compatibility

It DOES preserve:
- Every EXP report from EXP-026 → EXP-135 that has a surviving artifact (69 standalone `.md` reports + worklog narrative for the rest)
- Every analysis script (`scripts/expNNN/` directories + loose `expNNN_*.py` files)
- Every runtime log captured during experiments (`exp118_run.log`, `exp119_testA.log`, `exp119_testB.log`)
- Three historical project-status snapshots (v0.0.9, v0.0.10, and this v0.0.11)
- The 3,451-line `worklog.md` continuous investigation narrative

See `docs/EXP_INDEX.md` for the complete experiment index including missing numbers.

## Game under test

**Yatzi (PPSA17697)** — PS5 Unity 2022.3.5f1 / IL2CPP build.

## Current emulator status

### Working
- SharpEmuT24's direct execution backend (guest x86_64 runs natively on host CPU via `VirtualAlloc PAGE_EXECUTE_READWRITE`). Atomic operations are correct by construction.
- SELF/ELF loader (eboot + 8 PRX modules load successfully).
- RELA relocation processing: `R_X86_64_RELATIVE` (type 8) confirmed working — 50,450 relocations applied at runtime from guest memory at `0x801F435F0` (EXP-132).
- IL2CPP metadata hash-table resolver (Red-Black Tree, strcmp intrinsic) — confirmed correct (EXP-026 FINAL).
- Unity IL2CPP boot path through `real_init` entry — main thread reaches worker-creation phase.
- Worker thread creation: 14 `AssetGarbageCollectorHelper` worker threads + 1 IL2CPP GC scavenger thread spawn successfully.
- Semaphore HLE (`sceKernelCreateSema` / `WaitSema` / `SignalSema`): primitive honors guest-requested `init` count correctly (EXP-135). No HLE bug in the primitive itself.

### Broken / blocked
- **Game boot stalls in WaitSema(0x81) deadlock.** Main thread blocks at `0x804F6E9E6` waiting on semaphore `0x81` (named `Baselib_SystemSemaphore`, created with `init=0, max=2147483647`).
- All 14 worker threads block on their per-worker work semaphores (`0x5C`–`0x74`, all EVEN handles).
- GC scavenger thread blocks on `0x83` (SuspendSemaphore).
- System-wide deadlock. No frame is ever rendered.

### Root cause (current hypothesis, ~80% confidence)
**The bootstrap job that should signal semaphore 0x81 is never submitted by `real_init`.**

Evidence:
- 458 of 459 `SignalSema` call sites in eboot are never reached at runtime (EXP-134, RIP coverage analysis).
- The 1 `SignalSema` call site that IS reached is the dispatch loop's own post-decrement signal (i.e. workers completing old work, not new work being submitted).
- The dispatch loop at `0x804F6E880` is reached via a direct CALL from `real_init` (call site `0x804F4560E`), NOT via a corrupted function pointer (EXP-134).
- The producer candidate at `0x801028d80` (performs the exact `[rbx+0x90]++` + `[rbx+0x88]=...` + `SignalSema` pattern) is statically unreachable code: zero direct callers, zero LEA references, zero reads from its relocation slot (EXP-133).
- `real_init` itself blocks DURING its execution, never returns (EXP-128). The dispatch loop is called from within `real_init`, not after it.

## Golden Test status

No Golden Test exists yet. The closest candidate (`scripts/exp028/golden_test_runner.py`) was developed in EXP-028 to compare SharpEmu's CPU emulation against Unicorn as a gold standard, but it has not been wired into a CI gate.

## Known blockers (in priority order)

1. **Bootstrap job not submitted.** The producer that should signal semaphore `0x81` is never invoked. This is the immediate deadlock cause.
2. **No GPU/VideoOut reached.** Pipeline counters remain zero in all runs. No `sceVideoOutFlip`, no `sceAgc` calls. (Consequence of blocker #1 — game never reaches the render loop.)
3. **No dotnet SDK in the sandbox.** SharpEmu cannot be rebuilt for runtime instrumentation. All recent EXPs (EXP-126 onwards) are static analysis + log inspection only.
4. **`SHARPEMU_SEMA_FAST_PATH=1` is a trap.** Setting it bypasses WaitSema (returns OK immediately without decrementing count or blocking), which masks the real producer-side failure. All semaphore data collected under FAST_PATH=1 (EXP-072..EXP-078) is contaminated and was re-baselined from EXP-118 onwards.

## Rejected paths (do NOT re-test)

These hypotheses have been tested and rejected with concrete evidence:

| Hypothesis | Rejected by | Evidence |
|------------|-------------|----------|
| Vblank / event-flag driven dispatch | EXP-126 | No `sceVideoOutAddVblankEvent`, no `sceKernelWaitEventFlag` in either eboot or PRX modules |
| RELA relocation failure | EXP-131 → EXP-132 | Runtime log: "loaded from guest memory at 0x801F435F0", 50,450 relocations processed |
| Producer at 0x801028d80 is the real producer | EXP-133 | Zero direct callers, zero LEA references, zero runtime reads from 0x801cfccb0 |
| Dispatch loop reached via corrupted function pointer | EXP-134 | Direct CALL instruction at 0x804F4560E → 0x804F6E880 |
| HLE semaphore ignores guest `init` count | EXP-135 | HLE reads `init` from guest registers correctly; semaphore 0x81 created with `init=0` (expected for producer-consumer) |
| `SHARPEMU_SEMA_FAST_PATH=1` is a fix (not a bypass) | EXP-119 | FAST_PATH=1 crashes at RIP=0 (NULL call into address 0); pipeline counters still zero |
| Extra IL2CPP thread is a job dispatcher | EXP-123 | It's the GC scavenger thread; semaphore 0x83 is SuspendSemaphore |
| IL2CPP worker task function pointer is uninitialized by mistake | EXP-121 | `[rbx+0xF8]` is deliberately zeroed at worker creation (0x800a9fcae); `[rbx+0x108]` dependency flag set to 1 |

## Active hypotheses (queued for EXP-136+, do NOT require user permission to start)

Per the new investigation protocol (run primary + 2-3 alternatives in parallel, do not loop on user messages), the next batch of experiments should test:

### Primary hypothesis — HLE `SubmitJob` / `JobHandle_Schedule` is a no-op or `NotImplemented`
- **Test:** Audit every HLE export in `SharpEmu.Libs/` whose name matches `*Job*`, `*Schedule*`, `*Dispatch*`, `*Submit*`, `*Baselib*`, `*SystemSemaphore*`. List their bodies. If any returns 0 or throws `NotImplementedException`, that is the host-side root cause.
- **Predicted file:** `src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs` (already inspected in EXP-135 for `CreateSema` — needs full audit for `WaitSema` and any `Submit*` exports).

### Alternative hypothesis A — Bootstrap call site gated by a branch that never evaluates true
- **Test:** Disassemble `real_init` (function at PRX base + offset). Find the direct CALL to the dispatch loop. Check the conditional branch immediately preceding it. Determine the condition. Check whether the condition's inputs are ever set to a value that would allow the branch to be taken.
- **Predicted file:** `Il2cppUserAssemblies.prx` disassembly around `0x804F4560E`.

### Alternative hypothesis B — Argument-ordering mismatch in `sceKernelCreateSema` HLE
- **Test:** Compare the PS5 kernel `sceKernelCreateSema` signature (parameter order: `name`, `attr`, `init`, `max`, `opt`) against SharpEmu's HLE handler. If parameters are read in the wrong order, `init` could be silently zero even when the guest passes a non-zero value.
- **Predicted file:** `src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs`.

### Contradiction check — `WaitSema` consuming a count before `SignalSema` fires
- **Test:** In `WaitSema` HLE, verify the wait/decrement ordering. If `WaitSema` decrements count BEFORE checking the wait queue, it could starve producers in tight interleavings.

## Project knowledge structure

```
sharpemuT24/
├── worklog.md                            # 3,451-line continuous investigation log
├── CHECKPOINT_v0.0.11.md                 # Project checkpoint snapshot
├── PROJECT_STATUS_v0.0.9.md              # Earlier status
├── PROJECT_STATUS_v0.0.10.md             # Earlier status (Windows-log comparison)
├── PROJECT_STATUS_v0.0.11.md             # This file
├── docs/
│   └── EXP_INDEX.md                      # Complete experiment index (EXP-000..135)
├── exp-reports/                          # 69 standalone .md reports (EXP-035..EXP-135)
│   ├── EXP-035.md
│   ├── ...
│   └── EXP-135.md
├── scripts/                              # All analysis scripts + runtime logs
│   ├── exp026/  ...  exp135/             # Per-EXP directories
│   ├── exp079_loose/  exp081_loose/      # Loose .py scripts for EXPs without .md
│   ├── exp093_loose/  exp094_loose/
│   ├── exp097_loose/  exp098_loose/
│   ├── exp118_run.log                   # 786 KB runtime log
│   ├── exp119_testA.log                 # 810 KB (FAST_PATH=0 run)
│   ├── exp119_testB.log                 # 953 KB (FAST_PATH=1 run)
│   ├── resume_investigation_checklist.md # Resume-from-scratch checklist
│   └── *.py                              # Root-level analysis utilities
└── work/sharpemuT24/                     # SharpEmu source tree (already in repo)
```

## How to continue this investigation on a fresh machine

1. `git clone https://github.com/Sh-TB/sharpemuT24.git`
2. Read this file (`PROJECT_STATUS_v0.0.11.md`) end-to-end.
3. Read `docs/EXP_INDEX.md` to find experiments relevant to your hypothesis.
4. Read `worklog.md` lines ~2576–3451 (the EXP-111..EXP-135 narrative) for full context.
5. Read the specific `exp-reports/EXP-NNN.md` files for the experiments you want to extend.
6. Check `scripts/resume_investigation_checklist.md` for environment setup steps.
7. Pick up from the **Active hypotheses** section above. Do NOT re-test rejected paths.

## Git history rules going forward

- Every EXP commit message MUST follow the pattern `EXP-NNN: <one-line conclusion>`.
- Bulk backfills use `docs(exp): backfill EXP-XXX..EXP-YYY — <reason>`.
- Release commits use `vX.Y.Z: <release title>`.
- Random UUID commit messages are FORBIDDEN.
- Every new EXP report MUST be committed and pushed to GitHub BEFORE the next EXP starts. No exceptions.
