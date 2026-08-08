# EXP-138 Rendering Regression Analysis

**Date:** 2026-08-04
**Commit tested:** `9cef960` (EXP-138 patch) on top of `a2d4935` (latest main)

---

## Baseline (v0.0.9, f83b6ea)

| Frame | Colors | Source |
|-------|--------|--------|
| Frame 1 | 23 | GOLDEN_BASELINE.md |
| Frame 70 | 23 | GOLDEN_BASELINE.md |
| Frame 138 | 167+ | GOLDEN_BASELINE.md |

**PNG links (v0.0.9 reference):** Historical — not available in current sandbox. Baseline established on 2026-07-24 with Xvfb + Lavapipe + VulkanVideoPresenter.

**Key requirement from GOLDEN_BASELINE.md:**
- VulkanVideoPresenter activates (not HeadlessVideoPresenter)
- GLFW X11 backend selected
- 100+ framebuffer dumps produced
- At least one frame has 50+ distinct colors

---

## Current (EXP-138 HEAD)

| Metric | Result |
|--------|--------|
| Commit | `9cef960` (EXP-138) on `a2d4935` (main) |
| Frame count | 139 framebuffer dumps |
| Frame 1 colors | **23** |
| Frame 70 colors | **23** |
| Frame 138 colors | **228** |
| Non-zero pixels | 100% (3,686,400 / 3,686,400 bytes non-zero) |
| Draw count | (not in log — framebuffer dumps are the rendering evidence) |
| Backend | VulkanVideoPresenter (NOT HeadlessVideoPresenter) |
| GLFW | X11 backend selected |
| Crash count | 0 |

**PNG links (current, with EXP-138):**
- Frame 1: `scripts/exp138/evidence/golden/frame001.png` (8884 bytes, 23 colors)
- Frame 70: `scripts/exp138/evidence/golden/frame070.png` (8884 bytes, 23 colors)
- Frame 138: `scripts/exp138/evidence/golden/frame138.png` (37370 bytes, 228 colors)

**SHA256 hashes:**
- Frame 1: `09a8cb7d317af1909ab94812c36e828121b2dbdd6208466f65b86d3bb01db562`
- Frame 70: `09a8cb7d317af1909ab94812c36e828121b2dbdd6208466f65b86d3bb01db562` (identical to frame 1 — loading screen)
- Frame 138: `235147b669c1518eba60094f9622806929fa57d4f8dc4b59c4ce29c870678b58` (DIFFERENT — real game content)

---

## Difference

### First failing commit: NONE

**There is NO rendering regression.** EXP-138 does NOT break Dreaming Sarah rendering.

The previous "RENDERING BLOCKED" result was caused by using `SHARPEMU_HEADLESS=1`, which forces HeadlessVideoPresenter (a stub that doesn't render). When the correct environment is set up (Xvfb + Lavapipe + no SHARPEMU_HEADLESS), VulkanVideoPresenter activates and rendering works correctly — with EXP-138 applied.

### Environment setup required for rendering

The golden test script (`tests/golden/run-golden-tests.sh`) requires:
1. **Xvfb** running on `:99` (virtual X11 display)
2. **Lavapipe** (software Vulkan ICD — `lvp_icd.json` + `libvulkan_lvp.so`)
3. **GLFW X11** library (`libglfw.so.3`)
4. **`SHARPEMU_HEADLESS` unset** (so VulkanVideoPresenter is used, not HeadlessVideoPresenter)
5. `DISPLAY=:99` environment variable
6. `VK_ICD_FILENAMES` pointing to Lavapipe ICD
7. `LD_LIBRARY_PATH` including GLFW + Vulkan + X11 library paths

When all of these are set up correctly, rendering works with EXP-138 applied.

---

## Fix

**Files changed:** NONE

**Why:** No fix is needed. EXP-138 does not cause a rendering regression. The previous "RENDERING BLOCKED" result was an environment setup error (using `SHARPEMU_HEADLESS=1` instead of setting up Xvfb + Lavapipe).

The correct test environment was set up by:
1. Downloading and extracting `mesa-vulkan-drivers` .deb (provides Lavapipe)
2. Downloading and extracting `libglfw3` .deb (provides GLFW X11 backend)
3. Starting Xvfb on display `:99`
4. Setting `DISPLAY=:99`, `VK_ICD_FILENAMES`, `LD_LIBRARY_PATH`
5. Unsetting `SHARPEMU_HEADLESS` (critical — this was the previous mistake)

### Regression tests

| Test | Result |
|------|--------|
| Build | ✅ PASS (0 errors) |
| Boot | ✅ PASS (Can boot: YES) |
| GLFW X11 backend | ✅ PASS ("GLFW windowing platform in use: X11") |
| Vulkan VideoOut | ✅ PASS ("Vulkan VideoOut ready") |
| Frame count ≥ 50 | ✅ PASS (139 frames) |
| Colors ≥ 50 | ✅ PASS (228 colors in frame 138) |
| Frame 1 == Frame 70 (loading screen) | ✅ PASS (identical SHA256) |
| Frame 138 != Frame 1 (game content) | ✅ PASS (different SHA256) |
| Crash count = 0 | ✅ PASS |
| EXP-138 patch compiled | ✅ PASS |

---

## Final Status

# ✅ PASS

**Dreaming Sarah Golden Test PASSES with EXP-138 patch applied.**

Evidence:
- 139 framebuffer dumps produced
- Frame 1: 23 colors (matches v0.0.9 baseline)
- Frame 70: 23 colors (matches v0.0.9 baseline)
- Frame 138: 228 colors (exceeds v0.0.9 baseline of 167+)
- Frames 1 and 70 have identical SHA256 (loading screen — expected)
- Frame 138 has different SHA256 (real game content — expected)
- 100% non-zero pixels (real framebuffer data)
- VulkanVideoPresenter active (not HeadlessVideoPresenter)
- GLFW X11 backend selected
- 0 crashes

**EXP-138 does NOT regress Dreaming Sarah rendering.**

The previous "RENDERING BLOCKED" report was caused by incorrect test environment setup (using `SHARPEMU_HEADLESS=1`), NOT by the EXP-138 patch.

---

## What Was Wrong Previously

1. **Used `SHARPEMU_HEADLESS=1`** — this forced HeadlessVideoPresenter, which is a stub that doesn't render
2. **No Xvfb** — no virtual X11 display for GLFW to connect to
3. **No Lavapipe** — no software Vulkan renderer
4. **No GLFW library** — SharpEmu couldn't initialize GLFW

When these are fixed (Xvfb + Lavapipe + GLFW + no SHARPEMU_HEADLESS), rendering works correctly with EXP-138 applied.

## Evidence Files (GitHub URLs)

| File | Path |
|------|------|
| This report | `exp-reports/EXP-138-rendering-regression-analysis.md` |
| Frame 1 PNG | `scripts/exp138/evidence/golden/frame001.png` |
| Frame 70 PNG | `scripts/exp138/evidence/golden/frame070.png` |
| Frame 138 PNG | `scripts/exp138/evidence/golden/frame138.png` |
| Execution log | `scripts/exp138/evidence/golden/execution-log.txt` |
