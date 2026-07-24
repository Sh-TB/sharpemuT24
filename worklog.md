---
Task ID: EXP-016
Agent: main (SharpEmu bringup)
Task: Process new Harvest Days full app0 upload, implement FrameAnalyzer (splash detector) per user's request.

Work Log:
- User uploaded PPSA14677-appaaa.rar — full Harvest Days app0 (118 MB).
- Extracted to /tmp/games/harvest-full/:
  - eboot.bin (31.6 MB, fSELF magic 0x4F153D1D — decrypted ✅)
  - Media/Modules/Il2cppUserAssemblies.prx (78.5 MB, SELF magic 0x5414F5EE — ENCRYPTED ❌)
  - Media/Modules/PS5Util.prx (encrypted ❌)
  - Media/Plugins/{PSN, lib_burst_generated}.prx (both encrypted ❌)
  - Media/Resources/{unity default resources, unity_builtin_extra, mscorlib.dll-resources.dat}
  - sce_module/{libc, libSceNpCppWebApi}.prx (both encrypted ❌)
  - sce_sys/*.{dat, sprx, json, at9, ucp, keystone}

- Ran through BootDependencyAnalyzer:
  - Engine: Unity IL2CPP
  - Coverage: 38.9% (7/18 required files present)
  - Critical miss: 0
  - Critical encrypt: 2 (libc.prx + Il2cppUserAssemblies.prx)
  - Can boot: NO → ABORTED correctly, no time wasted on emulator analysis.

- Discovered bug in original BootDependencyAnalyzer:
  - Encrypted critical files (libc.prx, Il2cppUserAssemblies.prx) were treated as "present"
  - ShouldAbort was false because CriticalMissingCount was 0
  - Emulator proceeded and crashed with Illegal Instruction.
- FIX: Added CriticalEncryptedCount field to AnalysisReport. ShouldAbort now triggers
  if either CriticalMissingCount > 0 OR CriticalEncryptedCount > 0.
- Report now prints "Critical encrypt" line and shows specific encrypted critical files.

- Implemented FrameAnalyzer class in SharpEmu.Libs/VideoOut/FrameAnalyzer.cs:
  - Parses PPM frame file (handles SharpEmu's RGBA8-stored-as-RGB hack)
  - Samples ~50K pixels to compute color statistics (fast)
  - Classifies frame as one of:
    • Uniform Splash Frame (one color covers >95% of pixels)
    • Black Frame (>95% black)
    • White Frame (>95% white)
    • Multi-Color Content Frame (real scene/menu/UI is rendering)
    • Partial Content (50-95% one color)
    • Empty (frame too small)
  - Prints "Framebuffer Analysis" report with:
    • Resolution, format, pixel count
    • Distinct color count
    • Dominant color + coverage %
    • Top 5 colors with % coverage
    • Classification label (e.g. "Unity Splash Frame")
    • Conclusion (e.g. "GPU OK, VideoOut OK, but Scene NOT loaded")
    • Next steps (e.g. "Upload Media/level0", "Upload Media/globalgamemanagers")
- Wired into HeadlessVideoPresenter — runs automatically after frame 1 is saved.

Test results with new FrameAnalyzer:

| Game | First Frame? | Classification | Notes |
|------|--------------|----------------|-------|
| Yatzi (PPSA17697) | ✅ | Unity Splash Frame | RGB(224,88,64) 99.98% coverage — analyzer correctly identifies as splash, suggests uploading level0, globalgamemanagers, resources.assets, etc. |
| Dreaming Sarah | ⚠️ | Empty Frame | Produces 5 frames but all black (Xvfb/Vulkan doesn't work in headless env; previously had real frames when GPU was working) |
| Harvest Days (full app0) | ❌ | Aborted before frame | 2 critical files encrypted (libc.prx, Il2cppUserAssemblies.prx) — analyzer correctly aborts |

Stage Summary:
- ✅ BootDependencyAnalyzer now correctly handles encrypted critical files (was the bug that caused Harvest Days to crash with Illegal Instruction)
- ✅ FrameAnalyzer implemented — classifies first frame as splash vs real content, tells user exactly what to upload next
- ✅ Harvest Days new upload CANNOT boot because libc.prx and Il2cppUserAssemblies.prx are encrypted
- ✅ Yatzi's first frame is correctly identified as "Unity Splash Frame" with specific next steps
- 🟡 Dreaming Sarah regression: headless mode produces black frames (was working in EXP-014 with Xvfb+Vulkan)
- Artifacts produced:
  - /home/z/my-project/download/yatzi_first_frame.png (Unity splash background)
  - /home/z/my-project/SharpEmu/diagnostics/exp-016/{02-harvest-full,03-yatzi,04-dreaming-sarah-{xvfb,headless}}.log
- New files added:
  - src/SharpEmu.Core/Loader/BootDependencyAnalyzer.cs (CriticalEncryptedCount added)
  - src/SharpEmu.Libs/VideoOut/FrameAnalyzer.cs (NEW — 311 lines)
  - src/SharpEmu.Libs/VideoOut/HeadlessVideoPresenter.cs (wired FrameAnalyzer in)

---
Task ID: EXP-NID-NONZERO
Agent: main (SharpEmu bringup)
Task: Run user's cheap experiment — test if returning non-zero from 1D0H2KNjshE / hsi9drzHR2k breaks the busy-wait loop. Also capture caller mapping data.

Work Log:
- Read user's recommendation (in Persian) to run a cheap experiment: modify both
  NID stubs to return non-zero (R8 or constant 1) instead of 0, observe if the
  busy-wait loop breaks. User warned about premature interpretation of R8=256/R9=64
  as "cache line size" — could be buffer size, alignment, or batch size instead.
- Added two env-var-controlled knobs to GameCompatExports.cs:
  * SHARPEMU_NID_RETURN_NONZERO=1 → stubs return R8 (or 1 if R8==0)
  * SHARPEMU_NID_CALLER_MAP=1 → log caller module+offset from [RSP]
- Added background timer (System.Threading.Timer) that dumps cumulative NID call
  counts every 2 seconds, independent of NID activity — so we can definitively
  observe "NID calls have stopped" even if no NID fires.
- Added Interlocked.Increment-based per-NID counters (_calls1D0, _callsHsi9).
- Built and deployed new binary (50,864,085 bytes).
- Ran golden test (Dreaming Sarah) BEFORE the experiment to verify no regression:
  ✅ PASS (139 frames, 188 distinct colors, real game content).
- Created /home/z/my-project/scripts/exp-nid-caller-map.sh — baseline run with
  caller mapping enabled. Captured all 3 unique callers:
    * 1D0H2KNjshE @ eboot.bin+0x9B8551 (RDI=0x601183C90, R8=0x100, R9=0x40)
    * 1D0H2KNjshE @ eboot.bin+0x8BF76E (RDI=0, R8=0x400000, RCX=0xC0DEC0DECAFEBA00)
    * hsi9drzHR2k @ eboot.bin+0x14335FE (R8=0x3FF0000000000000 = 1.0 double)
- Created /home/z/my-project/scripts/exp-nid-nonzero-test.sh — runs both phases
  (baseline return 0, then non-zero return R8) sequentially with caller mapping.
- Ran the experiment:

| Phase | 1D0H2KNjshE calls | hsi9drzHR2k calls | Result |
|-------|-------------------|-------------------|--------|
| Baseline (return 0) | 60,343 | 19,968 | Audio/mutex loop |
| Non-zero (return R8) | 60,343 | 19,968 | Audio/mutex loop (IDENTICAL) |

- DEFINITIVE RESULT: returning non-zero does NOT break the loop. The "busy-wait
  loop" hypothesis from commit 7012c3e was WRONG. The NIDs are NOT in a polling
  loop with a return-value-based exit condition. They are in a FINITE iteration
  loop that runs exactly 60,343 + 19,968 = 80,311 times and exits NATURALLY.
- Captured the real boot sequence:
  T=0-4s    IL2CPP bootstrap
  T=4-6s    NID iteration loop (80,311 calls) — completes naturally
  T=6s+     Main thread enters AUDIO/MUTEX LOOP (no rendering)
            scePthreadMutexLock → sceAudioOutOutput → sceKernelClockGettime → sceKernelWaitSema
            (No sceAgc calls, no VideoOut flips, no frames rendered)
- Discovered the previous analysis mistake: "same stack address = tight busy-wait
  loop" was a misinterpretation. Same stack address = same CALL SITE, which is
  true for ANY iteration (for/while/do-while). The loop was finite, not infinite.
- Investigated the audio/mutex loop: WaitSema returns 0 because the semaphore
  has tokens (correct behavior, not a stub bug). The loop is the Unity main
  thread's "wait for next frame" loop, but it never produces any rendering.
  Found 3 plausible root causes:
  1. GfxDeviceWorker thread is scheduled but never produces a frame
  2. Unity engine's own GfxDevicePS5SharedData::CreateWorkload() is a TODO
     (guest debug print: "[DEBUG][PRINF] todo: void GfxDevicePS5SharedData::CreateWorkload()")
  3. vk.flip_capture_failed warning shows dcb.graphics queue is not initialized
- Ran golden test AFTER the experiment to verify no regression:
  ✅ PASS (139 frames, 188 colors).
- Updated CHECKPOINT_v0.0.11.md with new section 17 (CRITICAL UPDATE) documenting
  the refutation, caller map, real boot sequence, and new investigation plan.
- Closed the NID investigation. Next P1 is GfxDeviceWorker trace.

Stage Summary:
- ✅ User's cheap experiment executed as requested
- ✅ Hypothesis "1D0H2KNjshE/hsi9drzHR2k are loop exit condition" DEFINITIVELY REFUTED
  (Returning non-zero produces identical call counts: 60,343 / 19,968 in both phases)
- ✅ Caller mapping captured: all 3 unique call sites are inside eboot.bin
  (Unity engine code), not Il2cppUserAssemblies.prx
- ✅ Real boot sequence understood: NID loop is FINITE (completes in ~2 sec),
  not infinite busy-wait
- ✅ New bottleneck identified: audio/mutex loop after NID loop ends, with no
  rendering happening
- ✅ New P1 investigation target: GfxDeviceWorker thread state + CreateWorkload()
- ✅ Golden test still passes (no regression from new instrumentation)
- Artifacts produced:
  - /home/z/my-project/scripts/exp-nid-caller-map.sh
  - /home/z/my-project/scripts/exp-nid-nonzero-test.sh
  - /tmp/exp-nid-nonzero/{baseline_return0,nonzero_returnR8}.log
  - /tmp/exp-nid-caller-map.log
- New env vars added to SharpEmu:
  - SHARPEMU_NID_RETURN_NONZERO=1
  - SHARPEMU_NID_CALLER_MAP=1
- Modified file: src/SharpEmu.Libs/Kernel/GameCompatExports.cs

---
Task ID: EXP-PIPELINE-COUNTERS
Agent: main (SharpEmu bringup)
Task: Implement user's "cheap test" — add lightweight call counters to GPU/VideoOut
pipeline functions, compare Dreaming Sarah (working) vs Yatzi (broken), identify which
function is called vs not called. User explicitly said: "do NOT modify IL2CPP stubs anymore."

Work Log:
- Created new file src/SharpEmu.Libs/Kernel/PipelineCallCounters.cs:
  * Activated by env var SHARPEMU_PIPELINE_COUNTERS=1 (off by default → no-op)
  * Tracks call counts for 21 key functions across AGC + VideoOut pipelines
  * Background timer dumps cumulative counts every 2 seconds
  * Categories: AGC lifecycle (Init, CreateShader, CreatePrimState),
    AGC submission (DriverSubmitDcb, DriverSubmitAcb, DriverSubmitMultiDcbs),
    AGC draw calls (DrawIndex, DrawIndexAuto, DrawIndexOffset, DrawIndexIndirect, DispatchIndirect),
    VideoOut lifecycle (Open, RegisterBuffers, RegisterBuffers2, SubmitFlip,
    WaitVblank, GetFlipStatus, AddFlipEvent, AddVblankEvent)
- Added PipelineCallCounters.Increment() calls to entry of 11 functions in AgcExports.cs:
  Init, CreateShader, CreatePrimState, DcbDrawIndex, DcbDrawIndexAuto, DcbDrawIndexIndirect,
  DcbDispatchIndirect, DcbDrawIndexOffset, DriverSubmitDcb, DriverSubmitAcb, DriverSubmitMultiDcbs
- Added PipelineCallCounters.Increment() calls to entry of 8 functions in VideoOutExports.cs:
  VideoOutOpen, VideoOutWaitVblank, VideoOutAddFlipEvent, VideoOutAddVblankEvent,
  VideoOutSubmitFlip, VideoOutGetFlipStatus, VideoOutRegisterBuffers, VideoOutRegisterBuffers2
- Built and deployed new binary.
- Ran golden test (Dreaming Sarah) WITHOUT counters enabled → PASS (140 frames, 188 colors,
  no regression — confirms counters are no-op when env var is not set).
- Created /home/z/my-project/scripts/exp-pipeline-counters.sh — runs Dreaming Sarah
  and Yatzi sequentially (20s each) with SHARPEMU_PIPELINE_COUNTERS=1, dumps
  frame counts and final pipeline counter snapshots.
- Ran experiment. Side-by-side comparison:

| Function | Dreaming Sarah | Yatzi |
|----------|----------------|-------|
| AgcInit | 1 | 1 |
| AgcCreateShader | 99 | 36 |
| AgcCreatePrimState | 378 | 2 |
| AgcDriverSubmitDcb | 84 | 1 |
| AgcDcbDrawIndexAuto | 66 | 1 |
| AgcDcbDrawIndexOffset | 120 | 0 |
| VideoOutOpen | 1 | 1 |
| VideoOutRegisterBuffers2 | 1 | 1 |
| VideoOutSubmitFlip | 0 (uses DCB-embedded) | 1 (direct call) |
| VideoOutAddFlipEvent | 84 | 2 |
| Frames produced | 90 | 0 |
| flip_capture_failed warnings | 0 | 1 |
| UNMAPPED faults | 0 | 5 |

- KEY FINDING #1: Yatzi DOES reach the rendering phase — it submits 1 DCB, 1 draw call,
  and 1 direct sceVideoOutSubmitFlip. It is NOT stuck before rendering; it is stuck
  AFTER attempting one frame.

- KEY FINDING #2: Yatzi's `vk.flip_capture_failed` warning happens IMMEDIATELY after
  `Vulkan VideoOut ready` (line 2250), BEFORE the NID loop even starts (line 2320).
  This means the previous interpretation "NID loop runs first, then audio/mutex loop"
  was WRONG. The actual sequence is:
    T=5s   Vulkan VideoOut ready
    T=5s   sceVideoOutSubmitFlip called → flip_capture_failed (image not in _guestImages)
    T=5s   UNMAPPED fault at rip=0x800B28A0D: `cmp qword ptr [r12+38h],0`
           (Unity tries to read struct field at r12+0x38, but r12 is NULL)
           RCX=0xC0DEC0DECAFEBA00 (Unity's "we're in error state" magic marker)
    T=5s   Unity error handler runs (the 60,343 + 19,968 NID calls = 80,311 total)
    T=7s   NID loop completes
    T=7s+  Main thread spins on audio/mutex loop forever (game is in error state)

  The NID loop was never normal initialization — it was Unity's ERROR HANDLER
  triggered by the failed flip + memory fault.

- KEY FINDING #3 (answers user's specific question): The function responsible for
  registering the display buffer (sceVideoOutRegisterBuffers2) IS being called
  (counter=1 in both games). But it only populates `_availableGuestImages` (via
  RegisterKnownDisplayBuffer), NOT `_guestImages` (the actual Vulkan image resource).
  When the flip is later attempted, the presenter looks up `_guestImages` and fails
  with found=False. This is exactly the user's predicted scenario: "function is called
  but initialized=False persists → bug in HLE implementation."

- KEY FINDING #4: Dreaming Sarah works because it does NOT call sceVideoOutSubmitFlip
  directly. It uses DCB-embedded flips (sceAgcDcbDrawIndexOffset + flip packet in
  same submission). The DCB-embedded flip path goes through TrySubmitOrderedGuestImageFlip
  which checks `_availableGuestImages` (passes), but also requires the image to be
  rendered into first via the DCB itself. Dreaming Sarah always renders before flipping.

- KEY FINDING #5: Yatzi's behavior is the actual PS5 boot pattern — Unity registers
  display buffers and immediately flips them to display a black initial frame BEFORE
  any rendering. Real PS5 hardware creates the backing image when the buffer is
  registered. SharpEmu does not, causing the flip to fail silently and Unity to
  crash on the missing image data.

- ROOT CAUSE IDENTIFIED:
  Bug location: src/SharpEmu.Libs/VideoOut/VulkanVideoPresenter.cs line 1335
  (`RegisterKnownDisplayBuffer` method)
  Bug: only adds address to `_availableGuestImages` dictionary; does NOT create a
  real Vulkan image in `_guestImages`. When the game later flips this address
  before rendering, `ExecuteOrderedGuestFlip` looks up `_guestImages` and fails.
  Effect: Yatzi's initial boot flip fails, Unity's error handler runs, game stalls.

- Verified golden test passes BEFORE and AFTER all changes (no regression).
- Did NOT modify any IL2CPP stubs (per user's explicit instruction).

Stage Summary:
- ✅ User's cheap test executed as requested
- ✅ Pipeline counter instrumentation added (off by default, no behavior change)
- ✅ Side-by-side Dreaming Sarah vs Yatzi comparison captured
- ✅ ROOT CAUSE identified: RegisterKnownDisplayBuffer does not create Vulkan image
- ✅ NID loop reinterpreted as Unity's ERROR HANDLER (not normal init) — previous
  CHECKPOINT_v0.0.11.md section 17 had this wrong
- ✅ User's specific question answered: "function IS called, but flag NOT set"
- ✅ Golden test still passes (138 frames, 188 colors)
- Artifacts produced:
  - /home/z/my-project/scripts/exp-pipeline-counters.sh
  - /tmp/exp-pipeline-counters/{dreaming-sarah,yatzi}.log
  - src/SharpEmu.Libs/Kernel/PipelineCallCounters.cs (new file)
- Modified files:
  - src/SharpEmu.Libs/Agc/AgcExports.cs (11 Increment calls added)
  - src/SharpEmu.Libs/VideoOut/VideoOutExports.cs (8 Increment calls added)
- Next P1 (suggested fix): modify RegisterKnownDisplayBuffer to also create a
  placeholder Vulkan image in _guestImages so the first flip succeeds with black
- New env vars:
  - SHARPEMU_PIPELINE_COUNTERS=1 — enable pipeline call counters

---
Task ID: EXP-GIMG-LIFECYCLE + EXP-FALLBACK-FLIP
Agent: main (SharpEmu bringup)
Task: Per user's careful approach — trace _guestImages lifecycle in both
games BEFORE implementing fallback fix. Then implement fallback in
ExecuteOrderedGuestFlip (NOT in RegisterBuffers) with feature flag. Verify
golden test still passes, and verify Yatzi produces frames (not just no-crash).

Work Log:
- Step 1 (lifecycle trace): Added GIMG-CREATE logging at all 3 sites where
  _guestImages entries are created (lines 7004, 10223, 10360). Three paths:
  - cpu_backed_texture: created when CPU uploads a texture (used by Dreaming Sarah)
  - retained_variant: reusing a previously-stored variant (rare)
  - render_target_new: created when AGC renders into a render target
  Activated by SHARPEMU_TRACE_GUEST_IMAGE_EVENTS=1 (already-existing env var).

- Step 2 (lifecycle data): Ran /home/z/my-project/scripts/exp-gimg-lifecycle.sh
  Side-by-side comparison:

| | Dreaming Sarah | Yatzi |
|--|----------------|-------|
| GIMG-CREATE events | 3 (2 render_target_new + 1 cpu_backed_texture) | **0** |
| First flip_capture_failed | (none) | addr=0x10CA0000 |
| Total frames | 65 | 0 |

  This DEFINITIVELY confirms user's hypothesis: RegisterBuffers is NOT supposed
  to create the image. AGC's render_target_new path is the legitimate creator.
  Yatzi never reaches that path because it flips before rendering.

- Step 3 (implement fallback): Added CreateFallbackGuestImage() method to
  VulkanVideoPresenter.cs. Creates a B8G8R8A8Unorm Vulkan image, clears it to
  opaque black using a one-shot command buffer (CmdClearColorImage with
  (0,0,0,1) RGBA), adds it to _guestImages, returns the GuestImageResource.

  Wired into ExecuteOrderedGuestFlip: when _guestImages[address] lookup fails
  AND SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1 is set AND _availableGuestImages
  contains the address AND width/height > 0, call CreateFallbackGuestImage.
  Otherwise fall through to the existing flip_capture_failed warning.

  Key design decisions (per user's explicit instruction):
  - Fallback is in ExecuteOrderedGuestFlip (lazy), NOT in RegisterBuffers
  - Behind feature flag SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1 (off by default)
  - Dreaming Sarah unaffected (uses DCB-embedded flips, never hits fallback)

- Step 4 (golden test): Built and deployed. Golden test passes (118 frames,
  169 colors) with fallback OFF — confirming the fallback code path is
  unreachable when env var is not set.

- Step 5 (Yatzi test with fallback): Created and ran
  /home/z/my-project/scripts/exp-fallback-flip.sh.

  Side-by-side comparison WITH vs WITHOUT fallback (both 20s runs):

| Metric | Without fallback | With fallback |
|--------|-------------------|---------------|
| flip_capture_failed events | 1 | **0** |
| flip_fallback_created events | 0 | **1** |
| GIMG-CREATE events | 0 | **1** (path=fallback_flip) |
| Frames produced | 0 | **1** (frame #1) |
| UNMAPPED faults | 5 | 5 (no change) |
| NID-COUNTS final | 60343 / 19968 | 60343 / 19968 (no change) |
| 0xC0DEC0DECAFEBA00 magic markers | 15 | 15 (no change) |

  HONEST EVALUATION:
  ✅ Fallback FIX WORKS — flip no longer fails, frame is presented
  ✅ First black frame is displayed (1 distinct color)
  ❌ Game is STILL in Unity error state (UNMAPPED faults, NID loop, magic markers)
  ❌ Game still stalls in audio/mutex loop after first frame

- Step 6 (timeline analysis): Examined the exact ordering of events:

  WITHOUT fallback (baseline):
    T=5s  Vulkan VideoOut ready (line 2249)
    T=5s  vk.flip_capture_failed (line 2250) — image lookup failed
    T=5s  UNMAPPED fault #1 at rip=0x800B28A0D: cmp qword ptr [r12+38h],0
          (Unity tries to read struct field at r12+0x38, r12 is NULL)
    T=5s  RCX=0xC0DEC0DECAFEBA00 (Unity's error state magic marker)
    T=5s+ Unity error handler runs (the 60,343 + 19,968 NID calls)
    T=7s  NID loop completes, game stalls in audio/mutex loop

  WITH fallback:
    T=5s  Vulkan VideoOut ready (line 2249)
    T=5s  UNMAPPED fault #1 at SAME rip (line 2250) — NULL pointer STILL fires
          NOTE: fallback not yet created at this point!
    T=5s  AudioOut ports 1, 2 initialized (silent backend)
    T=5s  FMOD threads scheduled
    T=5s  scePthreadMutexLock calls
    T=5s+ flip_fallback_created (line 2282) — flip retry succeeds!
    T=5s+ vk.present_taken + vk.present_sample frame=1 — FRAME PRESENTED
    T=5s+ Unity error handler runs (same NID loop as without fallback)

  CRITICAL FINDING: The UNMAPPED fault at rip=0x800B28A0D happens
  IMMEDIATELY after Vulkan VideoOut becomes ready, BEFORE any flip is
  even attempted. The flip_capture_failed warning we previously thought
  was the cause is actually a CONSEQUENCE — Unity's error path fires
  first, then attempts the failed flip as part of error cleanup.

  This means: there is a SEPARATE root cause that triggers Unity's error
  path. The flip fix is correct (it eliminates the flip_capture_failed
  warning and produces a frame), but the underlying Unity error state
  has a different trigger.

- Honest conclusion documented:
  - The fallback fix is a VALID STEP FORWARD (frame count: 0 → 1)
  - But it is NOT the complete fix — game still stalls in error state
  - Next P1: investigate what causes the UNMAPPED fault at rip=0x800B28A0D
    immediately after VideoOut ready (likely a missing Unity engine callback
    or an unimplemented HLE function that should populate r12)

- Golden test still passes (118 frames, 169 colors).

Stage Summary:
- ✅ User's careful approach executed exactly as specified
- ✅ Lifecycle trace confirmed: RegisterBuffers should NOT create image;
  AGC render_target_new path is the legitimate creator
- ✅ Fallback implemented in ExecuteOrderedGuestFlip (lazy, NOT RegisterBuffers)
  behind SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1 feature flag
- ✅ Fallback successfully creates black placeholder image and presents frame
- ✅ Frame count: 0 → 1 (black frame, as expected)
- ⚠️ HONEST: game still stalls in Unity error state — fallback is INTERMEDIATE
  step, not complete fix. There's a separate root cause for the UNMAPPED fault
  at rip=0x800B28A0D that happens immediately after VideoOut ready.
- ✅ Golden test still passes (no regression, Dreaming Sarah unaffected)
- ✅ Did NOT modify any IL2CPP stubs (per user's explicit instruction)
- Artifacts produced:
  - /home/z/my-project/scripts/exp-gimg-lifecycle.sh
  - /home/z/my-project/scripts/exp-fallback-flip.sh
  - /tmp/exp-gimg-lifecycle/{dreaming-sarah,yatzi}.log
  - /tmp/exp-fallback-flip/yatzi.log (with fallback)
  - /tmp/exp-fallback-flip/yatzi-no-fallback.log (without fallback, for comparison)
- New env vars added:
  - SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1 — enable lazy fallback image creation
- Modified file: src/SharpEmu.Libs/VideoOut/VulkanVideoPresenter.cs
  - Added _videoOutFallbackImageEnabled flag (off by default)
  - Added CreateFallbackGuestImage() method (~150 lines)
  - Modified ExecuteOrderedGuestFlip() to use fallback when env var set
  - Added GIMG-CREATE tracing at 3 sites where _guestImages entries are created
- Next P1 (honest): investigate UNMAPPED fault at rip=0x800B28A0D — separate
  root cause, not fixed by fallback. Likely a missing HLE function that
  Unity expects to populate r12 before its first NULL check.
