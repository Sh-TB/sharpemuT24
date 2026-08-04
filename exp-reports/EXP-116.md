# EXP-116 — External Developer Claim Validation (GPU / Flip / Semaphore / Vulkan Import)

**Date:** 2026-08-03
**Goal:** Validate 6 external developer claims about GPU/flip/semaphore/Vulkan state. NO code changes. Investigation only.
**Sources of evidence used:**
- `/home/z/my-project/work/sharpemuT24-src/CHECKPOINT_v0.0.11.md` (2026-07-24, contains runtime traces from Yatzi runs with `SHARPEMU_PIPELINE_COUNTERS=1`)
- `/home/z/my-project/scripts/exp072/EXP-074.md` (2026-07-31, "no rendering reached" finding under FAST_PATH=1 + 11-byte NOP)
- `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/VideoOut/VideoOutExports.cs` (source code for SubmitFlip)
- `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/Kernel/GameCompatExports.cs` (source code for VkqLPArfFdc stub)
- `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs` (semaphore HLE source)
- `/tmp/games/yatzi/` filesystem (current game data state)

---

## ⚠️ CRITICAL LIMITATION — MUST BE STATED UPFRONT

**This entire validation is constrained by a major caveat that affects how much weight the findings carry:**

### The FAST_PATH=0 clean-trace gap

Per EXP-114's finding (this session): **nearly all prior semaphore runtime evidence (EXP-072..078) was collected under `SHARPEMU_SEMA_FAST_PATH=1` + an 11-byte NOP gate**, both of which change semaphore semantics:

- `FAST_PATH=1` makes `WaitSema` return OK immediately **without decrementing count, blocking, or registering a waiter** (line 108 of `KernelSemaphoreCompatExports.cs`)
- `SignalSema` has no such bypass — it always increments the count
- The 11-byte NOP gate was an experimental patch that enabled workers to reach `SignalSema` (otherwise they couldn't)

**Implication:** Any "workers signal wrong handles" or "handle 0x5C never signaled" observation from EXP-072..078 is an **artifact of the bypasses**, not necessarily real SharpEmu bugs. The callback-dispatch/WaitSema deadlock may not even reproduce the same way under clean `FAST_PATH=0` conditions.

The CHECKPOINT_v0.0.11.md findings (Claim 3, 4, 5, 6 below) come from a **different, earlier run** (2026-07-24) that did NOT have FAST_PATH=1 active — it reached `sceVideoOutSubmitFlip` under default configuration. So those findings are independent of the FAST_PATH contamination and carry full weight.

**I could not run a fresh trace in this session** because the prior tracer infrastructure (`_Exp*.cs` files) and the SharpEmu binary built with those tracers are not directly accessible in this session's filesystem. The runtime log at `/home/z/my-project/logs/devlog/app/debug.log` is empty (0 bytes).

---

## Claim 1 — "Import dispatch stall was fixed"

**Status: PARTIALLY CONFIRMED (with major caveat)**

### Evidence

**Before (early state, no fixes):**
- Per CHECKPOINT_v0.0.11.md section 21 and earlier: game stalled on `sceKernelWaitSema` deadlock before reaching VideoOut
- IL2CPP fake stubs returned NULL → 100,000+ unmapped memory recoveries before crash

**After (CHECKPOINT_v0.0.11.md, 2026-07-24 run):**
- Game progressed past the early stall
- Reached `Vulkan VideoOut ready` (checkpoint line 2247)
- Reached `sceVideoOutSubmitFlip` (1 direct call — checkpoint section 18, line 685)
- 1 frame presented (with `SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1` fallback)
- BUT: game still stalled afterward in audio/mutex loop

**After (EXP-074, 2026-07-31, under FAST_PATH=1 + 11-byte NOP):**
- 0 `sceVideoOutOpen` calls
- 0 `sceVideoOutSubmitFlip` calls
- 0 `sceGnmSubmitCommandBuffer` calls
- 0 `sceAgcDriverSubmitDcb` calls
- Game stalled on `WaitSema(0x5C)` spin

### Verdict

The "import dispatch stall was fixed" claim is **PARTIALLY CONFIRMED**:
- ✅ Progressed past the early IL2CPP fake-stub NULL cascade (FIXED)
- ✅ Progressed past the early WaitSema deadlock (FIXED, but only via `FAST_PATH=1` bypass — not a real fix)
- ❌ Did NOT progress to a stable rendering state — game still stalls (in audio/mutex loop per checkpoint, in WaitSema spin per EXP-074)
- ⚠️ The "fix" for the WaitSema stall was `FAST_PATH=1`, which masks the symptom rather than resolving the underlying callback-dispatch issue (per EXP-114)

**The stall behavior changed (NULL cascade gone, VideoOut reached in one configuration), but execution did NOT progress to stable first-frame rendering.** Different configurations reach different stall points; none reach a stable state.

---

## Claim 2 — "Semaphore handling is working correctly"

**Status: REJECTED (per EXP-114, with FAST_PATH caveat)**

### Evidence

**Source code analysis (EXP-114, this session):**

The semaphore HLE source (`KernelSemaphoreCompatExports.cs`) **looks correct** in its non-bypass paths:
- `WakePredicate` (lines 154-168) acquires tokens atomically inside `lock(semaphore.Gate)`
- `SignalSema` (lines 351-358) increments count under lock and pulses both guest and host waiters
- Spurious-wake handling: `WakePredicate` re-checks count under lock; if insufficient, returns false (re-blocks)
- Handle validation: returns `ORBIS_GEN2_ERROR_NOT_FOUND` for unknown handles

**BUT — runtime evidence contradicts "working correctly":**

Per EXP-074 (2026-07-31, under `FAST_PATH=1` + 11-byte NOP):
- WaitSema calls: 42 (workers on handle `0x5C`) + 6 (main thread on handles `0x5D, 0x5F, 0x61, 0x63, 0x65, 0x67`)
- SignalSema calls: 13,141 — **NONE on handle 0x5C** (the handle workers wait on)
- Handle 0x5C was never released

Per EXP-078 (5.7M-line sema trace, under same bypasses):
- 5.3M SignalSema calls, all on odd handles (`0x73, 0x67, 0x6D, ...`)
- 0 signals on even handles (worker semaphores `0x5C, 0x5E, 0x60, ...`)
- Counts grew unboundedly (e.g., `0x73`: 1 → 447,579)

### Why this evidence is unreliable

Per EXP-114:
- `FAST_PATH=1` makes `WaitSema` return OK immediately **without decrementing count**
- `SignalSema` has no bypass — it always increments
- So under `FAST_PATH=1`, **counts grow without bound by design** — this is the documented behavior of the bypass, not a bug
- The "workers signal wrong handles" observation is an artifact: workers signal whatever handle the game's code tells them to signal (`[rbx+0xB0]`), which happens to be odd because of allocation order, not because of any SharpEmu odd/even bifurcation
- Handle allocation in SharpEmu is purely sequential (`_nextSemaphoreHandle` starts at 1, increments by 1: handles 2, 3, 4, 5, ...)

### Verdict

**REJECTED.** The source code is correct in non-bypass paths, but:
1. All runtime evidence was collected under `FAST_PATH=1`, which changes semantics in ways that make "workers signal wrong handles" look like a bug when it's actually the bypass working as documented
2. The blocked handle (`0x5C`) was never released under any configuration tested — but this is expected under `FAST_PATH=1` (no real blocking happens) and cannot be reliably tested without a clean `FAST_PATH=0` run

**The claim "semaphore handling is working correctly" cannot be confirmed with the available runtime evidence.** A clean `FAST_PATH=0` trace is required to make any definitive statement. The source code review (EXP-114) found no obvious bug, but absence of bug in source review is not the same as confirmed correctness at runtime.

---

## Claim 3 — "sceVideoOutFlip was reached"

**Status: PARTIALLY CONFIRMED (reached, but with critical qualifiers)**

### Evidence (CHECKPOINT_v0.0.11.md section 18, 2026-07-24 run)

**sceVideoOutSubmitFlip WAS reached** — 1 direct call recorded by `SHARPEMU_PIPELINE_COUNTERS=1`:

| Function | Dreaming Sarah (working) | Yatzi |
|----------|--------------------------|-------|
| VideoOutOpen | 1 | 1 |
| VideoOutRegisterBuffers2 | 1 | 1 |
| **VideoOutSubmitFlip (direct)** | 0 (uses DCB-embedded) | **1** |
| VideoOutAddFlipEvent | 84 | 2 |

### Caller RIP, resolution, buffer address, framebuffer address

From checkpoint section 18:
- **Buffer address:** `0x10CA0000` (registered via `sceVideoOutRegisterBuffers2`, then flipped)
- **Resolution:** Not explicitly recorded in checkpoint, but the format was registered (width/height/pitch stored in `displayBuffer`)
- **Framebuffer address:** `0x10CA0000` (same as buffer address — the registered display buffer)

### Whether the address points to real game rendering memory

**NO.** Per checkpoint section 19:
- The `vk.flip_capture_failed` warning showed `queue=dcb.graphics addr=0x0000000010CA0000 found=False initialized=False`
- `_guestImages` (the "actual image resource" dictionary) was empty — Yatzi never created a single `_guestImages` entry
- GIMG-CREATE events for Yatzi: **0** (vs 3 for Dreaming Sarah)
- The address `0x10CA0000` was registered as a valid flip target (in `_availableGuestImages`) but never had a real Vulkan image created for it (not in `_guestImages`)
- Yatzi "just flips before ever rendering, so it never reaches that path" (the AGC `render_target_new` path that should populate `_guestImages`)

### With fallback enabled (`SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1`)

- A placeholder B8G8R8A8Unorm Vulkan image was created lazily in `ExecuteOrderedGuestFlip`
- Cleared to opaque black via `CmdClearColorImage((0,0,0,1))`
- Frame #1 was presented (black, but a real frame)

### Verdict

**PARTIALLY CONFIRMED:**
- ✅ `sceVideoOutSubmitFlip` was reached (1 call, runtime counter)
- ✅ Buffer address `0x10CA0000` was registered and flipped
- ❌ The address did NOT point to real game rendering memory — `_guestImages` was empty, no GIMG-CREATE events
- ⚠️ With fallback, a black placeholder image was created and presented — but this is a synthetic test pattern, not game content
- ⚠️ This finding is from the 2026-07-24 checkpoint run; the 2026-07-31 EXP-074 run (under `FAST_PATH=1`) recorded 0 SubmitFlip calls

**The "sceVideoOutFlip was reached" claim is true in one configuration (2026-07-24) and false in another (2026-07-31, FAST_PATH=1).** Neither configuration produced a real game frame.

---

## Claim 4 — "A frame was captured"

**Status: PARTIALLY CONFIRMED (a frame was presented, but it's a synthetic black test pattern, NOT real game content)**

### Evidence (CHECKPOINT_v0.0.11.md section 19)

**With `SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1`:**
- 1 frame presented (frame #1, black)
- `flip_fallback_created` events: 1 (the fallback created the image)
- `GIMG-CREATE` events: 1 (path=fallback_flip) — the fallback path created the Vulkan image
- `flip_capture_failed` events: 0 (fallback prevented the failure)

**Without fallback:**
- 0 frames produced
- 1 `flip_capture_failed` event (image lookup failed)
- 0 `GIMG-CREATE` events

### Real game content vs test pattern

**Test pattern (synthetic), NOT real game content.**

Evidence:
- The fallback image was created by `CmdClearColorImage((0,0,0,1))` — opaque black
- No draw calls were ever submitted to render into this image
- No triangles were ever drawn
- No GPU command buffer was ever submitted with rendering commands
- The image is a placeholder created to make the flip succeed, not actual game rendering

### Draw calls, triangle count, GPU command submission, framebuffer writes

From CHECKPOINT_v0.0.11.md section 18 (side-by-side comparison):

| Function | Dreaming Sarah (working) | Yatzi |
|----------|--------------------------|-------|
| AgcDriverSubmitDcb | 84 | **1** |
| AgcDcbDrawIndexAuto | 66 | **1** |
| AgcDcbDrawIndexOffset | 120 | **0** |
| AgcCreateShader | 99 | 36 |
| AgcCreatePrimState | 378 | 2 |
| Frames produced | 90 | **0** (without fallback) / **1** (with fallback, black) |

**Yatzi's GPU activity:**
- 1 `sceAgcDriverSubmitDcb` call (vs 84 for Dreaming Sarah) — minimal command buffer submission
- 1 `sceAgcDcbDrawIndexAuto` call (vs 66) — minimal draw call
- 0 `sceAgcDcbDrawIndexOffset` calls (vs 120) — no indexed draws
- 36 `sceAgcCreateShader` calls (vs 99) — some shader creation, but incomplete
- 2 `sceAgcCreatePrimState` calls (vs 378) — minimal pipeline state

**Triangle count:** Not directly recorded, but with only 1 `DrawIndexAuto` call and 0 `DrawIndexOffset` calls, the total triangle count is at most a handful — not enough for real game rendering.

**Framebuffer writes:** The framebuffer at `0x10CA0000` was never written to by GPU rendering. The only "write" was the fallback's `CmdClearColorImage` clear-to-black.

### Verdict

**PARTIALLY CONFIRMED:**
- ✅ A frame was presented (1 frame, with fallback)
- ❌ The frame was a synthetic black test pattern, NOT real game content
- ❌ Draw call count: 1 (vs 66+120=186 for working game) — insufficient for real rendering
- ❌ Triangle count: ~0 (no indexed draws, 1 auto-draw)
- ❌ GPU command buffer submission: 1 (vs 84 for working game)
- ❌ Framebuffer was never written by GPU rendering — only cleared to black by fallback

**The "frame was captured" claim is technically true (a frame was presented) but misleading — it's a synthetic black test pattern, not game content.** Calling this "a captured frame" without the qualifier "synthetic black fallback" would be deceptive.

---

## Claim 5 — "GPU subsystem was reached"

**Status: PARTIALLY CONFIRMED (partial initialization reached, but render pipeline incomplete)**

### Evidence — stage-by-stage trace

Per CHECKPOINT_v0.0.11.md sections 18, 19, 20:

| Stage | Reached? | Evidence |
|-------|----------|----------|
| Game code → GPU initialization | ✅ YES | `sceAgcDriverRegisterOwner` auto-init ran; `AgcInit` counter: 1 (same as Dreaming Sarah) |
| Memory allocation | ✅ YES | 2 `sceKernelAllocateDirectMemory` calls; 6 `sceKernelMapDirectMemory` calls (per EXP-077) |
| Command buffer creation | ⚠️ PARTIAL | 1 `sceAgcDriverSubmitDcb` call (vs 84 for working game) — minimal |
| Shader creation | ⚠️ PARTIAL | 36 `sceAgcCreateShader` calls (vs 99 for working game) — incomplete |
| Pipeline state | ⚠️ MINIMAL | 2 `sceAgcCreatePrimState` calls (vs 378 for working game) — minimal |
| Draw submission | ⚠️ MINIMAL | 1 `sceAgcDcbDrawIndexAuto` (vs 66), 0 `sceAgcDcbDrawIndexOffset` (vs 120) |
| Render target creation | ❌ NO | 0 `GIMG-CREATE` events (vs 3 for working game) — render target never created |
| Flip | ⚠️ WITH FALLBACK | 1 `sceVideoOutSubmitFlip` (vs 0 direct for working game, which uses DCB-embedded) — but only succeeded with fallback image |

### Where execution actually stops

Per CHECKPOINT_v0.0.11.md section 20, the **actual blocker** is at `rip=0x800B28A0D`:

```asm
0x800B28A08:  xor      eax, eax        ; RAX = 0
0x800B28A0A:  xor      r12d, r12d      ; R12 = 0 (INTENTIONAL!)
0x800B28A0D:  cmp      qword ptr [r12 + 0x38], 0    ; FAULT — reading NULL+0x38
0x800B28A13:  jne      0x800b27dd0     ; jump if [0x38] != 0 (impossible)
0x800B28A19:  jmp      0x800b289ed     ; else error path
0x800B28A1B:  call     0x801938160     ; abort handler
0x800B28A20:  ud2                       ; UNDEFINED INSTRUCTION — abort()
```

This is **Unity's assertion abort pattern** — when an invariant fails, the code jumps to a crash site that intentionally NULL-derefs to trigger SIGSEGV.

The caller analysis (section 20) showed:
- A shader lookup function at `0x800aba330` returned NULL
- The lookup was for the string `"Internal-ErrorShader.shader"` (read from guest address `0x801BB0024`)
- This is Unity's built-in **error shader** — used as fallback when a regular shader fails to load

### Root cause of the abort

Per CHECKPOINT_v0.0.11.md section 20-21:
- Yatzi's `Media/Resources/unity_builtin_extra` file is **0 bytes (EMPTY)**
- Yatzi's `Media/Resources/unity default resources` file is **0 bytes (EMPTY)**
- These files normally contain Unity's entire built-in shader library (100-500KB)
- Without them, the `Internal-ErrorShader` lookup returns NULL → Unity aborts

### Verdict

**PARTIALLY CONFIRMED:**
- ✅ GPU initialization started (`AgcInit` ran)
- ✅ GPU memory allocated (`sceKernelAllocateDirectMemory`)
- ✅ Some command buffers submitted (1 `sceAgcDriverSubmitDcb`)
- ✅ Some shaders created (36 `sceAgcCreateShader`)
- ❌ Render target never created (0 `GIMG-CREATE` events)
- ❌ Draw pipeline incomplete (1 draw call vs 186 for working game)
- ❌ Flip only succeeded with synthetic fallback image
- ❌ Unity aborted at `rip=0x800B28A0D` due to missing `Internal-ErrorShader` (empty `unity_builtin_extra`)

**The GPU subsystem was partially reached — initialization and some shader/pipeline creation ran, but the render pipeline is incomplete and Unity aborts before producing real frames due to missing built-in shader resources (a game data issue, not a SharpEmu code issue).**

### Caveat on the game data state

In THIS session's filesystem (`/tmp/games/yatzi/`), the `Media/Resources/` directory **does not exist at all** — neither `unity_builtin_extra` nor `unity default resources` are present (not even as 0-byte files). The full `Media/` directory contains only:
- `Media/Modules/Il2cppUserAssemblies.prx`
- `Media/Metadata/global-metadata.dat`

Other expected files (`Media/globalgamemanagers`, `Media/globalgamemanagers.assets`, `Media/globalgamemanagers.assets.resS`, `Media/level0`, `Media/sharedassets0.assets`) are also absent. **The game data in this session is incomplete compared to what the 2026-07-24 checkpoint analyzed.** I cannot re-verify the empty-`unity_builtin_extra` finding in this session's filesystem because the file isn't here.

---

## Claim 6 — "VkqLPArfFdc Vulkan import may block GPU"

**Status: REJECTED (VkqLPArfFdc was a red herring)**

### Evidence

**Source code** (`GameCompatExports.cs` lines 188-194):

```csharp
// VkqLPArfFdc — 0 calls on Windows upstream. Kept as harmless stub.
[SysAbiExport(Nid = "VkqLPArfFdc", ExportName = "VkqLPArfFdc", Target = Generation.Gen5, LibraryName = "libKernel")]
public static int VkqLPArfFdcStub(CpuContext ctx)
{
    ctx[CpuRegister.Rax] = 0x0000000602000000ul;
    return (int)OrbisGen2Result.ORBIS_GEN2_OK;
}
```

The stub:
- Returns `ORBIS_GEN2_OK` (success)
- Sets RAX to `0x0000000602000000` (a non-NULL placeholder value)
- Does NOT block

### Callers, when called, return value usage, whether failure changes flow

Per CHECKPOINT_v0.0.11.md:
- **VkqLPArfFdc call count: 0** (line 58: `| VkqLPArfFdc | 0 | 0 |`)
- "VkqLPArfFdc was a red herring — 0 calls on Windows; crash reduction was from removing bad stubs, not adding new ones" (line 341)
- "VkqLPArfFdc was NOT called on Windows — it was a red herring" (PROJECT_STATUS_v0.0.10.md line 24)

**The NID is in Yatzi's import table but is never actually called at runtime.** Even if it were called, the stub returns success with a non-NULL value, so it would not block anything.

### Static analysis — does failure change execution flow?

Since the stub always returns `ORBIS_GEN2_OK` (success) with a non-NULL RAX, the caller would treat it as successful. There is no failure path. The stub cannot block the GPU.

### Why the claim was made (and why it's wrong)

The GOLDEN_BASELINE.md (line 50) lists "VkqLPArfFdc NID unresolved" as a blocker for Yatzi, but this was based on the NID being in the import table — not on it actually being called. The checkpoint's runtime tracing proved it's never called.

### Verdict

**REJECTED.** VkqLPArfFdc:
- Has 0 runtime calls (per checkpoint line 58)
- Even if called, returns success with non-NULL value
- Cannot block GPU rendering
- Was explicitly identified as a red herring in the checkpoint

**The claim "VkqLPArfFdc Vulkan import may block GPU" is rejected by runtime evidence (0 calls) and source code analysis (stub returns success).**

---

## Final Section — New Useful Facts Discovered

These are facts proven by evidence in this EXP-116, that may not have been clearly stated before:

### 1. The "sceVideoOutSubmitFlip reached" finding is configuration-dependent

- **2026-07-24 checkpoint run (default config, no FAST_PATH):** `sceVideoOutSubmitFlip` was reached (1 call), but the framebuffer address `0x10CA0000` had no real Vulkan image — `_guestImages` was empty, `flip_capture_failed` fired
- **2026-07-31 EXP-074 run (FAST_PATH=1 + 11-byte NOP):** 0 `sceVideoOutSubmitFlip` calls — game stalled earlier in WaitSema spin

**Implication:** Any claim about whether the GPU/flip layer is reached depends on which configuration was tested. The two configurations reach different stall points.

### 2. The actual blocker (per 2026-07-24 checkpoint) is missing Unity built-in shaders, NOT semaphore sync

- Unity aborts at `rip=0x800B28A0D` (intentional NULL deref) because the `Internal-ErrorShader.shader` lookup returns NULL
- The lookup fails because `Media/Resources/unity_builtin_extra` is 0 bytes (empty)
- This is a **game data issue**, not a SharpEmu code issue
- The fallback image fix (`SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1`) makes the flip succeed with a black frame, but does NOT fix the underlying missing-shader abort

**Implication:** The entire EXP-072..078 + EXP-096..115 callback-dispatch investigation may have been investigating a **consequence** (workers not producing frames) of a **different root cause** (missing Unity built-in shaders causing Unity to abort before reaching the render loop). This is consistent with EXP-113's trajectory concern that "EXP-089 ≈ EXP-112 in substance" — both were investigating downstream symptoms of an upstream data issue.

### 3. Yatzi's GPU activity is minimal but non-zero

- 1 `sceAgcDriverSubmitDcb` (vs 84 for working game)
- 1 `sceAgcDcbDrawIndexAuto` (vs 66)
- 0 `sceAgcDcbDrawIndexOffset` (vs 120)
- 36 `sceAgcCreateShader` (vs 99)
- 2 `sceAgcCreatePrimState` (vs 378)
- 0 `GIMG-CREATE` events (vs 3)

**Implication:** The GPU subsystem does initialize and accept some commands, but the render pipeline never reaches the "render into target" stage. The abort happens before any real rendering.

### 4. The 0xC0DEC0DECAFEBA00 "magic marker" is SharpEmu's TLS stack canary, NOT Unity's error state marker

- Per CHECKPOINT_v0.0.11.md section 20: the value appears 5 times in SharpEmu source, all as `StackCheckGuardValue` / `StackChkGuardValue` / `__stack_chk_guard`
- It is written to `tlsBase + 0x28` (the standard `__stack_chk_guard` location)
- The previous interpretation ("Unity's error state magic marker") was WRONG
- The reason RCX has this value at the fault is because RAX was just XOR'd to 0, and RCX happens to hold the TLS canary loaded earlier for stack check validation

**Implication:** Any analysis that interpreted 0xC0DEC0DECAFEBA00 as a Unity error signal needs to be re-evaluated. This is a normal stack-canary value, not an error indicator.

### 5. The game data in this session's filesystem is incomplete

- `/tmp/games/yatzi/Media/Resources/` directory does NOT exist (no `unity_builtin_extra`, no `unity default resources`)
- `/tmp/games/yatzi/Media/` contains only `Modules/Il2cppUserAssemblies.prx` and `Metadata/global-metadata.dat`
- Other expected files (`globalgamemanagers*`, `level0`, `sharedassets0.assets`) are also absent

**Implication:** I cannot re-verify the empty-`unity_builtin_extra` finding in this session. The 2026-07-24 checkpoint finding still stands as historical evidence, but if a fresh trace were run in this session, the missing files might cause an even earlier failure (file-not-found errors during Unity's resource loading).

### 6. The FAST_PATH=0 clean-trace gap is the single most important limitation

- ALL prior semaphore runtime evidence (EXP-072..078) was collected under `FAST_PATH=1` + 11-byte NOP
- Under `FAST_PATH=1`, `WaitSema` returns OK immediately without decrementing count — counts grow without bound by design
- The "workers signal wrong handles" observation is an artifact of the bypass, not a real SharpEmu bug
- The callback-dispatch/WaitSema deadlock may not reproduce the same way under clean `FAST_PATH=0` conditions
- **A clean `FAST_PATH=0` trace is required before any definitive statement about semaphore correctness can be made**

**Implication:** This must be stated explicitly in the maintainer summary (EXP-115) as a limitation that affects how much weight the EXP-072..078 + EXP-096..115 callback-dispatch chain should carry.

---

## Summary Table

| # | Claim | Status | Key Evidence |
|---|-------|--------|--------------|
| 1 | Import dispatch stall was fixed | PARTIALLY CONFIRMED | NULL cascade gone; VideoOut reached in one config (2026-07-24); but game still stalls (audio/mutex loop or WaitSema spin depending on config) |
| 2 | Semaphore handling is working correctly | REJECTED | Source code looks correct (EXP-114); but all runtime data was under FAST_PATH=1 bypass, making observations unreliable; blocked handle 0x5C never released under any config |
| 3 | sceVideoOutFlip was reached | PARTIALLY CONFIRMED | 1 SubmitFlip call in 2026-07-24 run; buffer at 0x10CA0000; but no real Vulkan image (empty _guestImages); 0 calls in 2026-07-31 FAST_PATH=1 run |
| 4 | A frame was captured | PARTIALLY CONFIRMED | 1 frame presented WITH fallback (black); 0 frames without fallback; frame is synthetic black test pattern, NOT game content; 1 draw call vs 186 for working game |
| 5 | GPU subsystem was reached | PARTIALLY CONFIRMED | AgcInit ran; 1 DCB submit; 36 shaders created; but 0 render targets; Unity aborts at rip=0x800B28A0D due to missing Internal-ErrorShader (empty unity_builtin_extra) |
| 6 | VkqLPArfFdc Vulkan import may block GPU | REJECTED | 0 runtime calls; stub returns success with non-NULL value; explicitly identified as red herring in checkpoint |

---

## Recommended Next Test

**Run a clean `FAST_PATH=0` trace** to resolve the single most important limitation identified in this EXP-116 and EXP-114.

Specifically:
1. Rebuild SharpEmu with prior tracer infrastructure (the `_Exp*.cs` files from EXP-095..109) re-integrated, OR use the existing `SHARPEMU_LOG_SEMA=1` env var
2. Run Yatzi with `SHARPEMU_SEMA_FAST_PATH=0` (no bypass) and `SHARPEMU_LOG_SEMA=1`
3. Capture: which handles are waited on, which are signaled, whether the blocked handle is ever released, whether the callback `0x804FA1FE0` is ever invoked
4. Compare against the FAST_PATH=1 data from EXP-078

**Expected outcomes:**
- If the deadlock reproduces the same way under `FAST_PATH=0`: the callback-dispatch issue is real and not a bypass artifact — proceed with the maintainer question from EXP-115
- If the deadlock manifests differently (e.g., a different handle blocks, or the callback IS invoked): the FAST_PATH=1 data was misleading and the EXP-096..115 chain needs partial re-evaluation
- If the deadlock disappears entirely (game progresses further): the entire callback-dispatch investigation was chasing a FAST_PATH=1 artifact

**This test is the natural next step before posting the maintainer summary (EXP-115).** The summary should either include the results of this test, or explicitly state that this test could not be run and that the EXP-072..078 + EXP-096..115 chain may need re-validation under `FAST_PATH=0`.

---

## Artifacts

- `/home/z/my-project/scripts/exp116/EXP-116_CLAIM_VALIDATION.md` — this report
- Source evidence:
  - `/home/z/my-project/work/sharpemuT24-src/CHECKPOINT_v0.0.11.md` (2026-07-24 runtime traces)
  - `/home/z/my-project/scripts/exp072/EXP-074.md` (2026-07-31 runtime traces)
  - `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/VideoOut/VideoOutExports.cs` (SubmitFlip source)
  - `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/Kernel/GameCompatExports.cs` (VkqLPArfFdc stub source)
  - `/home/z/my-project/work/sharpemuT24-src/src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs` (semaphore HLE source)
- `/tmp/games/yatzi/` (current game data — incomplete; `Media/Resources/` directory absent)

No code changes were made. No fixes were implemented. This was investigation only.
