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
