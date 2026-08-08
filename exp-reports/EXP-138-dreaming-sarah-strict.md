# EXP-138 Dreaming Sarah Golden Test — Strict Visual Evidence Report

**Date:** 2026-08-04
**Commit tested:** `9cef960` (EXP-138 patch)
**Game:** Dreaming Sarah (PPSA02929)

---

## Verdict

```
EXECUTION:  PASS
RENDERING:  BLOCKED
```

**This is NOT a Golden Test PASS** per the strict visual evidence rule. The game executes correctly but rendering is blocked by the sandbox environment (no GPU).

**This is also NOT a regression from EXP-138.** The rendering block is a pre-existing architectural limitation of headless mode without a GPU backend.

---

## Environment

| Component | Value |
|-----------|-------|
| .NET SDK | 10.0.302 |
| OS | Linux x86-64 (sandbox container) |
| GPU | **NONE** |
| Vulkan | **NONE** (GLFW init fails: "Failed to detect any supported platform") |
| Headless | YES (`SHARPEMU_HEADLESS=1`) |

---

## Execution Evidence

### Build: PASS
- 0 errors, 13 pre-existing warnings
- EXP-138 patch (6 changes) compiled cleanly
- Pre-existing build issues (NOT from EXP-138): `_SignalSafeCrashWriter.cs` duplicate, `ps5_names.txt` gitignored

### Game Execution: PASS
- **Boot:** YES (`Can boot: YES`, 5-star eboot.bin)
- **Frame count:** 78 (in 5-second run; 205+ in previous 13-second run)
- **Flip events:** 78
- **Crash count:** 0
- **NULL execute faults:** 0
- **Guest return:** 0 (clean exit)
- **Imports resolved:** 278,000+ OK

---

## Rendering Evidence

### Frame Capture Files

| File | Path | Size |
|------|------|------|
| Frame #1 PNG | `scripts/exp138/evidence/dreaming-sarah-frame001.png` | 8117 bytes |
| Frame #10 PNG | `scripts/exp138/evidence/dreaming-sarah-frame010.png` | 8117 bytes |
| Frame analysis | `scripts/exp138/evidence/frame-analysis.txt` | 3620 bytes |
| Execution log | `scripts/exp138/evidence/execution-log.txt` | 143966 bytes |

### Frame Analysis

| Metric | Frame #1 | Frame #10 |
|--------|----------|-----------|
| Resolution | 1920×1080 | 1920×1080 |
| Format | RGBA8 | RGBA8 |
| Pixel count | 2,073,600 | 2,073,600 |
| Non-zero pixels | 0 (0.00%) | 0 (0.00%) |
| Distinct colors | 1 (RGB(0,0,0) α=0) | 1 (RGB(0,0,0) α=0) |
| Alpha values | All 0 | All 0 |
| SHA256 (pixel data) | `788ae0147bdf...` | `788ae0147bdf...` |
| SHA256 difference | — | **NONE (identical to frame 1)** |
| Classification | Empty Frame | Empty Frame |

### Visual Evidence Status

- ❌ Image contains non-zero pixels: **NO** (all frames 100% zero)
- ❌ Color count > 1: **NO** (only 1 color: black/transparent)
- ❌ Frames are visually different: **NO** (all frames have identical SHA256)

**Per Golden Visual Evidence Rule: This is NOT a Golden Test PASS.**

---

## Why draws=0 Despite sceAgcDcbDrawIndexOffset Calls

### Root Cause (from source code investigation)

The `draws=` counter is owned by `VulkanVideoPresenter._perfDrawCount` (VideoOutExports.cs:1484-1488), NOT by `HeadlessVideoPresenter`.

**In headless mode:**
1. `VideoOutManager.HasGpuSupport()` returns false (no `/dev/dri`, `/sys/class/drm`, NVIDIA driver)
2. `HeadlessVideoPresenter` is selected (no Vulkan render thread starts)
3. AGC DCB parser runs and correctly identifies draw packets (`sceAgcDcbDrawIndexOffset`, etc.)
4. Parser routes draws to `GuestGpu.Current` (hardcoded to `VulkanGuestGpuBackend` at GuestGpu.cs:14)
5. `VulkanGuestGpuBackend` has no render thread → draws silently dropped
6. `_perfDrawCount` never increments → `draws=0`

### Key Source Code Evidence

**AGC DCB parser runs (AgcExports.cs:3213, 3256):**
- `ParseSubmittedDcb` / `ParseSubmittedDcbCore` implement a full PM4 packet walker
- Correctly identifies `ItDrawIndex2`, `ItDrawIndexOffset2`, `ItDrawIndexIndirect`, `RDrawIndexAuto`
- Routes to `TryTranslateGuestDraw()` (AgcExports.cs:3536)

**Draw routing (AgcExports.cs:3663):**
```csharp
GuestGpu.Current.SubmitOffscreenTranslatedDraw(...)
```
- `GuestGpu.Current` is `VulkanGuestGpuBackend` (GuestGpu.cs:14)
- In headless mode, VulkanVideoPresenter is not active → draws dropped

**HeadlessVideoPresenter.DrawCall() is NEVER called:**
- `grep -rn "\.DrawCall(\|\.AgcDraw(\|\.AgcSubmit(\|\.SubmitCommandBuffer(" src/` returns ZERO results outside HeadlessVideoPresenter.cs itself
- The method exists but is orphaned API surface — no caller in the entire codebase

**Framebuffer dump reads from guest memory (VideoOutExports.cs:1782, 1815):**
- `TryDumpFrame` reads pixels from `slot.AddressLeft` in guest memory
- No GPU work executed → no pixels written to guest address → dump is all zeros

### Is this a regression from EXP-138?

**NO.**

EXP-138 only modified 2 files:
- `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs`
- `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.NativeWorker.cs`

EXP-138 did NOT touch:
- `HeadlessVideoPresenter.cs`
- `AgcExports.cs`
- `VideoOutExports.cs`
- `VulkanVideoPresenter.cs`
- `GuestGpu.cs`
- `VulkanGuestGpuBackend.cs`

The `draws=0` and empty framebuffer are **pre-existing architectural limitations** of headless mode without a GPU backend. They exist on `main` before EXP-138 and would exist on any commit.

---

## What Would Be Needed to Render in This Sandbox

1. **A Vulkan-capable GPU + working GLFW windowing init** — not available in sandbox
2. **OR a software `IGuestGpuBackend` implementation** — does not exist in codebase (`GuestGpu.cs:14` hardcodes `VulkanGuestGpuBackend`)
3. **OR wire `HeadlessVideoPresenter.AgcDraw()` into the AGC DCB parser** — would make `draws=` non-zero but still no pixel output (HeadlessVideoPresenter doesn't write pixels)

---

## Rendering State Classification

```
[ ] GPU Rendering Working
[ ] Headless Frame Pipeline Working
[x] Framebuffer Allocated But Empty
[ ] No Rendering Backend Available
```

**Selection: "Framebuffer Allocated But Empty"**

The framebuffer IS allocated (8.3MB, 1920×1080 RGBA8). Frame captures ARE being saved. But the framebuffer content is 100% zeros because:
- The DCB parser runs but routes draws to VulkanVideoPresenter (not active)
- HeadlessVideoPresenter.DrawCall() is never called
- No actual GPU rendering occurs

---

## Conclusion

### EXP-138 Impact on Dreaming Sarah

| Aspect | Status | Evidence |
|--------|--------|----------|
| Build | ✅ PASS | 0 errors, patch compiled cleanly |
| Boot | ✅ PASS | `Can boot: YES`, 5-star |
| Execution | ✅ PASS | 78+ frames, 0 crashes, clean exit |
| No regression | ✅ PASS | EXP-138 only touched CPU backend, not GPU |
| Rendering | ❌ BLOCKED | No GPU in sandbox (pre-existing, not regression) |

### Final Verdict

```
EXECUTION: PASS
RENDERING: BLOCKED
```

**Per Golden Visual Evidence Rule:** This is NOT a Golden Test PASS because captured frames do not contain verified non-zero pixel data.

**However:** EXP-138 does NOT regress Dreaming Sarah. The rendering block is a pre-existing sandbox environment limitation (no GPU/Vulkan), NOT caused by the patch. The patch only affects CPU-side `TryCallGuestFunction` return value propagation, which is neutral for Dreaming Sarah (native C++, not IL2CPP).

### Recommendation

- **For CPU-side regression gate:** EXP-138 is safe (no regression in boot/execution/crash metrics)
- **For full Golden Test PASS:** Maintainer must run on a machine WITH a GPU and Vulkan support to verify rendering output
- **For sandbox testing:** The sandbox can only verify CPU-side behavior (boot, imports, frame generation, crashes), not GPU rendering

---

## Evidence Files (GitHub URLs)

| File | GitHub URL |
|------|------------|
| This report | https://github.com/Sh-TB/sharpemuT24/blob/main/exp-reports/EXP-138-dreaming-sarah-strict.md |
| Frame #1 PNG | https://github.com/Sh-TB/sharpemuT24/blob/main/scripts/exp138/evidence/dreaming-sarah-frame001.png |
| Frame #10 PNG | https://github.com/Sh-TB/sharpemuT24/blob/main/scripts/exp138/evidence/dreaming-sarah-frame010.png |
| Frame analysis | https://github.com/Sh-TB/sharpemuT24/blob/main/scripts/exp138/evidence/frame-analysis.txt |
| Execution log | https://github.com/Sh-TB/sharpemuT24/blob/main/scripts/exp138/evidence/execution-log.txt |

---

## Next Steps

1. ✅ **Dreaming Sarah execution: PASS** (CPU-side, no regression from EXP-138)
2. ⚠️ **Dreaming Sarah rendering: BLOCKED** (sandbox limitation, NOT regression)
3. ⏸ **Arise regression** (next — same sandbox GPU limitation expected)
4. ⏸ **Yatzi FAST_PATH=0** (only after Arise PASS — this is where EXP-138 actually matters)
5. ⏸ **EXP-139+** (only if Yatzi still deadlocks)

**Note:** The real validation of EXP-138's impact on rendering will come from the Yatzi test. Dreaming Sarah (native C++) doesn't use `TryCallGuestFunction` for IL2CPP API lookups, so the RAX propagation fix is neutral for it. Yatzi (Unity IL2CPP) is where the fix should make a difference — if the deadlock breaks, that's the real proof.
