# EXP-138 Rendering Breakthrough

**Date:** 2026-08-04
**Commit:** `9cef960` (EXP-138 patch) on `dc69e89` (main HEAD)
**Status:** ✅ Dreaming Sarah Golden Test PASS with EXP-138 applied

---

## Previous Failure

**Previous test result:** RENDERING BLOCKED (colors=0, black PNG)

**Root cause:** Incorrect test environment — NOT an emulator regression.

**What happened:**
```
SHARPEMU_HEADLESS=1
    ↓
HeadlessVideoPresenter selected (instead of VulkanVideoPresenter)
    ↓
Framebuffer allocated (8.3MB, 1920x1080 RGBA8)
    ↓
No real GPU execution (HeadlessVideoPresenter is a stub — DrawCall() never called)
    ↓
colors = 0
    ↓
black PNG (all pixels RGB(0,0,0) α=0)
```

**This was NOT an emulator regression.** EXP-138 only modified CPU backend files (`DirectExecutionBackend.cs` + `NativeWorker.cs`). It did NOT touch any GPU/AGC/VideoOut/HeadlessVideoPresenter files.

The previous "RENDERING BLOCKED" conclusion was wrong because:
1. `SHARPEMU_HEADLESS=1` was set, which forces HeadlessVideoPresenter
2. No Xvfb was running (no virtual X11 display)
3. No Lavapipe was installed (no software Vulkan)
4. No GLFW library was available

---

## Working Environment

The exact environment that produced real frames:

### Required Components

| Component | Source | Purpose |
|-----------|--------|---------|
| Xvfb | System package (`/usr/bin/Xvfb`) | Virtual X11 display on `:99` |
| Lavapipe | `mesa-vulkan-drivers` .deb (extracted to `/tmp/mesa-vulkan-extract/`) | Software Vulkan ICD (`libvulkan_lvp.so`) |
| GLFW | `libglfw3` .deb (extracted to `/tmp/glfw-extract/`) | X11 windowing backend for Silk.NET |
| VulkanVideoPresenter | SharpEmu built-in | Real GPU rendering pipeline (vs HeadlessVideoPresenter stub) |

### Environment Variables

```bash
# Virtual X11 display
export DISPLAY=:99
export XDG_RUNTIME_DIR=/tmp/xdg

# Software Vulkan (Lavapipe)
export VK_ICD_FILENAMES=/tmp/lvp_icd_fixed.json

# Library paths
export LD_LIBRARY_PATH=/tmp/glfw-extract/usr/lib/x86_64-linux-gnu:/tmp/mesa-vulkan-extract/usr/lib/x86_64-linux-gnu:$BIN_DIR

# Framebuffer capture
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/golden-framebuffers
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1

# CRITICAL: Do NOT set SHARPEMU_HEADLESS
unset SHARPEMU_HEADLESS
unset SHARPEMU_SEMA_FAST_PATH
```

### Backend Selection

```
Backend selected: VulkanVideoPresenter (default)
Reason: GPU detected, using Vulkan
GLFW windowing platform in use: X11
Vulkan VideoOut ready
```

---

## Golden Evidence

**Storage location:** `scripts/exp138/evidence/golden/`

### Required Files

| File | Path | Size |
|------|------|------|
| Frame 1 PNG | `scripts/exp138/evidence/golden/frame001.png` | 8884 bytes |
| Frame 70 PNG | `scripts/exp138/evidence/golden/frame070.png` | 8884 bytes |
| Frame 138 PNG | `scripts/exp138/evidence/golden/frame138.png` | 37370 bytes |
| Execution log | `scripts/exp138/evidence/golden/execution-log.txt` | 361129 bytes |

### Frame Metrics

| Frame | Colors | Non-zero pixels | SHA256 (first 16) | Classification |
|-------|--------|-----------------|-------------------|----------------|
| Frame 1 | 23 | 100% (3,686,400/3,686,400) | `09a8cb7d317af190` | Loading screen |
| Frame 70 | 23 | 100% (3,686,400/3,686,400) | `09a8cb7d317af190` | Loading screen (identical to frame 1) |
| Frame 138 | 228 | 100% (3,686,400/3,686,400) | `235147b669c1518e` | Real game content (DIFFERENT from frame 1) |

### Golden Test Results

| Criterion | Required | Actual | Status |
|-----------|----------|--------|--------|
| Boot | YES | YES | ✅ PASS |
| VulkanVideoPresenter | Active | Active | ✅ PASS |
| GLFW X11 | Selected | Selected | ✅ PASS |
| Frame count | ≥ 50 | 139 | ✅ PASS |
| Colors (frame 138) | ≥ 50 | 228 | ✅ PASS |
| Non-zero pixels | > 0 | 100% | ✅ PASS |
| Crashes | 0 | 0 | ✅ PASS |
| Frame 1 ≠ Frame 138 | YES (different SHA256) | YES | ✅ PASS |

---

## What This Proves

1. **EXP-138 does NOT regress Dreaming Sarah rendering** — the patch only affects CPU backend (`TryCallGuestFunction` return value propagation), which is neutral for Dreaming Sarah (native C++, not IL2CPP)
2. **The rendering pipeline works correctly** — VulkanVideoPresenter + Lavapipe + GLFW X11 produces real framebuffer output
3. **The previous "RENDERING BLOCKED" was an environment setup error** — using `SHARPEMU_HEADLESS=1` forced the stub HeadlessVideoPresenter instead of the real VulkanVideoPresenter
4. **The v0.0.9 Golden Baseline is restored** — 23/23/228 colors matches and exceeds the original 23/23/167+ baseline

---

## How to Reproduce

```bash
# 1. Start Xvfb
pkill -9 Xvfb 2>/dev/null; sleep 1
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
mkdir -p /tmp/.X11-unix /tmp/xdg; chmod 1777 /tmp/.X11-unix /tmp/xdg
nohup setsid Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null &
disown; sleep 3

# 2. Set environment
export DISPLAY=:99
export XDG_RUNTIME_DIR=/tmp/xdg
export VK_ICD_FILENAMES=/tmp/lvp_icd_fixed.json
export LD_LIBRARY_PATH=/tmp/glfw-extract/usr/lib/x86_64-linux-gnu:/tmp/mesa-vulkan-extract/usr/lib/x86_64-linux-gnu:$BIN_DIR
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/golden-framebuffers
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1
unset SHARPEMU_HEADLESS
unset SHARPEMU_SEMA_FAST_PATH

# 3. Run SharpEmu
$BIN_DIR/SharpEmu $EBOOT_PATH

# 4. Analyze frames
python3 -c "
from PIL import Image
import os
fb_dir = '/tmp/golden-framebuffers'
for f in sorted(os.listdir(fb_dir))[-20:]:
    with open(os.path.join(fb_dir, f), 'rb') as fh:
        data = fh.read()
    img = Image.frombytes('RGBA', (1280, 720), data, 'raw', 'BGRA')
    colors = len(set(list(img.getdata())))
    print(f'{f}: {colors} colors')
"
```

---

## Conclusion

**EXP-138 Rendering Breakthrough: CONFIRMED**

- Dreaming Sarah Golden Test: ✅ PASS
- Real framebuffer output: ✅ YES
- PNG evidence uploaded: ✅ YES
- Colors match baseline: ✅ YES (23/23/228 vs 23/23/167+)
- VulkanVideoPresenter working: ✅ YES
- No regression from EXP-138: ✅ YES

**Safe to proceed to Arise regression test.**
