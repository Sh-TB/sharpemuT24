# Yatzi Master Debug State

**Primary debugging context for Yatzi (PPSA17697) on SharpEmuT24.**
**Last updated: 2026-07-31**
**Current commit: cd915e6**

This file is the single source of truth. Future agents MUST read this file first before opening any EXP report.

---

## 1. Current Truth

Only confirmed facts. Every line has been verified by runtime evidence or static analysis.

### Game Identity

| Field | Value |
|-------|-------|
| Title | Yatzi |
| Title ID | PPSA17697 |
| eboot.bin SHA256 | `d17fba4abc7858495c6f6e207b5c38961eec0c4639b04369f0c7b06866d80b6c` |
| eboot.bin Size | 32,697,964 bytes |
| Il2cppUserAssemblies.prx SHA256 | `d73b3fc7236fb2ee68e979bc96f169ac5a3c26df4036dfdb9424f28643b9598d` |
| global-metadata.dat SHA256 | `4c85fdec4efdb59534ab20af49615a36cbeef549f2f8de0431d78dbc5f21d918` |
| global-metadata.dat Size | 10,669,264 bytes |
| global-metadata.dat Magic | `0xFAB11BAF` |
| global-metadata.dat Version | 29 |
| Unity Engine | IL2CPP 2022.3.5f1 |

### Loader Configuration

| Field | Value |
|-------|-------|
| SHARPEMU_APP0_DIR | `/tmp/games/yatzi` |
| Expected metadata path | `/app0/Media/Metadata/global-metadata.dat` |
| Host metadata path | `/tmp/games/yatzi/Media/Metadata/global-metadata.dat` |
| EBOOT base | `0x800000000` |
| PRX (Il2cppUserAssemblies) base | `0x804CD5000` |
| libc.prx base | `0x804000000` |

### Required Environment

```bash
export SHARPEMU_SEMA_FAST_PATH=0    # MUST be 0 — FAST_PATH=1 causes worker NULL crash (EXP-081)
export SHARPEMU_APP0_DIR=/tmp/games/yatzi
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
# File MUST exist at Media/Metadata/global-metadata.dat (not just root)
```

### Active Diagnostic Patches

| Patch | Location | Purpose | Status |
|-------|----------|---------|--------|
| EXP-085 metadata flag | `_Exp036Il2cppInitTracer.cs` | Sets `[metadata_list_entry+0x19]=1` before il2cpp_init | Active — diagnostic, not permanent |
| 11 INT3 tracers | Various `_Exp0*.cs` files | Log execution at key IL2CPP functions | Active — diagnostic only, restored after hit |
| EXP-073 NOP bypass | REMOVED (EXP-080) | Was masking worker NULL crash | Removed — must NOT be re-added |

### Current Blocker

**sceKernelWaitSema / SignalSema synchronization deadlock.**

When global-metadata.dat is correctly loaded at `Media/Metadata/`:
- il2cpp_init is called and enters real_init
- call#7 (`0x804F23320`) is reached
- All 14 threads (main + 13 AssetGarbageCollectorHelper workers) block on WaitSema
- Main thread blocks on handle `0x83` at PRX `0x804FB5BAF`
- Workers block on handles `0x5C, 0x5E, 0x60, ...` at EBOOT `0x800AA0207`
- SignalSema is never called by any thread
- Deadlock → exit code 4 (stall)

This is the same pattern as EXP-062 (reported 2026-07-31, now confirmed on correct dump).

---

## 2. Current Boot State

Two execution paths exist depending on whether the PRX finds global-metadata.dat.

### Path A — Metadata NOT Found (Fallback)

```
global-metadata.dat NOT at Media/Metadata/
    │
    ├── PRX cannot open file via sceOpen
    │
    ├── il2cpp_init called (EXP036-IL2CPP_INIT-ENTER logged)
    ├── real_init called
    ├── call#7 called
    │
    ├── EXP-085 patch: metadata flag set to 1
    │   └── metadata_lookup returns 0 (NULL) — crash_func NOT called
    │
    ├── Unity job system starts
    │   └── 29 Job.worker threads + 14 Background Job.worker threads created
    │
    ├── Graphics threads created
    │   └── GfxFlipThread, UnityGfxDeviceWorker, UnityEOPThread
    │
    ├── VideoOut REACHED
    │   └── GPU detected, Vulkan backend selected
    │   └── FAILS: "GLFW Init failed: X11: Failed to open display :99" (host config)
    │
    └── CRASH at 0x80080684D
        └── mov r8d, [r15+rcx] where r15=NULL
        └── Per-image hash table at [image+0x278] is NULL
        └── Exit code: 139 (SIGSEGV)
```

**IMPORTANT:** Path A reaches VideoOut but is NOT the real initialization path. It is a fallback because the PRX cannot find the metadata file. Progress on this path is not meaningful for the real game.

### Path B — Metadata Found (Real Path)

```
global-metadata.dat at Media/Metadata/ (correct path)
    │
    ├── PRX opens and reads file via sceOpen
    │
    ├── il2cpp_init called
    ├── real_init called
    ├── call#7 called
    │
    ├── EXP-085 patch: metadata flag set to 1
    │
    ├── NO metadata_lookup crash (different code path than fallback)
    ├── NO Job.worker threads created
    ├── NO graphics threads created
    ├── NO VideoOut
    │
    └── DEADLOCK
        ├── Main thread: blocked on handle 0x83 at ret=0x804FB5BAF
        ├── 13 Workers: blocked on handles 0x5C..0x74 at ret=0x800AA0207
        ├── SignalSema NEVER called by any thread
        └── Exit code: 4 (stall)
```

**This is the real initialization path.** The deadlock here is the actual blocker.

### Path Comparison

| Metric | Path A (fallback) | Path B (real) |
|--------|-------------------|---------------|
| Metadata found | NO | YES |
| il2cpp_init | YES | YES |
| metadata_lookup | returns 0 (patched) | not reached |
| Job.workers | 29 | 0 |
| Gfx threads | 3 | 0 |
| VideoOut | REACHED | NOT reached |
| Result | SIGSEGV at 0x80080684D | Deadlock (all blocked) |
| Exit code | 139 | 4 |

---

## 3. Experiment Timeline

| EXP | Date | Commit | Question | Finding | Status |
|-----|------|--------|----------|---------|--------|
| 026 | 07-28 | 08c0735 | Is IL2CPP resolver BST algorithm correct? | Algorithm verified correct (239/239 symbols) | Completed |
| 027 | 07-28 | 08c0735 | Is CPU instruction emulation correct? | CPU emulation verified (T4: 10/10, T16: 768/768) | Completed |
| 028 | 07-29 | f1d0968 | Find first divergence | strcmp GOT pointing to freed memory | Completed |
| 029 | 07-29 | 13d7a4c | Why does BST strcmp fail? | Trampoline lifetime too short | Completed |
| 030 | 07-29 | ee1ed98 | Fix trampoline lifetime | Revised — deeper issue | Superseded |
| 031 | 07-29 | a8d5c09 | Narrow execution context issue | TryCallGuestFunction return value | Superseded |
| 032 | 07-29 | 3c186a4 | Why does resolver return 0? | CpuContext.Rax never updated (int→long truncation) | **Fixed** |
| 033 | 07-29 | af7d8b8 | Why crash after resolver? | NULL execute fault limit (100000) | Completed |
| 034 | 07-29 | 0e13c17 | Are globals populated? | Yes, but re-patching fails (0/232) | Superseded |
| 035 | 07-29 | 56bd06c | Is fake heap the cause? | No — uninitialized task descriptor | Superseded |
| 036 | 07-29 | 7986cbe | Why il2cpp_init never reached? | **FAST_PATH=1 causing starvation** | **Confirmed — see EXP-081** |
| 037 | 07-30 | 5a5d782 | Are IL2CPP static initializers running? | Empty init_array | Superseded (wrong dump) |
| 038 | 07-30 | 6f7a979 | Is DT_INIT callback passed? | rdx not passed | Superseded (wrong dump) |
| 039 | 07-30 | 1e13915 | Does rdx fix it? | No — circular dependency | Completed |
| 040 | 07-30 | f41736c | Are hash table entries filled? | Never filled — fill function never called | **Important** |
| 041 | 07-30 | d76f7bf | What is the init order? | il2cpp_init called BEFORE hash lookup sets 0x801E51240 | **Important** |
| 042 | 07-30 | 813a5d2 | Does metadata lookup return valid? | Yes — 0x801E51240 needs pre-init | Completed |
| 043 | 07-30 | 7a7b4ad | Is pre-init mechanism missing? | PRX DT_INIT forces jump to INT3 | Superseded |
| 044 | 07-30 | 7465613 | Is INT3 a module_start? | No — ELF padding | Completed |
| 045 | 07-30 | aedf782 | Does fini_array contain pre-init? | No — destructors only | Completed |
| 046 | 07-30 | 4721b59 | Is crash from call #7 or #8? | Call #8 — metadata list prematurely populated | **Important** |
| 047 | 07-30 | 3428a8f | Do three fixes prevent crash? | Yes but cascade remains | Completed |
| 048 | 07-30 | 538c4da | Does callback stub allow progress? | Yes — workers created | Completed |
| 049 | 07-30 | db3d578 | What is at 0x801E51220? | NULL — systemic pattern | Completed |
| 050 | 07-30 | ea58673 | Why is hash lookup skipped? | 15+ conditional jumps skip it | Completed |
| 051 | 07-30 | 30e6215 | Do buffer+NOP+loop fixes work? | No — all reverted | Completed |
| 052 | 07-30 | 0f6db8d | What mechanism is missing? | il2cpp_codegen_register wrapper identified | Superseded (misidentified) |
| 053 | 07-30 | 6b62771 | Is wrapper ever called? | NEVER called — 0 hits | **Corrected by EXP-083** |
| 054 | 07-30 | a101e62 | Where is Il2CppCodeRegistration? | Found at 0x8086E9000 | Superseded (wrong dump) |
| 055 | 07-30 | 5f89b31 | Where is MetadataRegistration? | Found at 0x80885C580 | Superseded (wrong dump) |
| 056 | 07-30 | d325f54 | Why structs populated but nothing works? | Missing CONSUMER function | Completed |
| 057 | 07-30 | 77bd7dc | What is the consumer? | Call #7 (0x804F23320) | Completed |
| 058 | 07-30 | d928189 | Does call #7 execute? | Returns early — metadata loader fails | Completed |
| 059 | 07-31 | efd65f5 | What is the real structure? | Il2CodeGenModule, not CodeReg — dump incomplete | **Important** |
| 060 | 07-31 | a915330 | Does complete dump fix init? | YES — IL2CPP init works | Completed |
| 061 | 07-31 | b28cce2 | Is the eboot correct? | **NO — Dreaming Sarah, not Yatzi!** | **Critical correction** |
| 062 | 07-31 | 89ad82e | Does FAST_PATH=0 deadlock? | YES — SignalSema never called, 14 threads blocked | **Important — current blocker** |
| 063 | 07-31 | 6a1819d | Does FAST_PATH=1 resolve deadlock? | Yes but causes NULL execute crash | **Corrected by EXP-081** |
| 064 | 07-31 | 202e54d | What causes NULL executes? | IL2CPP stubs return NULL → stack corruption | Completed |
| 065 | 07-31 | 47274be | Does heap alloc fix stack corruption? | Partial — deeper source remains | Partial |
| 066 | 07-31 | 137f3d7 | Does fixing re-patching help? | Re-patching fails (0/232) | Superseded |
| 067 | 07-31 | 45af2a2 | Is re-patching necessary? | No — resolver returns real addresses | Completed |
| 068 | 07-31 | 936a53c | What is the FAST_PATH tension? | Both settings have issues | Completed |
| 069 | 07-31 | 3c60edc | Is SignalSema imported? | Yes but NEVER called | Completed |
| 070 | 07-31 | 9304030 | Where is the gate? | cmp byte [rbx+0x108], 0 at 0x800AA0207 | Completed |
| 071 | 07-31 | a59f6a6 | What is [rbx+0x108]? | Tagged pointer (WRONG — see EXP-079) | **Corrected** |
| 072 | 07-31 | 3511466 | Does NOPping gate help? | SignalSema fires but on wrong handle | Diagnostic only |
| 073 | 07-31 | d1a90df | Does 11-byte NOP fix crash? | Prevents crash but signals wrong sema | **Removed in EXP-080** |
| 074 | 07-31 | 1204062 | Does game reach rendering? | NO — wrong handles signaled | Completed |
| 075 | 07-31 | 64b43b0 | Should CLEAR signal 0x5C? | CLEAR is destructor, not callback | **Corrected by EXP-079** |
| 076 | 07-31 | b0b641d | What is the dependency? | Chain ptr + missing GPU (WRONG) | **Corrected by EXP-077/079** |
| 077 | 07-31 | a2982c9 | Is GPU the blocker? | NO — downstream, not causal | Completed |
| 078 | 07-31 | c839ae3 | Is 0x5C ever signaled? | NO — 0/5.7M (NOP-contaminated) | **Corrected by EXP-080** |
| 079 | 07-31 | d13b8c9 | What does CLEAR actually do? | C++ destructor; [rbx+0x108] is byte flag | **Important correction** |
| 080 | 07-31 | d13b8c9 | Does clean run reach il2cpp_init? | NO — 100K NULL executes, FAST_PATH=1 | **Important** |
| 081 | 07-31 | 97db9fc | Why are [worker+0xF8] NULL? | **FAST_PATH=1** — workers race ahead of dispatcher | **Fixed (FAST_PATH=0)** |
| 082 | 07-31 | a922906 | Why crash at 0x80080684D? | Per-image hash table [image+0x278]=NULL | Completed |
| 083 | 07-31 | acd9271 | Where should registration happen? | Metadata global 0x801E51240 never populated | Completed |
| 084 | 07-31 | 49ad4b8 | What does hash_lookup search for? | Metadata list flag=0x00 (searchable) — should be non-zero | **Confirmed** |
| 085 | 07-31 | f2b5870 | Does flag fix allow progress? | YES — crash eliminated, VideoOut reached (fallback path) | **Fixed (diagnostic)** |
| — | 07-31 | 592c0f4 | Metadata validation | File valid, but correct loading → deadlock | Supporting evidence |
| — | 07-31 | cd915e6 | Golden Rule validation | All 5 rules confirmed | Completed |

---

## 4. False Leads / Corrected Findings

Every corrected assumption is documented here. Future agents must NOT reopen these without new evidence.

### EXP-061: Wrong Game Dump

```
Wrong: eboot.bin (7.7MB) was Yatzi
Correct: eboot.bin (7.7MB) was Dreaming Sarah — all EXP-035..058 addresses invalid
Impact: 24 experiments wasted on wrong game
```

### EXP-071/075/076: [rbx+0x108] Misidentified

```
Wrong: [rbx+0x108] is a tagged pointer to unresolved dependency
Correct: [rbx+0x108] is a byte flag (0x01 = work pending). Upper bytes are uninitialized heap garbage.
Corrected by: EXP-079
```

### EXP-075/076: CLEAR Misidentified

```
Wrong: CLEAR (0x800A9F750) is a dependency completion callback that should signal 0x5C
Correct: CLEAR is a C++ destructor for the worker pool singleton. Only called during teardown.
Corrected by: EXP-079
```

### EXP-076: GPU Init Misidentified as Blocker

```
Wrong: Root cause = missing GPU/graphics init
Correct: GPU init is downstream, not causal. Main thread reaches GPU memory alloc but stalls before il2cpp_init.
Corrected by: EXP-077
```

### EXP-063: FAST_PATH=1 Adopted as Fix

```
Wrong: FAST_PATH=1 resolves the deadlock (EXP-062)
Correct: FAST_PATH=1 causes workers to race ahead of dispatcher → call NULL [worker+0xF8] → 100K SIGSEGV → host crash
Corrected by: EXP-081
Fix: FAST_PATH=0 (proper blocking mode)
```

### EXP-073: NOP Bypass Adopted as Diagnostic

```
Wrong: 11-byte NOP at 0x800AA0207 is a viable workaround
Correct: NOP creates artificial execution path — signals wrong sema, masks real issue
Corrected by: EXP-080
Action: NOP removed, must NOT be re-added
```

### EXP-078: "0x5C Never Signaled" (NOP-Contaminated)

```
Wrong: Handle 0x5C is never signaled (0/5.7M) — missing completion path
Correct: Finding was from NOP-contaminated run. The NOP created an artificial execution path.
Corrected by: EXP-080
```

### EXP-052/053: Wrapper Misidentified

```
Wrong: Wrapper at 0x800805AE0 is il2cpp_codegen_register — its "never called" status is the root cause
Correct: Wrapper is a #dllimport: string parser. Its "never called" status is expected — not part of normal init.
Corrected by: EXP-083
```

### EXP-082: "Downstream of EXP-053"

```
Wrong: Crash at 0x80080684D is downstream of the EXP-053 wrapper-never-called issue
Correct: The wrapper is irrelevant (it's a string parser). The crash is caused by per-image hash table [image+0x278]=NULL.
Corrected by: EXP-083
```

### EXP-080: hash_table "Corruption"

```
Wrong: Hash table pointer at 0x801EF7610 is corrupted (changed from valid to invalid)
Correct: Compared values from two DIFFERENT addresses (0x801EF7610 vs 0x801EE7610 — 64KB apart). No corruption.
Corrected by: EXP-080 validation
Note: The 0x801EF7610 vs 0x801EE7610 typo is a standing gotcha — has caused wasted work TWICE.
```

### EXP-085: "VideoOut Reached" (Fallback Path)

```
Wrong: EXP-085 reached VideoOut — major milestone for Yatzi
Correct: VideoOut was reached on the FALLBACK path (metadata not found by PRX). The real init path (with metadata) leads to deadlock.
Corrected by: Golden Rule validation (2026-07-31)
Impact: "VideoOut reached" is NOT a valid milestone unless metadata path is confirmed.
```

---

## 5. Golden Rules

### Golden Rule 0 — Validate Reality Before Debugging Symptoms

Before analyzing crashes:
- Verify game file SHA256 (eboot, PRX, metadata)
- Verify file paths (metadata at Media/Metadata/, not just root)
- Verify execution branch (real path vs fallback)
- Verify A/B behavior (with/without metadata)
- Verify environment variables (FAST_PATH=0, not 1)

### Golden Rule 1 — No Root Cause Without Evidence

No root cause declaration without:
- Log evidence (specific addresses, register values, call traces)
- Reproducible test (same result on re-run)
- Commit reference (exact code state)
- A/B comparison (before vs after change)

### Golden Rule 2 — No Milestone From Fallback Paths

No milestone is accepted from fallback execution paths.

Example: "VideoOut reached" is meaningless unless:
- Metadata path confirmed (file found at Media/Metadata/)
- Real initialization path confirmed (not fallback)
- The milestone occurs on Path B, not Path A

### Golden Rule 3 — No Temporary Patches as Fixes

Diagnostic patches (NOP, flag writes, stubs) must be:
- Clearly marked as diagnostic
- Removed before drawing final conclusions
- Never treated as permanent fixes
- A/B tested against clean state

### Golden Rule 4 — Check Address Typos

The addresses `0x801EF7610` and `0x801EE7610` differ by 64KB and are NOT the same variable. This typo has caused wasted work twice (EXP-053, EXP-080).

Always verify which tracer's address you are reading from before comparing values.

### Golden Rule 5 — Preserve Both Original and Corrected Conclusions

When correcting an EXP:
- Keep both the original and corrected versions
- Mark the correction explicitly
- Never delete old conclusions
- Document the correction relationship

### Golden Rule 6 — Check Log Throttling

`grep -c` counts LOG LINES, not events. Throttled logging undercounts.

EXP-080 reported "1005 NULL executes" but the actual count was 100,000+ (logging throttles after #1000).

Always check for throttling. Use the highest numbered event, not line count.

### Golden Rule 7 — Don't Override Correct Findings Without Proof

EXP-036 correctly identified FAST_PATH=1 as the problem (2026-07-29). EXP-063 overrode this without disproving it. This wasted 18 experiments (EXP-063..080).

Before overriding a finding, explicitly disprove it with evidence.

---

## 6. Do Not Repeat

The following investigations are CLOSED. Do not reopen unless new evidence appears.

### Closed Investigations

| Topic | EXPs | Resolution |
|-------|------|------------|
| IL2CPP resolver BST algorithm | 026-028 | Verified correct |
| CPU instruction emulation | 027 | Verified correct |
| CpuContext.Rax return value | 032 | Fixed (int→long) |
| Fake heap hypothesis | 035 | Disproven |
| FAST_PATH=1 vs 0 | 036, 062, 063, 068, 081 | FAST_PATH=0 is correct |
| Worker NULL [rbx+0xF8] | 035, 064, 067, 081 | Caused by FAST_PATH=1 — fixed |
| NOP bypass at 0x800AA0207 | 072-078 | Removed — created artificial path |
| [rbx+0x108] as tagged pointer | 071, 075, 076 | It's a byte flag, not a pointer |
| CLEAR as dependency callback | 075, 076 | It's a C++ destructor |
| GPU init as blocker | 076 | Downstream, not causal |
| Wrapper 0x800805AE0 as il2cpp_codegen_register | 052, 053 | It's a #dllimport: parser |
| hash_table "corruption" (0x801EF7610 vs 0x801EE7610) | 080 | Typo — two different addresses |
| Metadata global 0x801E51240 NULL | 040, 041, 083, 084 | Caused by metadata list flag=0x00 — patched in EXP-085 |
| Metadata flag patch (EXP-085) | 085 | Diagnostic fix — eliminates crash_func crash |
| global-metadata.dat validity | Golden Rule validation | File is valid, correctly loaded |
| Wrong game dump (Dreaming Sarah) | 061 | Corrected — all EXP-035..058 invalidated |

### Standing Gotchas

1. **0x801EF7610 vs 0x801EE7610** — EF vs EE address typo. Has caused wasted work twice.
2. **Metadata file path** — Must be at `Media/Metadata/global-metadata.dat`, NOT just root.
3. **FAST_PATH=1** — Set in 6 scripts as EXP-062 workaround. Must be 0. Check all scripts.
4. **Log throttling** — NULL execute count was 100K+, not 1005. Check for throttled logging.
5. **Fallback path** — Without metadata at correct path, PRX takes fallback → different behavior.

---

## Quick Reference: Key Addresses

| Address | Description |
|---------|-------------|
| `0x800000000` | EBOOT base |
| `0x804CD5000` | Il2cppUserAssemblies.prx base |
| `0x804ED85D0` | il2cpp_init (PRX) |
| `0x804F04BA0` | real_init (PRX) |
| `0x804F23320` | call#7 / array_proc entry (PRX) |
| `0x800A9F9A0` | worker_create (EBOOT) |
| `0x800AA0170` | worker dispatch loop (EBOOT) |
| `0x800AA0207` | gate instruction (cmp byte [rbx+0x108], 0) |
| `0x800AA01CE` | call [rbx+0xF8] (worker task call) |
| `0x800805AE0` | #dllimport: string parser (NOT il2cpp_codegen_register) |
| `0x800806750` | hash table lookup function (crash at +0xFD) |
| `0x8004BD620` | hash_lookup function (EXP039 tracer) |
| `0x8007F90A0` | hash_table_writer (EXP039 tracer) |
| `0x800C66B40` | metadata_lookup (checks [entry+0x19] flag) |
| `0x80135DDD0` | crash_func (reads NULL [0x801E51240]) |
| `0x8013EF019` | metadata global write site (conditional on hash_lookup) |
| `0x801E51240` | metadata global pointer (NULL when not set) |
| `0x801EF7610` | global hash table pointer (EXP058 tracer — CORRECT address) |
| `0x801EE7610` | different global (EXP039 tracer — NOT the same as 0x801EF7610!) |
| `0x801EA4E80` | metadata list head pointer |
| `0x801EA49D8` | metadata lookup callback pointer |
| `0x801CEEA08` | task dispatcher function pointer slot |

---

## Next Steps

The current blocker is the **semaphore deadlock** (Path B) that occurs when metadata is correctly loaded.

Possible investigation directions (NOT yet started):
1. Trace why SignalSema is never called in the real init path
2. Check if a SharpEmu HLE function returns an error that causes the PRX to skip signaling
3. Investigate if the metadata flag patch (EXP-085) is still needed on the real path
4. Check if the deadlock is in the PRX's il2cpp_init or in EBOOT post-init code

**Do NOT investigate GPU, VideoOut, or rendering until the semaphore deadlock is resolved.**
