# EXP Investigation Index — SharpEmuT24 / Yatzi (PPSA17697)

**Scope:** Full archive of all investigation experiments from EXP-000 through EXP-135.
**Date range:** 2026-07-24 → 2026-08-04
**Total experiments performed:** ~80 (some numbers were skipped or consolidated)
**Reports preserved as `.md`:** 69 files
**Reports embedded in worklog only:** ~14 (EXP-079..EXP-110 range, see below)
**Reports never created (pre-history or skipped):** ~36

## Legend

| Status | Meaning |
|--------|---------|
| `REPORT` | Standalone markdown report exists in `exp-reports/` and/or `scripts/expNNN/` |
| `WORKLOG` | Performed but only documented inside `worklog.md` (no standalone .md) |
| `SCRIPTS` | No .md report; only loose analysis scripts (e.g. `exp079_*.py`) survive |
| `MISSING` | Number was either skipped, never performed, or no artifacts survive |
| `N/A` | Pre-history number before this project's investigation started (EXP-000..EXP-034) |

## EXP-000..EXP-034 — Pre-history (not part of this project)

| EXP | Status | Notes |
|-----|--------|-------|
| EXP-000..EXP-025 | N/A | Before this project's tracking began. Predates the Yatzi-bringup investigation arc. Any artifacts would be in the original SharpEmu upstream history. |
| EXP-026 | REPORT | SharpEmu IL2CPP metadata hash-table resolver — Red-Black Tree confirmed, strcmp works, native resolver returns 0 (root cause unknown at the time). Already on `main` history from 2026-07-28. |
| EXP-027 | SCRIPTS | `scripts/exp027/` — Unicorn-as-gold-standard methodology for CPU emulation validation. Reused in EXP-114. |
| EXP-028 | SCRIPTS | `scripts/exp028/` — User-approved ordered investigation. EXP-026 closed. First-divergence trace. |

## EXP-035..EXP-078 — IL2CPP / Unity bring-up arc

All experiments in this range have full standalone reports (in `exp-reports/`) and supporting scripts (in `scripts/expNNN/`).

| EXP | Status | Title (short) | Files |
|-----|--------|---------------|-------|
| EXP-035 | REPORT | IL2CPP Runtime Dependency Trace & Fix Plan | `exp-reports/EXP-035.md`, `scripts/exp035/` |
| EXP-036 | REPORT | IL2CPP Initialization Order & Threading | `exp-reports/EXP-036.md`, `scripts/exp036/` |
| EXP-037 | REPORT | IL2CPP Global State Initialization | `exp-reports/EXP-037.md`, `scripts/exp037/` |
| EXP-038 | REPORT | sce_dynamic / RELA analysis & crash function | `exp-reports/EXP-038.md`, `scripts/exp038/` |
| EXP-039 | REPORT | Hash table lookup tracer (4 variants) | `exp-reports/EXP-039.md`, `scripts/exp039/` |
| EXP-040 | REPORT | Real init tracer | `exp-reports/EXP-040.md`, `scripts/exp040/` |
| EXP-041 | REPORT | Call #7 disasm & hash call tracer | `exp-reports/EXP-041.md`, `scripts/exp041/` |
| EXP-042 | REPORT | Metadata lookup tracer & callback chain | `exp-reports/EXP-042.md`, `scripts/exp042/` |
| EXP-043 | REPORT | Exhaustive write search / relocation analysis | `exp-reports/EXP-043.md`, `scripts/exp043/` |
| EXP-044 | REPORT | FiniArray tracer / INT3 origin verify | `exp-reports/EXP-044.md`, `scripts/exp044/` |
| EXP-045 | REPORT | eboot fini & first path check | `exp-reports/EXP-045.md`, `scripts/exp045/` |
| EXP-046 | REPORT | List dump tracer | `exp-reports/EXP-046.md`, `scripts/exp046/` |
| EXP-047 | REPORT | (small) | `exp-reports/EXP-047.md` |
| EXP-048 | REPORT | (small) | `exp-reports/EXP-048.md` |
| EXP-049 | REPORT | Crash function disasm | `exp-reports/EXP-049.md`, `scripts/exp049/` |
| EXP-050 | REPORT | Metadata list writes | `exp-reports/EXP-050.md`, `scripts/exp050/` |
| EXP-051 | REPORT | Jump bytes analysis | `exp-reports/EXP-051.md`, `scripts/exp051/` |
| EXP-052 | REPORT | Real IL2CPP/PS5 Metadata Initialization | `exp-reports/EXP-052.md`, `scripts/exp052/` |
| EXP-053 | REPORT | Runtime tracer for IL2CPP metadata registration walker | `exp-reports/EXP-053.md`, `scripts/exp053/` |
| EXP-054 | REPORT | BOOT_STAGE_5 Master Investigation | `exp-reports/EXP-054.md`, `scripts/exp054/` |
| EXP-055 | REPORT | Find IL2CPP registration entry point | `exp-reports/EXP-055.md`, `scripts/exp055/` |
| EXP-056 | REPORT | IL2CPP Registration Chain Investigation | `exp-reports/EXP-056.md`, `scripts/exp056/` |
| EXP-057 | REPORT | Find and invoke the consumer function | `exp-reports/EXP-057.md`, `scripts/exp057/` |
| EXP-058 | REPORT | Runtime trace call #7 consumer candidate | `exp-reports/EXP-058.md`, `scripts/exp058/` |
| EXP-059 | REPORT | Ground-truth comparison with real Unity IL2CPP | `exp-reports/EXP-059.md`, `scripts/exp059/` |
| EXP-060 | REPORT | Complete dump verification + baseline boot test | `scripts/exp060/dump_verification_report.md` |
| EXP-061 | REPORT | Artifact Identity Audit (old vs new eboot) | `exp-reports/EXP-061.md`, `scripts/exp061/` |
| EXP-062 | REPORT | Semaphore stall quick checks (FAST_PATH / SignalSema) | `exp-reports/EXP-062.md`, `scripts/exp062/` |
| EXP-063 | REPORT | Semaphore stall investigation + FAST_PATH fix | `exp-reports/EXP-063.md`, `scripts/exp063/` |
| EXP-064 | REPORT | Trace NULL execute during Unity game manager loading | `exp-reports/EXP-064.md`, `scripts/exp064/` |
| EXP-065 | REPORT | Fix stack corruption in NULL execute recovery | `exp-reports/EXP-065.md`, `scripts/exp065/` |
| EXP-066 | REPORT | IL2CPP stub realism investigation | `exp-reports/EXP-066.md`, `scripts/exp065/` |
| EXP-067 | REPORT | IL2CPP import repatch + causal chain verification | `exp-reports/EXP-067.md`, `scripts/exp065/` |
| EXP-068 | REPORT | Unity worker task submission investigation | `exp-reports/EXP-068.md`, `scripts/exp065/` |
| EXP-069 | REPORT | Static search for SignalSema + semaphore | `exp-reports/EXP-069.md`, `scripts/exp065/` |
| EXP-070 | REPORT | Find specific conditional branch gating SignalSema | `exp-reports/EXP-070.md`, `scripts/exp065/` |
| EXP-071 | REPORT | Find what clears [rbx+0x108] to 0 | `exp-reports/EXP-071.md`, `scripts/exp065/` |
| EXP-072 | REPORT | Diagnostic gate clear test (NOP gate at 0x800AA0207) | `exp-reports/EXP-072.md`, `scripts/exp072/` |
| EXP-073 | REPORT | 11-byte NOP (incl. jmp) — SignalSema actually fires | `exp-reports/EXP-073.md`, `scripts/exp072/` |
| EXP-074 | REPORT | Check rendering progress after SignalSema fix | `exp-reports/EXP-074.md`, `scripts/exp072/` |
| EXP-075 | REPORT | Find real signal path for worker semaphore 0x5C | `exp-reports/EXP-075.md`, `scripts/exp072/` |
| EXP-076 | REPORT | Identify dependency object and completion producer | `exp-reports/EXP-076.md`, `scripts/exp072/` |
| EXP-077 | REPORT | Why Unity PRX task dispatch is not reached | `exp-reports/EXP-077.md`, `scripts/exp072/` |
| EXP-078 | REPORT | Semaphore handle distribution analysis (odd/even split) | `exp-reports/EXP-078.md`, `scripts/exp072/` |

## EXP-079..EXP-110 — Partially documented (worklog references only)

These experiments were performed but the standalone `.md` reports were not preserved at the time. Their findings survive in `worklog.md` and supporting scripts survive as loose `expNNN_*.py` files in `scripts/exp079_loose/`, `scripts/exp081_loose/`, `scripts/exp093_loose/`, `scripts/exp094_loose/`, `scripts/exp097_loose/`, `scripts/exp098_loose/`.

| EXP | Status | Notes |
|-----|--------|-------|
| EXP-079 | SCRIPTS | 30+ analysis scripts (`scripts/exp079_loose/`) for worker dispatch / PLT resolution / RELA scan. Findings in `worklog.md`. |
| EXP-080 | WORKLOG | Per EXP-114 task: "EXP-080 may have disproved parts of EXP-078." No standalone artifacts survive. |
| EXP-081 | SCRIPTS | Knowledge-base creation + F8-writer search (`scripts/exp081_loose/`). |
| EXP-082 | WORKLOG | Referenced obliquely. No standalone artifacts. |
| EXP-083 | WORKLOG | Referenced. No standalone artifacts. |
| EXP-084 | WORKLOG | Referenced. No standalone artifacts. |
| EXP-085 | WORKLOG | Build artifacts in `work/sharpemu-build-exp085/` (binaries not uploaded — too large). |
| EXP-086..EXP-088 | WORKLOG | Referenced. No standalone artifacts. |
| EXP-089 | WORKLOG | **Key conclusion:** "No work submitted, likely a GC trigger/timer/event/callback SharpEmu doesn't implement." Cited in EXP-113 trajectory check. |
| EXP-090..EXP-092 | WORKLOG | EXP-092 build artifacts in `work/sharpemu-build-exp092/`. |
| EXP-093 | SCRIPTS | Codegen register disasm (`scripts/exp093_loose/`). |
| EXP-094 | SCRIPTS | Impl disasm + writer search (`scripts/exp094_loose/`). |
| EXP-095 | WORKLOG | Build artifacts in `work/sharpemu-build-exp095/`. "Missing shader" theory. |
| EXP-096 | WORKLOG | Build artifacts in `work/sharpemu-build-exp096/`. Shader investigation. |
| EXP-097 | SCRIPTS | Indirect call / LEA / global search (`scripts/exp097_loose/`). Build artifacts in `work/sharpemu-build-exp097/`. |
| EXP-098 | SCRIPTS | Global writer search (`scripts/exp098_loose/`). Build artifacts in `work/sharpemu-build-exp098/`. |
| EXP-099 | WORKLOG | Build artifacts in `work/sharpemu-build-exp099/`. |
| EXP-100 | WORKLOG | Skipped / consolidated. |
| EXP-101..EXP-103 | WORKLOG | Build artifacts in `work/sharpemu-build-exp101/`, `-exp102/`, `-exp103/`. EXP-103 tracer fix confirmed r14/r12 valid. |
| EXP-104..EXP-106 | WORKLOG | EXP-106 identified registered-but-never-invoked callback 0x804FA1FE0. |
| EXP-107..EXP-109 | WORKLOG | Build artifacts in `work/sharpemu-build-exp107/`. Callback dispatch investigation continued. |
| EXP-110 | WORKLOG | Consolidation step. |

## EXP-111..EXP-135 — Modern phase (full reports + scripts)

All experiments in this range have full standalone reports in `exp-reports/`.

| EXP | Status | Title (short) | Files |
|-----|--------|---------------|-------|
| EXP-111 | REPORT | Filtered enumeration of `call [reg+0x08]` sites in Il2cppUserAssemblies.prx | `exp-reports/EXP-111.md`, `scripts/exp111/` |
| EXP-112 | REPORT | Filtered audit of real_init's 164 calls | `exp-reports/EXP-112.md`, `scripts/exp112/` |
| EXP-113 | REPORT | External developer claim validation + trajectory reassessment | `exp-reports/EXP-113.md`, `scripts/exp113/` |
| EXP-114 | REPORT | Synchronization layer validation (Reframe 2, Unicorn gold-standard) | `exp-reports/EXP-114.md`, `scripts/exp114/` |
| EXP-115 | REPORT | Consolidated maintainer summary "unsolved after 113 EXPs" | `scripts/exp115/MAINTAINER_SUMMARY.md` |
| EXP-116 | REPORT | Validate 6 external dev claims: GPU/flip/semaphore/Vulkan | `exp-reports/EXP-116.md`, `scripts/exp116/` |
| EXP-117 | REPORT | Asset verification + 7-claim reviewer validation | `exp-reports/EXP-117.md`, `scripts/exp117/` |
| EXP-118 | REPORT | Unity resource runtime validation (real unity_builtin_extra) | `exp-reports/EXP-118.md`, `scripts/exp118/` |
| EXP-119 | REPORT | FAST_PATH A/B test (FAST_PATH=0 stalls, FAST_PATH=1 NULL call) | `exp-reports/EXP-119.md`, `scripts/exp119/`, `scripts/exp119_testA.log`, `scripts/exp119_testB.log` |
| EXP-120 | REPORT | NULL call at 0x800AA01CE (call [rbx+0xF8] with [rbx+0xF8]=NULL) | `exp-reports/EXP-120.md`, `scripts/exp120/` |
| EXP-121 | REPORT | [rbx+0xF8] intentionally 0 at creation (0x800a9fcae) | `exp-reports/EXP-121.md`, `scripts/exp121/` |
| EXP-122 | REPORT | SignalSema fires 13/12 on ODD, ZERO on EVEN — dispatch missing | `exp-reports/EXP-122.md`, `scripts/exp122/` |
| EXP-123 | REPORT | IL2CPP thread 0x804F88AA0 is GC scavenger; 0x83 is SuspendSemaphore | `exp-reports/EXP-123.md`, `scripts/exp123/` |
| EXP-124 | REPORT | **BREAKTHROUGH:** main thread blocks on WaitSema(0x81) at 0x804F6E9E6 | `exp-reports/EXP-124.md`, `scripts/exp124/` |
| EXP-125 | REPORT | ZERO lock xadd/inc/add [reg+0x90] in all 8 PRX modules | `exp-reports/EXP-125.md`, `scripts/exp125/` |
| EXP-126 | REPORT | Vblank/event hypothesis REJECTED | `exp-reports/EXP-126.md`, `scripts/exp126/` |
| EXP-127 | REPORT | HLE correct; 459 SignalSema callers unreachable — bootstrap not submitted (~70% conf.) | `exp-reports/EXP-127.md`, `scripts/exp127/` |
| EXP-128 | REPORT | Main thread blocks DURING real_init — never returns | `exp-reports/EXP-128.md`, `scripts/exp128/` |
| EXP-129 | REPORT | Producer candidate 0x801028d80 writes [rbx+0x90]+[rbx+0x88]+SignalSema, 0 callers | `exp-reports/EXP-129.md`, `scripts/exp129/` |
| EXP-130 | REPORT | RELA entry at r_offset=0x1cfccb0 has r_addend=0x1028d80 (CORRECTED in EXP-132) | `exp-reports/EXP-130.md`, `scripts/exp130/` |
| EXP-131 | REPORT | Hypothesized TryLoadTableBytes failure for [---] segment (REJECTED by EXP-132) | `exp-reports/EXP-131.md`, `scripts/exp131/` |
| EXP-132 | REPORT | **CORRECTION:** RELA table loaded successfully (50,450 relocations); EXP-131 REJECTED | `exp-reports/EXP-132.md`, `scripts/exp132/` |
| EXP-133 | REPORT | Producer 0x801028d80 is UNREACHABLE (zero reads, zero callers, zero LEA) | `exp-reports/EXP-133.md`, `scripts/exp133/` |
| EXP-134 | REPORT | 458/459 SignalSema callers never executed (RIP coverage) | `exp-reports/EXP-134.md`, `scripts/exp134/` |
| EXP-135 | REPORT | Semaphore 0x81 created with init=0 (correct); HLE honors guest init count — no HLE bug | `exp-reports/EXP-135.md`, `scripts/exp135/` |

## Investigation Status Summary

**Current root-cause hypothesis (as of EXP-135):**
The deadlock is NOT in the HLE semaphore primitive (EXP-135 confirmed HLE honors `init=0` correctly). The deadlock is caused by a missing producer: the bootstrap job that should signal semaphore 0x81 (and through it, the worker dispatch loop) is never submitted by `real_init`. 458 of 459 `SignalSema` call sites in eboot are never reached at runtime (EXP-134). The dispatch loop itself is invoked via a direct CALL (not a corrupted pointer), so the failure is upstream of the dispatch loop.

**Strongest next-step hypotheses (queued, not yet tested):**
1. An HLE export that should implement `SubmitJob` / `JobHandle_Schedule` returns 0 or `NotImplemented`.
2. The Unity bootstrap function is called via a direct call inside `real_init`, but the call site is gated by a branch that never evaluates true.
3. Argument-ordering or signature mismatch in `sceKernelCreateSema` HLE causes `WaitSema` to consume a count that was never `SignalSema`'d.

**Rejected paths (do not re-test):**
- Vblank / event-flag driven dispatch (EXP-126: no `sceVideoOutAddVblankEvent`, no `sceKernelWaitEventFlag`)
- RELA relocation failure (EXP-131 → REJECTED by EXP-132: 50,450 relocations applied successfully)
- Producer at 0x801028d80 (EXP-133: unreachable code)
- Function-pointer corruption of dispatch loop (EXP-134: direct CALL)
- HLE semaphore init-count bug (EXP-135: HLE correctly honors guest init)

## Knowledge preservation files

| File | Purpose |
|------|---------|
| `worklog.md` | 3,451-line continuous investigation log (this is the authoritative narrative) |
| `CHECKPOINT_v0.0.11.md` | Snapshot of project status at v0.0.11 boundary |
| `PROJECT_STATUS_v0.0.9.md` | Earlier status snapshot |
| `PROJECT_STATUS_v0.0.10.md` | Earlier status snapshot (Windows-log comparison) |
| `PROJECT_STATUS_v0.0.11.md` | Current release status document |
| `scripts/resume_investigation_checklist.md` | Checklist for resuming the investigation on a fresh machine |
