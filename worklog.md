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
