# SharpEmuT24 Project Status Report
## Migration to New Chat Context
## Version: v0.0.9

---

# 1. Golden Rule

Dreaming Sarah = Golden Test. Every change must pass it.
- GLFW X11 → Vulkan VideoOut → Real framebuffer → 50+ colors
- Run: `tests/golden/run-golden-tests.sh`

# 2. Root Cause That Was Found

GLFW backend selection on Xvfb-only Linux:
- Before: only requested X11 when WAYLAND_DISPLAY was set
- After (PR #457): always request X11 when DISPLAY is set
- Result: Vulkan surface created, real framebuffer dumps produced

# 3. Proof of Real Rendering

Dreaming Sarah: 138 frames, 167+ colors, real game content.
Frames saved at: /home/z/my-project/download/game-screenshots/

# 4. Mistakes Documented

1. HSV test pattern (RGB 229,95,68) confused with game output
2. 6 false hypotheses wasted days (scheduler, semaphore, metadata, files, stubs, regression)
3. Real fix was one function: PreferX11OnLinuxWayland()

# 5. Game Status

| Game | Engine | Status | Blocker |
|------|--------|--------|---------|
| Dreaming Sarah | Native C++ | ✅ GOLDEN | None |
| Yatzi | Unity IL2CPP | 🟡 Progress | Bootstrap loop (48 crashes) |
| Seeker | Unity IL2CPP | 🟡 Same | Same as Yatzi |
| Arise | Native C++ | ❌ | SIGILL crash |
| Harvest Days | Unity IL2CPP | ❌ | Encrypted PRX files |

# 6. NID Stubs Added (commit b451ae9)

| NID | Name | Effect |
|-----|------|--------|
| VkqLPArfFdc | IL2CPP bootstrap | Returns non-NULL |
| GrQ9s4IrNaQ | sceAudioOutGetPortState | Returns OK |
| MM4IZSEYytQ | sceAgcDriverSetHsOffchipParam | Returns OK |
| XlNp7jzGiPo | sceAgcDriverSetTFRing | Returns OK |
| xk0AcarP3V4 | scePadOpen | Returns fake handle |
| 1-LFLmRFxxM | sceKernelMkdir | Returns OK |
| rVjRvHJ0X6c | sceKernelFindInternalFile | Returns NOT_FOUND |
| BHouLQzh0X0 | sceKernelFindInternalFileVariant | Returns NOT_FOUND |

Yatzi results: unresolved NIDs 4→0, crashes 18120→48

# 7. Yatzi Current Issue

Game stuck in bootstrap loop calling:
- 1D0H2KNjshE_stub (59x) — Harvest Days stub, may be wrong for Yatzi
- hsi9drzHR2k_stub (21x) — Harvest Days stub, may be wrong for Yatzi
- scePthreadMutexLock, sceKernelClockGettime, sceAudioOutOutput

Next: investigate if Harvest Days stubs are causing wrong behavior in Yatzi.
Need to trace what these NIDs actually are and if they should return different values.

# 8. NID Coverage Gap

Old working source (e3bbe69): 1029 NIDs
Current source: ~920 NIDs (after our stubs)
Missing: ~109 NIDs from old source (SaveData, AudioPropagation, etc.)

# 9. Diagnostics Tools Built

- BootDependencyAnalyzer (tests/golden/GOLDEN_BASELINE.md)
- ExecutableFormatDetector
- FrameAnalyzer
- Golden test script (tests/golden/run-golden-tests.sh)
- SHARPEMU_LOG_SEMA, SHARPEMU_LOG_OPEN, SHARPEMU_LOG_IL2CPP_NULL
- SHARPEMU_TRACE_GUEST_IMAGES (swapchain dump)
- SHARPEMU_DUMP_VIDEOOUT (BMP dump)
- SHARPEMU_STALL_WATCHDOG_SECONDS

# 10. Environment

- Linux headless (Debian, no physical GPU)
- Xvfb :99 1920x1080x24
- Lavapipe (llvmpipe, LLVM 19.1.7, software Vulkan)
- .NET SDK 10.0.302
- GLFW 3.4 with X11 platform hint
- libX11 user-local install

# 11. Next Steps (Priority Order)

1. **Freeze Dreaming Sarah** — no renderer changes
2. **Fix Yatzi bootstrap loop** — investigate 1D0H2KNjshE/hsi9drzHR2k stubs
3. **Port missing NIDs** from old source (e3bbe69)
4. **Test Seeker** after Yatzi works
5. **Investigate Arise SIGILL**
6. **Harvest Days** needs decrypted PRX files

# 12. Key Commits

- f83b6ea — v0.0.9 release (GLFW X11 fix + real frames)
- 17a0d05 — PreferX11OnLinuxWayland fix (PR #457)
- 3b2d499 — VkqLPArfFdc + 3 NID stubs
- b451ae9 — 4 more NID stubs (scePadOpen, sceKernelMkdir, etc.)
- golden-render-baseline tag at v0.0.9
