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

### Golden Rule 8 — Verify the Function Body Before Assuming Its Behavior

EXP-091 assumed `il2cpp_codegen_register` "should insert entries" based on its name and Unity documentation. EXP-093 proved by disassembly that the actual function is a 55-byte stub that only saves 3 pointers to globals. **Never assume a function's behavior from its name alone — always disassemble and verify the body.** The same applies to EXP-052/053, which misidentified `0x800805AE0` as `il2cpp_codegen_register` (it was actually a `#dllimport:` parser, per EXP-083).

### Golden Rule 9 — Fast Hypothesis Validation, Never Trust First Success

A patch that changes behavior is NOT automatically the root cause. Every successful workaround must answer: **"What is the exact mechanism that makes this work?"**

**Workflow:**
1. Test a concrete hypothesis quickly.
2. Treat the result as **evidence, not truth**.
3. Verify with independent methods:
   - Static disassembly
   - Runtime tracing
   - Memory validation
   - A/B testing
4. If evidence contradicts the theory:
   - Correct the theory.
   - Update documentation.
   - Preserve the old conclusion as a corrected false lead.

**Canonical example — EXP-085:**
- Initial observation: Setting metadata flag `[entry+0x19]=1` allowed boot to progress.
- Wrong conclusion: "Metadata flag fix solved the problem."
- Later verification (EXP-086+): The progress was caused by a fallback path because metadata was not loaded. The patch changed behavior but did not solve the real metadata initialization problem.
- Correct conclusion: Diagnostic patch only — mechanism not understood.

**Rule:** If the mechanism is unknown:
- Classify as **temporary observation**, not root cause.
- Continue investigation.
- Do NOT build future fixes on it.

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

---

## EXP-086 Correction (2026-07-31)

### Correction to Current Blocker

**Previous (incorrect):** "SignalSema is never called by any thread"

**Corrected:** SignalSema IS called — 13 times. Workers signal their signal_semas (0x5D, 0x5F, ...) during creation. The actual deadlock is:
- Workers block on wait_semas (0x5C..0x74) — nobody dispatches tasks
- GC thread blocks on SuspendSemaphore (0x83) — nobody triggers GC
- Main thread is NOT blocked — it's running but went silent after sceKernelAllocateDirectMemory

### Updated Path B Description

```
Path B (real metadata path):
  ├── il2cpp_init → real_init → call#7 → array_proc entered
  ├── 13 workers created, signal their signal_semas, then block on wait_semas
  ├── GC thread created, blocks on SuspendSemaphore (0x83)
  ├── Import errors: sceKernelVirtualQuery NOT_FOUND, sceKernelDirectMemoryQuery NOT_FOUND, 
  │   fopen NOT_FOUND, PERMISSION_DENIED for unknown NID
  ├── sceKernelAllocateDirectMemory called (GPU memory allocated!)
  ├── Main thread goes silent — running but no more HLE calls
  └── Stall detector fires (all 14 other threads blocked)
```

### Key Progress on Path B

The main thread reaches `sceKernelAllocateDirectMemory` — this is significant progress! It means IL2CPP initialization completed enough to start GPU resource allocation. The blocker is that the main thread stops making HLE calls after this point.


---

## EXP-087 Correction (2026-07-31)

### Correction to EXP-086

**EXP-086 said:** "Main thread is NOT blocked — it's running but went silent"

**Corrected:** The main thread IS blocked — on `sceKernelWaitSema(handle=0x81)`. The stall detector captured this in the "Stall snapshot" line:
```
Stall snapshot: rip=0x6FFFFD001150 rdi=0x6FFF00000081
Stall import-stub: nid=Zxa0VhQVTsk -> libKernel:sceKernelWaitSema
sema.wait-host-block handle=0x00000081 name='Baselib_SystemSemaphore' ret=0x804F6E9EB
```

The main thread was NOT listed as a "Stall guest-thread" because the stall detector only lists threads blocked in HLE handlers, not threads stuck in import stubs. But the thread IS effectively blocked.

### Updated Current Blocker

**ALL 15 threads are deadlocked:**
- Main thread: blocked on `WaitSema(0x81)` at PRX `0x804F6E9EB`
- 13 Workers: blocked on `WaitSema(0x5C..0x74)` at EBOOT `0x800AA0207`
- GC thread: blocked on `WaitSema(0x83=SuspendSemaphore)` at PRX `0x804FB5BAF`

**Nobody signals any of these semaphores.** This is a true all-threads-deadlocked state.

### Handle 0x81 Details

- Name: `Baselib_SystemSemaphore`
- Created alongside 0x80, 0x82 (right before GC semaphores 0x83, 0x84)
- Never signaled (0 `sema.signal` entries in entire log)
- Main thread waits on it from PRX `0x804F6E9EB` (vaddr 0x2999EB)
- Created AFTER workers and BEFORE GC thread


---

## EXP-088: Semaphore 0x81 Owner Identified (2026-07-31)

### Semaphore Ownership

Handle 0x81 is the **IL2CPP ThreadPool work-available semaphore**.

- **Subsystem:** Unity IL2CPP ThreadPool (Baselib_SystemSemaphore)
- **WaitSema caller:** `0x804F6E510` (PRX) — thread pool dispatch function
- **SignalSema caller:** `0x804F6ECF9` (PRX) — same function, called when work is dispatched via atomic CAS
- **Why never signaled:** No work is submitted to the thread pool

### Updated Current Blocker

The deadlock is caused by **no work being submitted to the IL2CPP thread pool**. The main thread enters the pool as a worker and waits for work. SignalSema exists in the same function but is only called when work is dispatched — and no work is ever dispatched.

The root cause is likely an HLE function returning an error (sceKernelVirtualQuery NOT_FOUND, sceKernelDirectMemoryQuery NOT_FOUND, fopen NOT_FOUND, or PERMISSION_DENIED for unknown NID) that prevents the IL2CPP runtime from reaching the work submission stage.


---

## EXP-089: Missing Work Submission (2026-07-31)

### Classification: D — Waiting for an Event SharpEmu Never Generates

The main thread creates the GC system and thread pool, then **immediately enters the thread pool as a worker** without submitting any work. The IL2CPP runtime doesn't reach the work submission stage.

### Precise Timeline

```
Line 8905: sceKernelAllocateDirectMemory — GPU memory allocated
Line 8906: SuspendSemaphore (0x83) created — GC system init
Line 8907: ResumeSemaphore (0x84) created
Line 8908-8918: 11 Baselib_SystemSemaphore (0x85-0x90) — thread pool
Line 8922: GC thread created
Line 8923: Main thread enters thread pool → WaitSema(0x81) → BLOCKS
Line 8925: GC thread blocks on WaitSema(0x83)
```

Only 18 lines between AllocateDirectMemory and deadlock. No work submitted.

### EXP-058 Tracer Bug Correction

The "count=2454267240" from EXP-058/079 was a **tracer bug** — the tracer divided `rsi` (a pointer) by `entry_size`, producing a meaningless large number. The actual count is `rcx=0x379=889`.

### Updated Blocker

The blocker is NOT a missing SignalSema or a semaphore bug. The blocker is that **no work is submitted to the IL2CPP ThreadPool** because the IL2CPP runtime initialization doesn't reach the work submission stage. The runtime creates the GC and thread pool infrastructure, then enters the pool without queuing any work.

The missing trigger is likely:
- A GC trigger mechanism that SharpEmu doesn't implement
- A timer/event that should fire after system init
- A callback that the IL2CPP runtime registers but SharpEmu never invokes


---

## EXP-090: Missing Trigger = _ThreadPoolWaitCallback (2026-07-31)

### Root Cause Chain

```
EXP-040: Hash table entries never filled
    ↓
EXP-085: Flag patch makes ALL lookups return NULL (prevents crash but also prevents valid lookups)
    ↓
real_init looks up "_ThreadPoolWaitCallback" via hash table → returns NULL
    ↓
ThreadPool has no worker callback → can't dispatch work
    ↓
Main thread enters pool → WaitSema(0x81) → deadlock
```

### Classification Correction

EXP-089 said "D) waiting for event SharpEmu never generates."
**Corrected: A) Missing HLE implementation** — metadata hash table not populated.

### The Missing Trigger

The missing trigger is NOT a timer, GC callback, or event. It is the **`_ThreadPoolWaitCallback` function pointer**, looked up via the IL2CPP metadata hash table during `real_init`. The hash table is empty → lookup returns NULL → ThreadPool has no callback → no work → deadlock.

### Key Address

- `_ThreadPoolWaitCallback` lookup at: `0x804F055D6` (in real_init, calls `0x804F21D70`)
- Result stored at: `0x808B53C48` (global function pointer — NULL when hash table is empty)
- ThreadPool dispatch function: `0x804F6E510`

### Fix Direction

The fix must populate the IL2CPP metadata hash table so lookups return valid results. This addresses BOTH:
1. The ThreadPool deadlock (lookups return valid callbacks)
2. The crash_func crash (EXP-085: `0x801E51240` would be set to a valid value)

If the hash table is properly populated, the EXP-085 flag patch can be REMOVED.


---

## EXP-091: Hash Table Never Populated — DT_INIT Missing (2026-07-31)

### Root Cause (FINAL)

The IL2CPP metadata hash table at `0x801EF7610` is **created but never populated**. 

- EBOOT: 1689 READ sites (lookups), 1 WRITE site (creator only)
- PRX: 0 reads, 0 writes to `0x801EF7610`
- Entries are all `0xFFFFFFFF` (empty sentinel), count=0

The entries should be inserted by `il2cpp_codegen_register` during PRX DT_INIT (module initialization). SharpEmu likely doesn't call the PRX's DT_INIT, so the registration never runs.

### Chicken-and-Egg

The IL2CPP runtime looks up function pointers (like `_ThreadPoolWaitCallback`) via the hash table. But the insert function is ALSO looked up via the hash table. Without initial entries (from DT_INIT), no lookups succeed, including the lookup for the insert function itself.

### Fix: Call PRX DT_INIT

SharpEmu's PRX loader must call the PRX's DT_INIT function during module loading. This runs `il2cpp_codegen_register` which populates the hash table with initial entries. After DT_INIT:
- Hash table is populated → lookups succeed
- `_ThreadPoolWaitCallback` is found → ThreadPool works
- `0x801E51240` is set → crash_func doesn't crash
- EXP-085 flag patch can be REMOVED

### Updated Blocker

**Root cause: PRX DT_INIT not called → hash table empty → all lookups fail → deadlock.**

This is the SINGLE root cause that connects ALL prior findings:
- EXP-040: hash table never filled ← DT_INIT not called
- EXP-083: metadata global NULL ← hash table empty
- EXP-085: flag patch needed ← hash table empty (can be removed after fix)
- EXP-088: ThreadPool deadlock ← _ThreadPoolWaitCallback lookup fails
- EXP-090: missing trigger ← _ThreadPoolWaitCallback NULL


---

## EXP-092: DT_INIT_ARRAY Fix Applied (2026-07-31)

### Bug Fixed

`RunImageInitializers` was dead code — never called. `RunPreloadedModuleInitializers` only called DT_INIT, not DT_INIT_ARRAY. Fixed by calling `RunImageInitializers` for each module.

### Results

- DT_INIT_ARRAY now called for all preloaded modules
- PRX module_start (0x804CD5010) executes
- **37 more semaphores created** (stall moved from handle 0x81 to 0xA6)
- Hash table STILL empty (populated=0/100) — population happens during il2cpp_init, not DT_INIT

### Updated Understanding

The hash table is NOT populated by DT_INIT_ARRAY. It's populated during `il2cpp_init` → `real_init` → `call#7`. The DT_INIT_ARRAY fix is correct and necessary but not sufficient. The remaining issue is inside il2cpp_init's execution path.


---

## EXP-093: il2cpp_codegen_register Is a Stub (2026-07-31)

### Major Correction

EXP-091 said: *"`il2cpp_codegen_register` should insert entries during PRX DT_INIT."*
EXP-092 said: *"Hash table is populated during `il2cpp_init` → `real_init` → `call#7`."*

**Both assumptions CORRECTED by EXP-093:** `il2cpp_codegen_register` is a STUB that does NOT populate any hash table.

### il2cpp_codegen_register Location & Body

Full call chain (verified by static disassembly):

```
real_init @ 0x804F04C5C:  call [0x808958220]
  → 0x804D9C620   (wrapper: 3 LEAs + JMP)
    → 0x804FA60C0 (trampoline: JMP)
      → 0x804F23280  (ACTUAL il2cpp_codegen_register — 55-byte stub)
```

The stub at `0x804F23280` does only 3 things:
1. `call 0x804F71390` (once_init / lock helper)
2. Saves 3 args to globals: `[0x808B542E8]=rdi`, `[0x808B542F0]=rsi`, `[0x808B542F8]=rdx`
3. Returns. **No iteration, no hash insert.**

### Hardcoded Args (Match EXP-054/055)

The wrapper loads 3 hardcoded pointers:
- `rdi = 0x8086E9010` = `Il2CppCodeRegistration @ 0x8086E9000 + 0x10` (EXP-054 ✓)
- `rsi = 0x80885C598` = `Il2CppMetadataRegistration @ 0x80885C580 + 0x18` (EXP-055 ✓)
- `rdx = 0x8082AE0C0` = method pointers / type index array (new)

### Where the Metadata Actually Goes

The PRX uses a DIFFERENT structure than `0x801EF7610`:
- `call#7` (`0x804F23320`) reads the 3 globals saved by `il2cpp_codegen_register`
- Loop body `0x804F238F0` operates on a structure accessed via `[0x808923D88]`
- `array_proc` (`0x804F2B4D0`) is a merge sort on the array at `0x808958230`
- None of these write to `0x801EF7610` (PRX has 0 reads, 0 writes to it — EXP-091)

### Updated Blocker

**Root cause pivot:** The hash table at `0x801EF7610` may be a RED HERRING. The PRX doesn't use it by design. The actual metadata lookup mechanism (used by `_ThreadPoolWaitCallback` lookup at `0x804F055D6` → `0x804F21D70`) likely uses a different structure — possibly `[0x808923D88]` or the sorted array at `0x808958230`.

**Next EXP-094:** Disassemble `il2cpp_class_get_method_from_name` (`0x804F21D70`) to find what structure it ACTUALLY searches. If it doesn't read `0x801EF7610`, then the entire EXP-040..092 hash table investigation was chasing the wrong structure.

*(Golden Rule 8 added to the main Golden Rules section above.)*


---

## EXP-094: Hash Table at 0x801EF7610 Confirmed RED HERRING — Lookup Uses [0x808923D88] (2026-07-31)

### Major Confirmation of EXP-093 Hypothesis

EXP-093 hypothesized that `0x801EF7610` was a red herring and the actual lookup uses `[0x808923D88]`. EXP-094 **PROVES** this by disassembling the actual lookup function.

### il2cpp_class_get_method_from_name Is a Trampoline

```
0x804F21D70  jmp 0x804EEE8D0   ; 1-instruction trampoline
```

The actual implementation at `0x804EEE8D0` reads `[0x808923D88]` as its context pointer (5 reads), and **NEVER reads `0x801EF7610`** (0 reads).

### Runtime State of [0x808923D88]

From EXP-092 log:
- `[0x808923D88]` = `0x7F113CED77E0` (host-side pointer — POPULATED)
- Context structure contains stack canaries (`0xC0DEC0DECAFEBA00`)
- `[context+0x30]` = `0x55FBF4A4E3A0` (non-NULL host pointer — method table?)

### PRX-wide Writer Scan

- 50 PRX functions READ `0x808923D88` (verified first 10 — all reads)
- 0 PRX functions WRITE `0x808923D88` via RIP-relative addressing
- 0 EBOOT accesses to `0x808923D88`
- The write happens via indirect pointer (register-computed address, not RIP-relative)

### Why _ThreadPoolWaitCallback Lookup Still Returns NULL

The context IS populated, the method table pointer `[context+0x30]` IS non-NULL, but the lookup still returns NULL. This means:
- The method table exists but may be **incompletely populated**
- OR the method table contains wrong data (host vs guest pointers)
- OR the lookup key doesn't match

### Updated Blocker

**The blocker is NO LONGER "hash table empty".** The hash table at `0x801EF7610` is irrelevant — the PRX never reads it.

**The new blocker:** The method table at `[context+0x30]` (where context = `[0x808923D88]`) does not contain `_ThreadPoolWaitCallback`. Need to trace what methods ARE in the table and why `_ThreadPoolWaitCallback` is missing.

### EXP-040..092 Retrospective

The EXP-040..092 investigation of `0x801EF7610` was chasing the **wrong structure**. However, the work was not wasted:
- EXP-054/055 correctly identified `Il2CppCodeRegistration` and `Il2CppMetadataRegistration`
- EXP-092's DT_INIT_ARRAY fix was correct and necessary
- EXP-093 correctly identified `il2cpp_codegen_register` as a stub

**Lesson (Golden Rule 8):** Always verify by disassembly which structure a function ACTUALLY reads before investigating that structure. EXP-040 assumed `0x801EF7610` was the lookup target based on EBOOT read sites — but the PRX lookup function reads a completely different address.

### Next EXP-095

Add a runtime tracer at the `_ThreadPoolWaitCallback` lookup call site (`0x804F055D6` in `real_init`) to dump:
1. The 3 args (type_ptr, namespace_str, method_name_str)
2. The return value
3. The context structure and method table contents

One question: What does the method table at `[context+0x30]` actually contain, and is `_ThreadPoolWaitCallback` in it?


---

## EXP-095: _ThreadPoolWaitCallback Lookup SUCCEEDS — Deadlock Persists on WaitSema(0xA6) (2026-08-01)

### Major Correction to EXP-090/094

EXP-090 claimed "_ThreadPoolWaitCallback lookup returns NULL → deadlock".
EXP-094 claimed "method table doesn't contain _ThreadPoolWaitCallback".

**BOTH CORRECTED BY EXP-095:** The lookup **SUCCEEDED** at runtime. `rax = 0x6007E64D0` (non-NULL guest heap pointer to a valid `MethodInfo` structure). The method table at `[context+0x30]` IS populated and DOES contain `_ThreadPoolWaitCallback`.

### Runtime Trace (Two-Stage INT3)

A new tracer (`_Exp095ThreadPoolLookupTracer.cs`) was built with two-stage INT3:
- Stage 1: INT3 at call site `0x804F055D6` — captures args (rdi, rsi, rdx)
- Stage 2: INT3 at return site `0x804F055DB` — captures return value (rax)

Results:
- `rdi (type_ptr) = 0x60070B3A0` (guest heap — valid Il2CppClass*)
- `rsi (namespace) = 0x80826CCD3` (PRX data — "System.Threading")
- `rdx (method_name) = 0x6014F9870` (guest heap — tracer failed to read string)
- `rax (return_value) = 0x6007E64D0` — **NON-NULL, lookup SUCCEEDED**

Method info at `0x6007E64D0`:
- `+0x00 = 0x60070B3A0` (Il2CppClass* — matches rdi arg)
- `+0x10, +0x18, +0x20` = guest heap pointers (method name, signature, invoker)
- Valid, populated MethodInfo structure

### Deadlock Persists

After the lookup succeeds, the main thread continues, creates the GC thread, enters the ThreadPool dispatch function (`0x804F6E510`), and blocks on `WaitSema(0xA6)` at `0x804F6E9EB`. This is the **exact same deadlock** as EXP-092:
- Stall handle: `0xA6` (same as EXP-092)
- Stall caller: `0x804F6E9EB` (same ThreadPool dispatch)
- All 15 threads blocked

### Root Cause Re-Confirmed (EXP-088/089)

The deadlock is NOT caused by a missing callback. It's caused by **no work being submitted to the ThreadPool**. The callback EXISTS (`rax = 0x6007E64D0`) but is never INVOKED because no work items are queued.

EXP-088/089 originally identified this correctly, but EXP-090/091/092/093/094 incorrectly redirected the investigation toward the metadata/hash table. EXP-095 corrects this: the metadata lookup is NOT the problem. The problem is that the IL2CPP runtime doesn't submit work to the ThreadPool after the lookup succeeds.

### Tracer Bug (Minor)

`Exp095ReadCString` fails on guest heap addresses (`0x60...` range) because they're not identity-mapped to host addresses. Only PRX/EBOOT data segment addresses are directly dereferenceable. Future tracers should use `CpuContext.TryReadUInt8()` for guest heap strings. This bug does NOT affect the key finding (rax was read from the register, not memory).

### Updated Blocker

**The blocker is NO LONGER "missing _ThreadPoolWaitCallback".** The callback exists and the lookup succeeds.

**The new/old blocker:** No work is submitted to the ThreadPool after the lookup. The IL2CPP runtime has the callback pointer (stored at `[0x808B53C48] = 0x6007E64D0`) but doesn't queue any work items before entering the pool.

### Next EXP-096

Trace what the main thread does between `0x804F055DB` (lookup result stored) and `0x804F6E9EB` (WaitSema block). Look for a `QueueUserWorkItem` or similar work-submission call that should happen but doesn't. Check if an HLE function returns an error that causes the runtime to skip work submission.


---

## EXP-096: Work Submission Function NEVER Reached — Entire Call Chain Is Dead Code (2026-08-01)

### Case A Confirmed

The work-submission function (`0x804F6EC20`, which calls `SignalSema(0xA6)`) is **NEVER reached** at runtime. None of its 3 call sites (`0x804F4571A`, `0x804F9FAAA`, `0x804FA14C8`) are executed. Static analysis proves the entire call chain is dead code.

### Work-Submission Function

`0x804F6EC20` is the function that:
1. Iterates worker entries (loop at `0x804F6EC50..0x804F6EC66`)
2. Performs atomic CAS on `[entry+0x90]` (`0x804F6ECD3: lock cmpxchg`)
3. If CAS succeeds and `esi < 0`, calls `SignalSema` at `0x804F6ECF9`

### 3 Call Sites — All Dead Code

| Call Site | In Function | Direct Callers of That Function |
|-----------|-------------|-------------------------------|
| `0x804F4571A` | `0x804F456E0` | **0** |
| `0x804F9FAAA` | `0x804F9FA80` | **1** (at `0x804FA2089`, in function `0x804FA1FE0`) |
| `0x804FA14C8` | `0x804FA1440` | **0** |

And `0x804FA1FE0` itself has **0 direct callers**.

The ENTIRE work-submission call chain is dead code — only reachable via indirect function pointers that are never set up.

### Runtime Verification

- EXP-096 tracer patched all 3 call sites with INT3
- **ZERO hits** — none of the 3 call sites were reached
- EXP-095 lookup still succeeded (`rax = 0x6007E64D0`)
- Same stall: `WaitSema(0xA6)` at `0x804F6E9EB`
- Exit code: 4 (stall)

### Why the Call Chain Is Dead Code

The functions `0x804F456E0`, `0x804F9FA80`, `0x804FA1440`, and `0x804FA1FE0` have zero direct `call` instructions targeting them. They are only callable via:
1. C++ virtual method tables (vtables)
2. .NET delegate invocation
3. IL2CPP runtime callbacks (GC, timer, type init)
4. Function pointer globals

On a real PS5, one of these indirect registration mechanisms would set up the call chain. SharpEmu likely doesn't implement the HLE function that performs this registration.

### Updated Blocker

**The blocker is NO LONGER "no work submitted" (symptom).** The root cause is: **the work-submission call chain is dead code because the indirect function pointers that should reach it are never set up.**

### Next EXP-097

Find what should set up the indirect call chain:
1. Search PRX data segment for function pointers to `0x804F456E0`, `0x804F9FA80`, `0x804FA1440`, `0x804FA1FE0`
2. Check if these appear in IL2CPP registration data (globals at `0x808B542E8/F0/F8`)
3. Look for `call [reg]` or `call [rip+disp]` that might indirectly call these
4. Determine which HLE function should populate the function pointer

One question: What indirect call mechanism should reach `0x804F6EC20`, and why is the function pointer never set?


---

## EXP-097: Dead-Code Functions Not Registered Anywhere — Self-Registering Function Never Called (2026-08-01)

### Exhaustive Search Result

Searched for the 5 dead-code function addresses (`0x804F456E0`, `0x804F9FA80`, `0x804FA1440`, `0x804FA1FE0`, `0x804F6EC20`) as function pointers:

| Search Method | Hits |
|-------------|------|
| Stored qwords in PRX data segments | **0** |
| Stored qwords in EBOOT data segments | **0** |
| 4-byte values in non-executable segments | **0** |
| LEA instructions computing the addresses | **1** (self-referential: `0x804FA210F: lea rsi, -> 0x804FA1FE0`) |
| `movabs reg, imm64` instructions | **0** |
| IL2CPP registration globals (runtime) | 3/3 populated, **0 match** dead-code addresses |
| Runtime-set function pointer globals | 7/7 populated, **0 match** dead-code addresses |
| Fini_array entries (runtime) | 16 entries, **0 match** |

### Self-Registering Function Pattern

Function `0x804FA1FE0` is a **self-registering function**:
```asm
0x804FA210F  lea  rsi, [rip+...]  ; -> 0x804FA1FE0 (its own address!)
0x804FA2127  jmp  0x804F889D0     ; tail jump to registration function
```

It loads its own address into `rsi` and tail-jumps to `0x804F889D0` (registration function that reads `[0x808923D88]` context). But `0x804FA1FE0` itself has **0 callers** — it's dead code.

### Once-Init Guard Never Cleared

`[0x808B418D8]` = `0xFFFFFFFFFFFFFFFF` (sentinel) at runtime. The self-registering function `0x804FA1FE0` was supposed to clear this guard and register the function pointers, but it's never called.

### 7 Runtime-Set Function Pointer Globals (All Populated, None Point to Dead Code)

| Global | Call Sites | Runtime Value |
|--------|-----------|---------------|
| `[0x808B417E0]` | 1 | `0x804F09550` |
| `[0x808B417E8]` | 2 | `0x800C76C60` |
| `[0x808B417F8]` | 2 | `0x800C76CA0` |
| `[0x808B418E8]` | 1 | `0x804FB0B30` |
| `[0x808B418F0]` | **35** | `0x804FBF820` |
| `[0x808B41900]` | **15** | `0x804FBF760` |
| `[0x808B41938]` | 1 | `0x804D49340` |

All populated, none match dead-code functions.

### Updated Blocker

**The blocker is NO LONGER "function pointers not set".** The 7 runtime-set globals ARE populated, the 3 IL2CPP globals ARE populated. The problem is that the **self-registering function `0x804FA1FE0`** (which should register the work-submission path) is itself dead code — it has 0 callers and is never executed.

### Next EXP-098

Find what should call `0x804FA1FE0`:
1. Check the PRX's **init_array** (DT_INIT_ARRAY) at runtime — is `0x804FA1FE0` one of the entries?
2. Trace the 25 call sites in `real_init` to see if any reaches `0x804FA1FE0`
3. Check if `0x804FA1FE0` is an IL2CPP icall that should be registered by a runtime function
4. Consider: is `0x804FA1FE0` supposed to be called from EBOOT?

One question: Is `0x804FA1FE0` in the PRX's init_array, and if not, what code path should reach it?


---

## EXP-111: UD2 Instructions Are Noreturn Markers, NOT Function Entry Stubs (2026-08-02)

### Hypothesis REJECTED

**Hypothesis:** "UD2 stubs at function entry fail because patching skips the original function prologue. A trampoline that preserves the function entry/prologue semantics may allow execution to continue."

**Verdict: REJECTED.** Both UD2 instructions are noreturn markers AFTER calls, NOT at function entry.

### Critical Context

- **EXP-108/109/110 do not exist.** The latest EXP before this was EXP-097. No previous UD2 patching was attempted.
- **libSceApt does not exist** anywhere in the codebase, docs, or game files.
- The function containing the primary UD2 (0x801832480) was **never reached** during any emulator run.

### Primary UD2: 0x801832489

Function at 0x801832480:
```asm
0x801832480  push     rbp           ; FUNCTION ENTRY (prologue)
0x801832481  mov      rbp, rsp      ; prologue continued
0x801832484  call     0x801936B50   ; call PLT stub (imported function)
0x801832489  ud2                    ; NORETURN MARKER (not function entry!)
```

The UD2 is at offset +9, AFTER the prologue and call. The prologue IS preserved.

### Secondary UD2: 0x8007F9093

After `call 0x801832480` (calls the primary UD2's function). Also a noreturn marker.

### 67 Callers, Zero Hits

The noreturn wrapper at 0x801832480 has 67 callers in the EBOOT. None were reached during EXP-092/095/096/097. The function is an error/panic path that was correctly never triggered.

### Conclusion

The UD2 trampoline hypothesis is irrelevant:
1. The UD2 is a compiler-generated noreturn marker, NOT a function-entry stub
2. The prologue is already preserved and executes before the call
3. There is no code to continue to after the UD2 (only INT3 padding + next function)
4. The function was never called during any emulator run

The actual blocker remains the ThreadPool deadlock from EXP-096/097 (work-submission call chain is dead code).


---

## EXP Numbering Gap Explanation (2026-08-02)

**Gap:** EXP-099 through EXP-110 do not exist (12 numbers skipped).

**Cause:** EXP-111 was created as a side hypothesis test (UD2/libSceApt trampoline validation) requested by an external agent. It was numbered EXP-111 because the external agent assumed EXP-098..110 already existed. They did not — the last mainline EXP was EXP-098.

**Resolution:**
- EXP-111 is kept as-is (Golden Rule 5: never delete old conclusions)
- EXP-099 is the next mainline EXP (NOT EXP-112)
- The gap EXP-099..110 is administrative, not investigative — no experiments were lost
- Future EXPs continue from EXP-099 sequentially

**Current EXP count:** 10 mainline EXPs (090-098) + 1 side test (111) = 11 EXPs in the 090+ range

---

## EXP-098: Registration Function IS Reached — EXP-097 Corrected (2026-08-02)

### EXP-097 CORRECTED

EXP-097 claimed the registration function `0x804FA20E0` was "dead code" (never called). **WRONG.** Runtime INT3 tracing proves it IS reached.

### Runtime Evidence

```
Line 8451: [EXP098-WORKING-INIT-ENTER] caller=0x804F04C75 — 0x804F51020 IS reached
Line 8492: [EXP098-DEAD-REG-ENTER] *** 0x804FA20E0 REACHED! *** caller=0x804F527F9
```

The registration function `0x804FA20E0` fires AFTER the _ThreadPoolWaitCallback lookup. Its caller `0x804F527F9` is inside function `0x804F527C0`, called from real_init at `0x804F0590B` (offset +0xD6B).

### Two Registration Systems

| Working (7 globals) | Dead-Code Path |
|---------------------|----------------|
| `0x804F51020` → `0x804FBF780` | `0x804FA20E0` → `0x804F889D0` → `0x804FC33B0` |
| SUCCEEDS (globals populated) | UNKNOWN (guard still 0xFFFF...) |

### How the 7 Working Globals Are Populated (Template)

`0x804F51020` (once-init, called from real_init):
1. Loads 7 function pointers via LEA
2. Calls registration helpers (0x804FBF780, 0x804FBFC20, etc.)
3. Each helper stores function pointer to a global (e.g., `mov [0x808B41900], rbx`)

### The Missing Piece

`0x804FA20E0` tail-jumps to `0x804F889D0`, which calls `0x804FC33B0` (once-init primitive). If `0x804FC33B0` returns failure, the callback is never registered.

### EXP-097 Golden Rule 8 Violation

EXP-097 assumed `0x804FA1FE0` was "self-registering" because LEA at `0x804FA210F` loads `0x804FA1FE0`. But the LEA is inside function `0x804FA20E0` (a DIFFERENT function), not inside `0x804FA1FE0`. Function boundary was not verified.

### DT_INIT_ARRAY Is Empty

PRX DT_INIT_ARRAYSZ = 0 (0 entries). No constructors. The "37 more semaphores" from EXP-092 came from module_start (DT_INIT), not init_array.

### Next EXP-099

Trace `0x804F889D0` to check return value of `0x804FC33B0`. Does the once-init primitive succeed or fail?
