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
Task ID: EXP-017
Agent: main (SharpEmu bringup)
Task: Investigate architecture-correct approach for multi-buffer draw orphan (KRz stub).
      User hypothesis: GPU state should persist at AGC queue/context level,
      rather than physical buffer merge. Verify by measurement.

Work Log:
- Reviewed existing AGC driver architecture:
  * SubmittedGpuState.Graphics is a single long-lived SubmittedDcbState
    (the persistent per-queue GPU state object).
  * CxRegisters / ShRegisters / UcRegisters dictionaries persist across
    DCB submissions on the same queue.
  * ResetSubmittedParserState is only invoked by explicit RDrawReset /
    RAcbReset packets inside a DCB (NOT at submission boundaries).
  * Therefore the existing architecture ALREADY implements queue-level
    state persistence; no new state object is required.

- Verified that the previously-staged SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS=1
  experiment uses gpuState.Graphics (the persistent queue state) for both
  the normally-submitted setup DCB AND the auto-chained draw DCB. This is
  NOT physical buffer merge — it is exactly the architecture-correct
  approach the user requested (state persistence at queue level, with each
  buffer processed independently through the same persistent state).

- Built SharpEmu with current source and ran four measurements:

  Test A: Dreaming Sarah WITHOUT auto-chain (Golden Test baseline)
    Result: PASS, 138 frames, 256 distinct colors.

  Test B: Dreaming Sarah WITH auto-chain=1 (Golden Test regression check)
    Result: PASS, 139 frames, 260 distinct colors. No regression.

  Test C: Yatzi WITHOUT auto-chain (baseline)
    Result: render_work_enter=0, VulkanOffscreenGuestDraw=0,
            krz_auto_chain=0, queue_reset=1, present_taken=1.
            Draw DCB orphaned (never parsed) — confirms root cause.

  Test D: Yatzi WITH auto-chain=1 (3 reproducibility runs)
    Run 1: render_work_enter=2, VulkanOffscreenGuestDraw=1, present_taken=2,
           krz_auto_chain=2, queue_reset=1, dcb_draw_index_auto=1.
    Run 2: identical to Run 1.
    Run 3: identical to Run 1.
    Draw DCB successfully parsed via persistent queue state.
    VulkanOffscreenGuestDraw executes; rt_writer seq=2 target=0x11390000
    (real render target, R8G8B8A8Unorm 1920x1080) with both export and
    pixel shaders bound (es=0x601540500, ps=0x601540D00).

- Only ONE queue_reset event fires (from the setup DCB's RDrawReset header).
  The auto-chained draw DCB does NOT contain a reset, so state set by the
  setup DCB persists across to the draw DCB. TryTranslateGuestDraw sees
  valid ShRegisters / CxRegisters and translates the draw successfully.

Stage Summary:
- ✅ User hypothesis CONFIRMED: queue-level state persistence is the
  architecture-correct approach and it already works in the existing
  SubmittedGpuState.Graphics design. No new state object or per-DCB reset
  is needed.
- ✅ The auto-chain experiment (SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS=1) is
  NOT physical buffer merge. It processes each KRz-touched buffer as a
  separate submission through the SAME persistent queue state, which is
  exactly the architecture-correct approach.
- ✅ Golden Test still passes with auto-chain enabled (no regression for
  Dreaming Sarah: 139 frames / 260 colors vs 138 / 256 baseline).
- ✅ Yatzi draw now translates and executes (VulkanOffscreenGuestDraw
  fires, rt_writer logs the render target with shaders bound). 3/3 runs
  reproducible.
- ❌ NEW BLOCKER (separate from state persistence): Yatzi only issues 1
  sceVideoOutSubmitFlip (and 1 dcb_set_flip embedded in setup DCB). The
  flip uses the fallback image at 0x10B20000. The draw writes to a
  different render target at 0x11390000. Since no further flip happens
  after the draw executes, the rendered RT is never displayed. This is a
  present-path mismatch, not a state-persistence failure.
- Artifacts:
  /home/z/my-project/logs/yatzi-nochain.log         (Yatzi baseline)
  /home/z/my-project/logs/yatzi-chain-run{1,2,3}.log (Yatzi with auto-chain)
  /home/z/my-project/logs/yatzi-krz-chain.log        (initial auto-chain run)

Commit: 58464ca  fix: queue-level state persistence for KRz-touched draw buffers

Next Step Recommendation:
  The remaining Yatzi blocker is NOT state persistence — it is a
  present-path mismatch:
    * Draw writes to RT 0x11390000 (render_target_new, R8G8B8A8Unorm)
    * sceVideoOutSubmitFlip flips fallback image at 0x10B20000
    * Only 1 SubmitFlip + 1 dcb_set_flip happen in 60s, both BEFORE
      the draw executes. The RT is never flipped to display.

  Possible angles for the next investigation:
    1. Does Yatzi's eboot.bin call sceVideoOutSubmitFlip with the RT
       address as the buffer address? Trace rdi of SubmitFlip and
       compare to 0x11390000.
    2. Is the game waiting on a semaphore (WaitSema) that never gets
       signaled because the GPU work completion event isn't firing?
       The setup DCB's completion fired (submission 1), but the
       auto-chained draw's completion may not.
    3. Is the render target at 0x11390000 registered with VideoOut via
       sceVideoOutRegisterBuffers2? VideoOutRegisterBuffers2=1 in the
       counters — verify what address it registered.

---
Task ID: EXP-018
Agent: main (SharpEmu bringup)
Task: Publish a complete checkpoint of all changes after reference commit
      4cc320f (semaphore handle fix). Document six areas: semaphore fix,
      KRz buffer tracking, auto-chain feature, GPU state persistence
      verification, full test results, and current blocker status. Update
      worklog. No code deletion or reset.

Work Log:
- Verified git state: exactly one commit exists between 4cc320f and HEAD
  (58464ca — queue-level state persistence for KRz-touched draw buffers).
  Working tree only had uncommitted worklog.md changes.
- Reviewed commit 4cc320f in detail:
  * File: src/SharpEmu.Libs/Kernel/KernelSemaphoreCompatExports.cs
  * Added ResolveSemaphoreHandle(uint handle) => handle & 0x7FFFFFFFu
  * Applied to all 5 semaphore APIs (WaitSema, PollSema, SignalSema,
    CancelSema, DeleteSema).
  * Golden Test passed (136f, 256c); Yatzi semaphore 0x10F now signaled
    (was 0 before).
- Reviewed commit 58464ca in detail:
  * File: src/SharpEmu.Libs/Agc/AgcExports.cs (+178/-1)
  * Added _krzTouchedBuffers / _krzProcessedBuffers / _krzBufferCommandBase
    static fields.
  * Added SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS feature flag (OFF by default).
  * Rewrote KRz stub to register touched buffers.
  * Added ProcessPendingKrzBuffers() pump.
  * Hooked ProcessPendingKrzBuffers at end of SubmitDcb and end of
    DcbDrawIndexAuto, plus public TryAutoChainKrzBuffers entry point
    for WaitSema pump path.
- Verified SubmittedGpuState.Graphics architecture:
  * Single long-lived SubmittedDcbState instance per guest memory.
  * CxRegisters / ShRegisters / UcRegisters / KnownRenderTargets /
    RenderTargetWriters persist across DCB submissions.
  * ResetSubmittedParserState only called by RDrawReset/RAcbReset packets
    (line 3292) and at queue creation (line 4661) — NOT at submission
    boundaries.
  * Therefore the existing architecture already implements queue-level
    state persistence; no new state object was needed.
- Collected test results from four runs:
  * Golden Test baseline (flag unset): 138f, 256c, PASS
  * Golden Test with flag=1: 139f, 260c, PASS — no regression
  * Yatzi baseline: render_work_enter=0, VulkanOffscreenGuestDraw=0
  * Yatzi with flag=1 (3 reproducibility runs, all identical):
    render_work_enter=2, VulkanOffscreenGuestDraw=1, rt_writer logged
    with es=0x601540500 ps=0x601540D00 target=0x11390000
- Documented current blocker:
  * Draw writes to RT 0x11390000 (real render_target_new).
  * Flips use fallback image at 0x10B20000.
  * Only 1 SubmitFlip + 1 dcb_set_flip in 60s, both BEFORE the draw
    executes. RT is never displayed.
  * Three angles proposed for next investigation (no code changes made).

Stage Summary:
- ✅ Checkpoint document CHECKPOINT_v0.0.12.md created at repo root,
  covering all six sections requested by the user:
    1. Semaphore Resolve Handle (commit 4cc320f)
    2. KRz Buffer Tracking (commit 58464ca)
    3. SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS implementation
    4. GPU State Persistence verification
    5. Full test results (Golden + Yatzi, before/after, all metrics)
    6. Current blocker (RT writer target, flip mismatch, VideoOut path)
- ✅ No code was deleted, reset, or modified. Only documentation added.
- ✅ Experimental flag SHARPEMU_AGC_AUTO_CHAIN_KRZ_BUFFERS remains OFF by
  default, exactly as it was after commit 58464ca.
- ✅ Three reproducibility runs confirm Yatzi metrics are stable.
- Next-step recommendation recorded in section 6.3 of the checkpoint
  document: investigate the present-path mismatch (VideoOutRegisterBuffers2
  argument, completion event notification, dcb_set_flip ordering) before
  promoting the flag to default-on.
