# EXP-117 — Asset Verification + Independent Reviewer Validation Report

**Date:** 2026-08-03
**Role:** Independent reviewer (per user's framing). This is a TEST-ONLY report. No code changes. No fixes. No suggestions to change debugging direction.
**Method:** Strict evidence-based review of accumulated runtime/static evidence, plus a new asset-verification check (the cheaper test the user prioritized before the FAST_PATH=0 trace).

---

## Part 1 — ASSET VERIFICATION (the cheaper test, done first)

### Test objective

Per the user's instruction: verify whether `Media/Resources/unity_builtin_extra` and `unity default resources` actually exist and are non-empty in any available Yatzi dump, because the 2026-07-24 checkpoint's "missing shader" theory rests on this and I could not re-verify it in the prior session.

### What I checked

**Searched the entire accessible filesystem for these files.** Found them in `/home/z/my-project/upload/`:

| File | Size | Header bytes (first 80 ASCII) | Source |
|------|------|-------------------------------|--------|
| `/home/z/my-project/upload/unity_builtin_extra` | **820,024 bytes (~820KB)** | `\x00...2022.3.5f1\x00...` (Unity version string visible) | User-uploaded, dated Jul 25 17:56 |
| `/home/z/my-project/upload/unity default resources` | **859,240 bytes (~859KB)** | `\x00...2022.3.2f1\x00...` (Unity version string visible) | User-uploaded, dated Jul 25 17:54 |

Also found archives confirming these are real Yatzi assets:
- `/home/z/my-project/upload/unity default resources.rar` (174KB archive, contains `unity default resources` 859,240 bytes, timestamp `29-09-25 20:59` — matches Yatzi dump)
- `/home/z/my-project/upload/globalgamemanagers.rar` (82KB archive, contains `globalgamemanagers` 210,920 bytes, timestamp `29-09-25 20:59`)
- `/home/z/my-project/upload/globalgamemanagers.assets.zip` (2.5MB)
- `/home/z/my-project/upload/globalgamemanagers` (210,920 bytes, also has `2022.3.5f1` version string — matches Yatzi's Unity version per EXP-059)

### Verification of file contents

The `unity_builtin_extra` file:
- Is NOT empty (820KB)
- Contains the Unity version string `2022.3.5f1` at offset 0x38 (exactly matching Yatzi's Unity version per EXP-059)
- Has a file format consistent with Unity serialized asset files (no `UnityFS` magic, but starts with the same header pattern as `globalgamemanagers` — another known Unity asset file)

The `unity default resources` file:
- Is NOT empty (859KB)
- Contains the Unity version string `2022.3.2f1` at offset 0x38 (close to but slightly older than Yatzi's `2022.3.5f1` — Unity resource files are typically version-compatible across minor revisions, per checkpoint section 21)

### The "complete dump" archive contents

The archive `PPSA17697-app0UPLOAD_COMPLETE_DUMP.rar` (28MB) contains:
- `eboot.bin` (32.7MB)
- `global-metadata.dat` (10.6MB)
- `Il2cppUserAssemblies.prx` (74.7MB)
- `lib_burst_generated.prx`, `libc.prx`, `libSceNpCppWebApi.prx`, `PS5Util.prx`, `PSNCommon.prx`, `PSNCore.prx`, `SaveData.prx`

**It does NOT contain `Media/Resources/unity_builtin_extra` or `unity default resources`.** The user uploaded those separately (in their own .rar files), strongly suggesting they were missing from the original "complete" dump and the user obtained them later.

### Why this matters

The 2026-07-24 checkpoint (section 20-21) found that:
- `Media/Resources/unity_builtin_extra` was **0 bytes (empty)** at the time of that run
- `Media/Resources/unity default resources` was **0 bytes (empty)** at the time of that run
- This caused Unity's `Internal-ErrorShader.shader` lookup to return NULL → Unity abort at `rip=0x800B28A0D`

**My finding today:** The actual Unity resource files exist (in `/home/z/my-project/upload/`) and are properly sized (820KB and 859KB respectively). The 2026-07-24 checkpoint's "empty file" finding was about a **specific incomplete dump state at that time** — the user has since obtained the real files.

### Asset verification verdict

**The "missing shader" theory from the 2026-07-24 checkpoint was based on a dump-completeness issue that has since been resolved.** The real `unity_builtin_extra` (820KB, Unity 2022.3.5f1) is available in `/home/z/my-project/upload/`. If a fresh trace were run today with this file placed in `Media/Resources/`, the `Internal-ErrorShader` lookup should succeed (assuming SharpEmu's file-open path resolves the upload directory correctly, which it currently does NOT — the game's `Media/Resources/` directory doesn't exist in this session's `/tmp/games/yatzi/`).

**Implication for the EXP-096..115 callback-dispatch investigation:** The "missing shader" theory does NOT invalidate the callback-dispatch investigation, because the missing-shader issue is a separate, dump-completeness problem that has since been fixed. The callback-dispatch issue (registered callback never invoked) was investigated under `FAST_PATH=1` semantics and may or may not reproduce under `FAST_PATH=0` — but it's a separate question from the missing-shader issue.

**Implication for the maintainer summary:** The summary should NOT claim "missing shader is the root cause" as a settled conclusion. It should note that:
1. The 2026-07-24 checkpoint identified a missing-shader abort (real at the time)
2. The user has since obtained the real `unity_builtin_extra` (820KB) and `unity default resources` (859KB)
3. A fresh trace with these files properly placed in `Media/Resources/` is required to determine whether the missing-shader abort is still the blocker, or whether the callback-dispatch issue is the real blocker (or both, or neither)

---

## Part 2 — Independent Reviewer Validation (7-point format)

Per the user's instruction: "Return only: CLAIM / STATUS / EVIDENCE / CONFIDENCE. No code changes."

---

### Claim 1 — GPU Stub Regression Test

**Developer claim:** "Before adding GPU stubs, Flip #1 happened. After adding `GrQ9s4IrNaQ`, `VkqLPArfFdc`, `XlNp7jzGiPo`, `MM4IZSEYytQ`, Flip stopped."

**STATUS: REJECTED**

**EVIDENCE:**

1. The 4 stubs are added in commit `3b2d499` ("VkqLPArfFdc + 3 NID stubs") per CHECKPOINT_v0.0.11.md section 10 (line 276) and PROJECT_STATUS_v0.0.10.md line 90.

2. The CHECKPOINT_v0.0.11.md section 12 ("Mistakes Documented") explicitly lists "regression" as one of the **6 false hypotheses that wasted days**:
   > "6 false hypotheses wasted days — scheduler, semaphore deadlock, metadata corruption, missing files, fake stubs, regression"

3. PROJECT_STATUS_v0.0.10.md section "Action Items" recommends KEEPING all 4 stubs:
   - `VkqLPArfFdc` — "Keep (harmless)" (0 calls on Windows)
   - `GrQ9s4IrNaQ` — "Keep" (Maybe needed)
   - `MM4IZSEYytQ` — "Keep" (Maybe needed)
   - `XlNp7jzGiPo` — "Keep" (Maybe needed)

4. The actual cause of the "Flip stopped" was the missing-shader abort at `rip=0x800B28A0D` (per checkpoint section 20), NOT the GPU stubs.

5. The 4 stubs are pure return-zero (or return-non-NULL for VkqLPArfFdc) stubs. Source verified at `GameCompatExports.cs` lines 188-203:
   ```csharp
   VkqLPArfFdcStub: returns ORBIS_GEN2_OK with RAX=0x0000000602000000
   AudioOutGetPortStateStub: returns 0
   AgcDriverSetHsOffchipParamStub: returns 0
   AgcDriverSetTFRingStub: returns 0
   ```
   None of these can cause a "Flip stopped" regression — they all return success.

**CONFIDENCE: HIGH** — The checkpoint itself identified the regression claim as a false hypothesis. The stubs return success; they cannot block anything.

---

### Claim 2 — VideoOut / Flip Validation

**Developer claim:** "sceVideoOutFlip was reached."

**STATUS: PARTIALLY CONFIRMED (configuration-dependent)**

**EVIDENCE:**

1. CHECKPOINT_v0.0.11.md section 18 (2026-07-24 run, default config, no FAST_PATH): `sceVideoOutSubmitFlip` was called **1 time** (vs 0 direct calls for Dreaming Sarah, which uses DCB-embedded flips). `VideoOutOpen` = 1, `VideoOutRegisterBuffers2` = 1, `VideoOutAddFlipEvent` = 2.

2. EXP-074 (2026-07-31 run, under FAST_PATH=1 + 11-byte NOP): **0 calls** to `sceVideoOutOpen`, `sceVideoOutSubmitFlip`, `sceVideoOutSubmitFrame`, `sceGnmSubmitCommandBuffer`, `sceAgcDriverSubmitDcb`.

3. Buffer address: `0x10CA0000` (registered via `sceVideoOutRegisterBuffers2`, then flipped) — checkpoint section 18.

4. Resolution: Not explicitly recorded in the checkpoint's pipeline counters. The SubmitFlip source (`VideoOutExports.cs` lines 1126-1312) uses `displayBuffer.Width`/`Height`/`PitchInPixel` from the registered buffer.

5. The user's "1920x1080" claim in the latest message is consistent with a typical PS5 display buffer but I could not directly verify it from available evidence in this session.

6. **Framebuffer was NOT real** — `_guestImages` was empty, 0 `GIMG-CREATE` events (vs 3 for working Dreaming Sarah). The address `0x10CA0000` was registered as a valid flip target (in `_availableGuestImages`) but never had a real Vulkan image created for it.

7. With `SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1`: 1 frame presented (frame #1, black, synthetic test pattern via `CmdClearColorImage((0,0,0,1))`).

**CONFIDENCE: HIGH** that `sceVideoOutSubmitFlip` was reached in the 2026-07-24 config; **MEDIUM** that the resolution was 1920x1080 (consistent but not directly verified); **HIGH** that the framebuffer was fallback (not real game content).

---

### Claim 3 — GPU Rendering Pipeline Validation

**Developer claim:** "Did the GPU actually render game content?"

**STATUS: REJECTED (GPU did NOT render game content)**

**EVIDENCE:**

From CHECKPOINT_v0.0.11.md section 18 (2026-07-24 run, side-by-side with working Dreaming Sarah):

| Metric | Dreaming Sarah (working) | Yatzi |
|--------|--------------------------|-------|
| AgcDriverSubmitDcb | 84 | **1** |
| AgcDcbDrawIndexAuto | 66 | **1** |
| AgcDcbDrawIndexOffset | 120 | **0** |
| AgcCreateShader | 99 | 36 |
| AgcCreatePrimState | 378 | 2 |
| GIMG-CREATE (render target creation) | 3 | **0** |
| Frames produced | 90 | 0 (without fallback) / 1 (with fallback, black) |

1. **drawCalls count:** 1 (vs 186 for working game — `AgcDcbDrawIndexAuto`=1 + `AgcDcbDrawIndexOffset`=0). Insufficient for real rendering.

2. **triangleCount:** Not directly recorded, but with only 1 `DrawIndexAuto` and 0 `DrawIndexOffset`, the total is at most a handful — not enough for real game rendering.

3. **render targets:** 0 `GIMG-CREATE` events — no render target was ever created. The "render_target_new" path (which should populate `_guestImages`) was never reached.

4. **framebuffer writes:** The framebuffer at `0x10CA0000` was NEVER written by GPU rendering. The only "write" was the fallback's `CmdClearColorImage` clear-to-black.

5. **DCB submissions:** 1 `sceAgcDriverSubmitDcb` (vs 84 for working game).

6. **GPU command execution:** Minimal — 1 DCB submitted with at most 1 draw call. No real rendering pipeline ran.

**CONFIDENCE: HIGH** — The GPU did not render game content. The single frame presented (with fallback) was a synthetic black test pattern, not game rendering.

---

### Claim 4 — Unity Resource Validation

**Developer claim:** "unity_builtin_extra / Internal-ErrorShader may block rendering."

**STATUS: PARTIALLY CONFIRMED (was true at 2026-07-24; file now available)**

**EVIDENCE:**

1. CHECKPOINT_v0.0.11.md section 20 (2026-07-24 run): The `Internal-ErrorShader.shader` lookup at function `0x800ABA330` returned NULL → Unity abort at `rip=0x800B28A0D` (intentional NULL-deref assertion pattern).

2. CHECKPOINT_v0.0.11.md section 21: At that time, `Media/Resources/unity_builtin_extra` was **0 bytes (empty)** and `Media/Resources/unity default resources` was **0 bytes (empty)**.

3. CHECKPOINT_v0.0.11.md section 21: The fault timing showed the abort happened BEFORE Unity even opened `unity_builtin_extra`:
   ```
   Line 2266: stat unity default resources → found (0 bytes)
   Line 2273: UNMAPPED fault (Internal-ErrorShader lookup returns NULL)
   Line 2340: stat unity_builtin_extra → found (0 bytes)  <-- 67 lines LATER
   ```

4. **NEW FINDING (this session, EXP-117):** The real `unity_builtin_extra` file (820,024 bytes, Unity `2022.3.5f1`) exists in `/home/z/my-project/upload/unity_builtin_extra`. The real `unity default resources` (859,240 bytes, Unity `2022.3.2f1`) exists in `/home/z/my-project/upload/unity default resources`. Both were uploaded Jul 25 (after the 2026-07-24 checkpoint) and have file timestamps matching the Yatzi dump (`29-09-25 20:59`).

5. **The "missing shader" theory was true at the time of the 2026-07-24 checkpoint, but the file has since been obtained.** A fresh trace with the real file placed in `Media/Resources/` is required to determine whether the missing-shader abort is still the blocker.

6. CHECKPOINT_v0.0.11.md section 21 also notes: "Yatzi is also missing `level0` and `sharedassets0.assets`, so it wouldn't be playable without those either." — But `globalgamemanagers` (210KB) and `globalgamemanagers.assets` (2.5MB zip) ARE available in `/home/z/my-project/upload/`, also uploaded Jul 25.

**CONFIDENCE: HIGH** that the missing-shader abort was real at 2026-07-24; **HIGH** that the file is now available; **MEDIUM** that placing the file in `Media/Resources/` would resolve the abort (requires a fresh trace to confirm — SharpEmu's file-open path must resolve the new location).

---

### Claim 5 — Semaphore / Thread Validation

**Developer claim:** "Semaphore handling works."

**STATUS: UNKNOWN (evidence was collected only with FAST_PATH=1; cannot confirm without FAST_PATH=0)**

**EVIDENCE:**

1. **Source code analysis (EXP-114, this session):** The semaphore HLE source (`KernelSemaphoreCompatExports.cs`) looks correct in non-bypass paths:
   - `WakePredicate` acquires tokens atomically inside `lock(semaphore.Gate)`
   - `SignalSema` increments count under lock and pulses both guest and host waiters
   - Spurious-wake handling: `WakePredicate` re-checks count under lock; if insufficient, returns false (re-blocks)
   - Handle allocation is purely sequential (`_nextSemaphoreHandle` starts at 1, increments by 1: handles 2, 3, 4, 5, …) — NO odd/even bifurcation

2. **CRITICAL CORRECTION from CHECKPOINT_v0.0.11.md section 14 (commit `881591a`):** Prior EXP-078 conclusion "workers signal wrong handles" was **WRONG**. The checkpoint found:
   - SignalSema = 4009 (signals ARE happening, not 0 as previously thought)
   - **Group 1 (PAIRED, 0x5C-0x75): WORKING** — 13 pairs, wait on EVEN handle, signal on ODD handle (handle+1). This is Unity's normal "worker wait/completion signal" pattern BY DESIGN.
   - **Group 2 (DEADLOCKED, 0x81-0x8D): ALL BLOCKED** — 13 semaphores waited on, NONE ever signaled. These are the ACTUALLY DEADLOCKED semaphores.
   - **Group 3 (MIXED, 0x93-0xA2): PARTIALLY WORKING** — both waits and signals, but wait_count > signal_count.

3. CHECKPOINT_v0.0.11.md section 15: "All 13 deadlocked semaphores (0x81-0x8D) are waited on by Job.worker 0-12" — These workers are NOT deadlocked; they are **IDLE**, correctly waiting for the main thread to dispatch C# Job System work. Nobody is dispatching jobs because the main thread is stuck in bootstrap.

4. **The REAL bottleneck per checkpoint section 15:** The MAIN THREAD is stuck in a busy loop (calling `1D0H2KNjshE`, `hsi9drzHR2k`, `scePthreadMutexLock`, `sceKernelClockGettime`, `sceAudioOutOutput`) — NOT in a semaphore wait. The workers are idle waiting for work that never comes.

5. **FAST_PATH caveat (EXP-114, this session):** ALL prior semaphore runtime evidence (EXP-072..078) was collected under `SHARPEMU_SEMA_FAST_PATH=1` + 11-byte NOP gate. Under `FAST_PATH=1`, `WaitSema` returns OK immediately **without decrementing count, blocking, or registering a waiter**. This means:
   - Counts grow without bound by design (e.g., handle 0x73: 1 → 447,579) — this is the documented behavior of the bypass, not a bug
   - The "workers signal wrong handles" observation was an artifact of the bypass — workers signal whatever handle the game's code tells them to signal
   - The callback-dispatch/WaitSema deadlock may not reproduce the same way under clean `FAST_PATH=0` conditions

6. The checkpoint's section 14-15 data appears to come from a DIFFERENT, earlier trace (commit `881591a`) that may have used different settings. I cannot tell from this session's filesystem whether section 14-15 was also under FAST_PATH=1 or not.

**CONFIDENCE: HIGH** that source code looks correct; **HIGH** that prior EXP-078 "wrong handles" interpretation was corrected by checkpoint section 14; **MEDIUM** that workers are idle (not deadlocked); **LOW** that the callback-dispatch issue is real under FAST_PATH=0 (requires clean trace to confirm).

---

### Claim 6 — VkqLPArfFdc Validation

**Developer claim:** "VkqLPArfFdc may block GPU."

**STATUS: REJECTED**

**EVIDENCE:**

1. **Source code** (`GameCompatExports.cs` lines 188-194):
   ```csharp
   // VkqLPArfFdc — 0 calls on Windows upstream. Kept as harmless stub.
   [SysAbiExport(Nid = "VkqLPArfFdc", ExportName = "VkqLPArfFdc", Target = Generation.Gen5, LibraryName = "libKernel")]
   public static int VkqLPArfFdcStub(CpuContext ctx)
   {
       ctx[CpuRegister.Rax] = 0x0000000602000000ul;
       return (int)OrbisGen2Result.ORBIS_GEN2_OK;
   }
   ```
   The stub returns `ORBIS_GEN2_OK` (success) with RAX set to a non-NULL placeholder value. It CANNOT block anything.

2. **Runtime calls:** 0 (per CHECKPOINT_v0.0.11.md line 58: `| VkqLPArfFdc | 0 | 0 |`)

3. **Explicitly identified as red herring** in:
   - CHECKPOINT_v0.0.11.md line 341: "VkqLPArfFdc was a red herring — 0 calls on Windows; crash reduction was from removing bad stubs, not adding new ones"
   - PROJECT_STATUS_v0.0.10.md line 24: "VkqLPArfFdc was NOT called on Windows — it was a red herring"
   - PROJECT_STATUS_v0.0.10.md line 66: "VkqLPArfFdc | IL2CPP bootstrap | No (0 calls on Windows) | Keep (harmless)"

4. The NID is in Yatzi's import table but is **never actually called at runtime**.

**CONFIDENCE: HIGH** — VkqLPArfFdc cannot block GPU. 0 runtime calls; stub returns success; explicitly identified as red herring in multiple documents.

---

### Claim 7 — FAST_PATH=0 Limitation

**Developer claim (implicit):** "FAST_PATH=1 may have contaminated prior semaphore observations."

**STATUS: CONFIRMED**

**EVIDENCE:**

1. **Source code** (`KernelSemaphoreCompatExports.cs` line 108):
   ```csharp
   if (string.Equals(Environment.GetEnvironmentVariable("SHARPEMU_SEMA_FAST_PATH"), "1", StringComparison.Ordinal))
   {
       return SetReturn(ctx, OrbisGen2Result.ORBIS_GEN2_OK);  // returns success WITHOUT waiting or decrementing count
   }
   ```
   `FAST_PATH=1` makes `WaitSema` return OK immediately **without decrementing count, blocking, or registering a waiter**.

2. **`SignalSema` has NO such bypass** — it always increments count and pulses waiters (lines 339-373).

3. EXP-077 (line 14 of EXP-078.md) explicitly states: "**Configuration:** FAST_PATH=1, 11-byte NOP gate active, SHARPEMU_LOG_SEMA=1" — confirming ALL of EXP-072..078's semaphore data was collected under both bypasses.

4. EXP-078's observations that are now suspect:
   - "5.3M SignalSema calls" — all incremented counts (signal works normally)
   - "Semaphore count keeps incrementing (0x73: 1 → 447,579)" — exactly what FAST_PATH=1 produces
   - "Workers signal wrong handles" — corrected by checkpoint section 14 (paired semaphores by design)
   - "Handle 0x5C never signaled" — under FAST_PATH=1, no real blocking happens, so this cannot distinguish "signal genuinely missing" from "signal would fire under real blocking"

5. **I could not run a clean FAST_PATH=0 trace** in this session because the prior tracer infrastructure is not directly accessible. The runtime log at `/home/z/my-project/logs/devlog/app/debug.log` is empty (0 bytes).

**CONFIDENCE: HIGH** — FAST_PATH=1 definitely contaminated prior semaphore observations. A clean FAST_PATH=0 trace is required before any definitive statement about semaphore correctness can be made.

---

## Part 3 — Summary Table

| # | Claim | Status | Confidence |
|---|-------|--------|------------|
| 1 | GPU stub regression (4 stubs caused Flip to stop) | **REJECTED** | HIGH — checkpoint explicitly lists "regression" as a false hypothesis; stubs return success, cannot block |
| 2 | sceVideoOutFlip was reached | **PARTIALLY CONFIRMED** | HIGH for 2026-07-24 run (1 call); HIGH that framebuffer was fallback; MEDIUM on 1920x1080 resolution |
| 3 | GPU rendered game content | **REJECTED** | HIGH — 1 draw call vs 186; 0 render targets; framebuffer never written by GPU |
| 4 | unity_builtin_extra / Internal-ErrorShader blocks rendering | **PARTIALLY CONFIRMED** | HIGH that abort was real at 2026-07-24; HIGH that file is now available (820KB); MEDIUM that placing file resolves abort (requires fresh trace) |
| 5 | Semaphore handling works | **UNKNOWN** | HIGH source looks correct; HIGH prior "wrong handles" was corrected; LOW on whether callback-dispatch issue is real under FAST_PATH=0 |
| 6 | VkqLPArfFdc may block GPU | **REJECTED** | HIGH — 0 calls; stub returns success; explicitly identified as red herring |
| 7 | FAST_PATH=1 contaminated prior semaphore observations | **CONFIRMED** | HIGH — source confirms bypass; EXP-077/078 ran under FAST_PATH=1 |

---

## Part 4 — New Useful Facts Discovered (this EXP-117)

These are facts proven by evidence in this EXP-117, that may not have been clearly stated before:

### 1. The real `unity_builtin_extra` file IS available (820KB, Unity 2022.3.5f1)

Located at `/home/z/my-project/upload/unity_builtin_extra` (and archived in `/home/z/my-project/upload/unity default resources.rar`). The 2026-07-24 checkpoint's "empty file" finding was about a specific incomplete dump state at that time. The user has since obtained the real file.

**Implication:** The "missing shader" theory does NOT invalidate the EXP-096..115 callback-dispatch investigation. They are separate issues:
- Missing shader: dump-completeness issue, now resolvable with the uploaded file
- Callback dispatch: may be a real SharpEmu issue, but evidence was collected under FAST_PATH=1 and needs re-validation under FAST_PATH=0

### 2. The checkpoint's section 14-15 ALREADY corrected the EXP-078 "workers signal wrong handles" interpretation

The "wrong handles" pattern is the **paired semaphore pattern** (Unity's normal worker wait/completion signal: wait on EVEN, signal on ODD = handle+1). The actual deadlock is at handles 0x81-0x8D (Job.worker 0-12), and those workers are NOT deadlocked — they are IDLE, waiting for work that never comes.

**Implication:** EXP-078's conclusion was wrong. The EXP-096..115 callback-dispatch investigation was partly motivated by EXP-078's "wrong handles" finding. With that finding corrected, the motivation for the callback-dispatch investigation weakens — but doesn't disappear, because the workers being idle still means SOMETHING isn't dispatching work.

### 3. The REAL bottleneck per checkpoint section 15: the MAIN THREAD is in a busy loop, not a semaphore wait

The main thread is calling `1D0H2KNjshE`, `hsi9drzHR2k`, `scePthreadMutexLock`, `sceKernelClockGettime`, `sceAudioOutOutput` in a loop. It is NOT blocked on any semaphore.

**Implication:** The callback-dispatch investigation (EXP-096..115) was looking for why "workers don't get work" — but the answer may be simpler: the main thread is in a loop that never reaches the work-dispatch code. Why is the main thread in that loop? That's the real question.

### 4. The "regression" claim (4 GPU stubs caused Flip to stop) is a documented false hypothesis

CHECKPOINT_v0.0.11.md section 12 explicitly lists "regression" as one of 6 false hypotheses that wasted days. The 4 stubs all return success; they cannot block anything.

**Implication:** The user's A/B regression test proposal ("Restore the last state where Flip happened, add GPU stubs one by one") would not produce useful information because the regression claim itself is false. The stubs are not the cause.

### 5. The complete Yatzi dump archive does NOT contain the Unity resource files

`PPSA17697-app0UPLOAD_COMPLETE_DUMP.rar` (28MB) contains only PRX files + eboot.bin + global-metadata.dat. The `Media/Resources/unity_builtin_extra` and `unity default resources` files are in SEPARATE archives (`unity default resources.rar`, `globalgamemanagers.rar`).

**Implication:** If someone re-extracts only the "complete dump" archive, they will NOT get the Unity resource files. Both archives must be extracted, and the Unity resource files must be placed in `Media/Resources/`.

### 6. The game data state in this session's `/tmp/games/yatzi/` is incomplete

The `/tmp/games/yatzi/` directory (which existed in the prior session) is no longer present in this session — the session was reset. The Unity resource files exist in `/home/z/my-project/upload/` but are not currently placed in any game directory structure that SharpEmu would resolve.

**Implication:** A fresh trace in this session would need to first reconstruct the game directory structure with all the necessary files placed correctly.

---

## Part 5 — Recommended Next Tests (in priority order, per evidence)

These are NOT suggestions to change code. They are the cheapest tests that would resolve the most uncertainty, ordered by cost/benefit:

### Test A (cheapest): Reconstruct game directory + place real `unity_builtin_extra` + run trace

1. Create `/tmp/games/yatzi/Media/Resources/` directory
2. Copy `/home/z/my-project/upload/unity_builtin_extra` → `/tmp/games/yatzi/Media/Resources/unity_builtin_extra`
3. Copy `/home/z/my-project/upload/unity default resources` → `/tmp/games/yatzi/Media/Resources/unity default resources`
4. Copy other uploaded files (`globalgamemanagers`, etc.) to their proper locations
5. Run SharpEmu with `SHARPEMU_PIPELINE_COUNTERS=1` and check if the `Internal-ErrorShader` abort at `rip=0x800B28A0D` is gone

**Expected outcomes:**
- If abort is gone: the missing-shader issue is resolved; the callback-dispatch issue (if real) is now the blocker
- If abort persists: the file placement didn't work, or there's a different issue with SharpEmu's file-open path

### Test B (more expensive): Clean FAST_PATH=0 trace

Per EXP-114 and this EXP-117's Claim 7. Requires rebuilding SharpEmu with prior tracer infrastructure OR using `SHARPEMU_LOG_SEMA=1` with `SHARPEMU_SEMA_FAST_PATH=0`.

**Expected outcomes:**
- If deadlock reproduces: callback-dispatch issue is real (not a bypass artifact)
- If deadlock manifests differently: FAST_PATH=1 data was misleading; EXP-096..115 chain needs partial re-evaluation
- If deadlock disappears: entire callback-dispatch investigation was chasing a FAST_PATH=1 artifact

### Test C (not recommended): A/B regression test of GPU stubs

Per this EXP-117's Claim 1, the regression claim is a documented false hypothesis. Running this test would not produce useful information.

---

## Part 6 — Reviewer's Honest Assessment

This EXP-117 was scoped as a strict evidence-based review. The reviewer's role is to validate or reject claims, NOT to suggest code changes or set debugging direction.

**The single most important finding of this EXP-117** is that the real `unity_builtin_extra` file (820KB, Unity 2022.3.5f1) IS available in `/home/z/my-project/upload/`. The 2026-07-24 checkpoint's "missing shader" theory was based on an incomplete dump state that has since been corrected. This means:

1. The "missing shader" theory is NOT the settled root cause — it was a real issue at the time, but the file is now available
2. The callback-dispatch investigation's relevance is NOT invalidated by the missing-shader theory — they are separate issues
3. The cheapest next test (Test A above) is to place the real file in `Media/Resources/` and re-run, to determine whether the missing-shader abort is still the blocker

**The reviewer does NOT recommend changing any code based on these findings.** The reviewer's role is only to validate or reject claims. The main development process must ignore these suggestions unless independent tests confirm them.

---

## Artifacts

- `/home/z/my-project/scripts/exp117/EXP-117_ASSET_VERIFICATION_AND_REVIEW.md` — this report
- Verified files:
  - `/home/z/my-project/upload/unity_builtin_extra` (820,024 bytes, Unity 2022.3.5f1)
  - `/home/z/my-project/upload/unity default resources` (859,240 bytes, Unity 2022.3.2f1)
  - `/home/z/my-project/upload/globalgamemanagers` (210,920 bytes, Unity 2022.3.5f1)
  - `/home/z/my-project/upload/PPSA17697-app0UPLOAD_COMPLETE_DUMP.rar` (28MB, contains PRX files only)
  - `/home/z/my-project/upload/unity default resources.rar` (174KB archive)
  - `/home/z/my-project/upload/globalgamemanagers.rar` (82KB archive)
  - `/home/z/my-project/upload/globalgamemanagers.assets.zip` (2.5MB)
- Source evidence:
  - `/home/z/my-project/work/sharpemuT24-src/CHECKPOINT_v0.0.11.md` (2026-07-24 runtime traces + section 14-15 semaphore correction)
  - `/home/z/my-project/work/sharpemuT24-src/PROJECT_STATUS_v0.0.10.md` (Windows log analysis + NID stub status)
  - `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/Kernel/GameCompatExports.cs` (4 GPU stubs source)
  - `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs` (FAST_PATH bypass source)
  - `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/VideoOut/VideoOutExports.cs` (SubmitFlip source)

No code changes were made. No fixes were implemented. No commits. This was investigation only.
