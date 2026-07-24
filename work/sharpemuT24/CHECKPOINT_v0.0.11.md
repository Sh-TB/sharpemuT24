# SharpEmuT24 — Definitive Checkpoint for Next Chat
## Version: v0.0.11 (post 0455370)
## Date: 2026-07-24

---

# 1. Golden Baseline (NON-NEGOTIABLE)

```
Tag: golden-render-baseline (v0.0.9, commit f83b6ea)
Game: Dreaming Sarah (PPSA02929)
Engine: Native C++
Result: ✅ PASS (138 frames, 167+ colors, real game content)
Test: tests/golden/run-golden-tests.sh
```

**Rule: Every change must pass Dreaming Sarah Golden Test before merge.**

---

# 2. What We Proved

## GLFW X11 Fix (PR #457)
- Root cause: PreferX11OnLinuxWayland() required WAYLAND_DISPLAY to request X11
- Fix: Always request X11 when DISPLAY is set
- Result: Vulkan surface created → real framebuffer → actual game image

## Real Game Frames
- Dreaming Sarah produces 138 real framebuffer dumps
- Frame 138 has 167+ distinct colors (real game content, not test pattern)
- Pipeline: Game → AGC → DCB → Vulkan → Swapchain → Framebuffer → Image

## Test Pattern Bug (Fixed)
- GenerateFramePattern() produced HSV color cycle (RGB 229,95,68 for frame 1)
- This was confused with "Unity splash" for days
- Now: FrameAnalyzer classifies frames (splash vs real content)

---

# 3. Game Status Matrix

| # | Game | Engine | Status | Blocker | Next Step |
|---|------|--------|--------|---------|-----------|
| 1 | Dreaming Sarah | Native C++ | ✅ GOLDEN | None | Protect |
| 2 | Yatzi (PPSA17697) | Unity IL2CPP | ❌ Same as upstream | SignalSema=0 | IL2CPP bootstrap trace |
| 3 | Seeker (PPSA12500) | Unity IL2CPP | ❌ Same | Same as Yatzi | After Yatzi |
| 4 | Arise (PPSA06328) | Native C++ | ❌ | SIGILL crash | Crash analyzer |
| 5 | Harvest Days (PPSA14677) | Unity IL2CPP | ❌ | Encrypted PRX | Need fSELF |

---

# 4. Windows Log Comparison (CRITICAL)

User provided upstream Windows log (PPSA17697-20260721-152128.log).

| Metric | Windows (upstream) | Linux (our fork) |
|--------|-------------------|-----------------|
| VkqLPArfFdc | 0 | 0 |
| SignalSema | **0** | **0** |
| CreateSema | 28 | 24 |
| sceAgc calls | 0 | 0 |
| Stall | Yes (20s timeout) | Yes (infinite loop) |
| All threads blocked | Yes (WaitSema) | Yes (WaitSema) |

**Conclusion: Yatzi's IL2CPP bootstrap deadlock is an UPSTREAM limitation, not our bug.**
Both upstream Windows and our Linux fork have the same issue: SignalSema is never called.

---

# 5. NID Stubs (Current State after 0455370)

## Kept (verified needed or harmless)

| NID | Name | Justification |
|-----|------|---------------|
| VkqLPArfFdc | IL2CPP bootstrap | 0 calls on Windows, harmless non-NULL return |
| GrQ9s4IrNaQ | sceAudioOutGetPortState | Called by Yatzi |
| MM4IZSEYytQ | sceAgcDriverSetHsOffchipParam | Called by Yatzi |
| XlNp7jzGiPo | sceAgcDriverSetTFRing | Called by Yatzi |
| rVjRvHJ0X6c | sceKernelFindInternalFile | Called by Yatzi |
| BHouLQzh0X0 | sceKernelFindInternalFileVariant | Called by Yatzi |
| 1-LFLmRFxxM | sceKernelMkdir | Called by Yatzi |

## Removed (Harvest Days only, not needed for Yatzi)

| NID | Name | Reason |
|-----|------|--------|
| 1D0H2KNjshE | HarvestMemOp1 | 0 calls on Yatzi Windows log |
| hsi9drzHR2k | HarvestMemOp2 | 0 calls on Yatzi Windows log |
| AcslpN1jHR8 | PadDeviceClassGetExtendedInfo | Harvest Days specific |
| 5TjaJwkLWxE | HarvestStub5Tja | Harvest Days specific |
| 3BytPOQgVKc | HarvestStub3Byt | Harvest Days specific |
| pztV4AF18iI | HarvestStubPztV | Harvest Days specific |
| xk0AcarP3V4 | scePadOpen | Conflicts with real PadExports implementation |

## Stub Policy v2 (NEW RULE)

Before adding any NID stub, verify ALL of:
1. NID exists in game's import table
2. NID is actually called (not just imported)
3. Current fallback (return-zero) causes failure
4. API behavior is known

If upstream doesn't resolve the NID and the game runs the same → do NOT stub.

---

# 6. NID Coverage Gap

```
Old working source (e3bbe69): 1029 unique NIDs
Current source (0455370):     ~920 unique NIDs
Missing:                       ~109 NIDs
```

Missing NIDs are in: SaveData (34), AudioPropagation (39), KernelPthread (15+3),
Font (8), Net (4), Pad (2), Ngs2 (2), Ajm (2), and others.

Porting these requires resolving dependency chain (GuestGpuTypes, GuestBlendConstant, etc.)

---

# 7. Diagnostics Inventory

## Source Files
```
src/SharpEmu.Core/Loader/BootDependencyAnalyzer.cs
src/SharpEmu.Core/Loader/ExecutableFormatDetector.cs
src/SharpEmu.Libs/VideoOut/FrameAnalyzer.cs
src/SharpEmu.CLI/DiagnosticEngine.cs
src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Diagnostics.cs
src/SharpEmu.Libs/Agc/AgcExports.Diagnostics.cs
src/SharpEmu.Diagnostics.Contracts/DiagnosticAdapter.cs
src/SharpEmu.Logging/IDiagnosticSink.cs
```

## Golden Test
```
tests/golden/GOLDEN_BASELINE.md
tests/golden/run-golden-tests.sh
```

## Environment Variables
```
SHARPEMU_LOG_SEMA          — Semaphore trace
SHARPEMU_LOG_OPEN          — File open trace
SHARPEMU_LOG_IL2CPP_NULL   — IL2CPP NULL return trace
SHARPEMU_LOG_IL2CPP_STUBS  — IL2CPP stub trace
SHARPEMU_LOG_GUEST_THREADS — Thread state trace
SHARPEMU_LOG_GUEST_EXCEPTIONS — Exception trace
SHARPEMU_LOG_POSIX_SIGNALS — Signal trace
SHARPEMU_DUMP_VIDEOOUT     — BMP frame dump
SHARPEMU_TRACE_GUEST_IMAGES — Swapchain dump
SHARPEMU_GUEST_IMAGE_DUMP_DIR — Dump directory
SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS — Continuous dump
SHARPEMU_STALL_WATCHDOG_SECONDS — Stall detection
SHARPEMU_DUMP_FAULT_STACK_WINDOW — Crash stack dump
SHARPEMU_WRITABLE_APP0 — Allow writes to /app0/
SHARPEMU_HEADLESS — Use headless presenter (no Vulkan)
SHARPEMU_SEMA_FAST_PATH — Bypass semaphore waits (BREAKS Unity)
```

---

# 8. Environment Setup

```bash
# Xvfb
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset &

# Vulkan (Lavapipe software renderer)
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build

# Display
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg

# Game
export SHARPEMU_APP0_DIR=/tmp/games/dreaming-sarah/PPSA02929-app0
export SHARPEMU_WRITABLE_APP0=1

# Frame capture
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/framebuffers
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1

# Run (NOT headless — must use Vulkan for real frames)
unset SHARPEMU_HEADLESS
./SharpEmu --log-level=info eboot.bin
```

---

# 9. Key Commits

```
f83b6ea  v0.0.9 release (GLFW X11 fix + real frames)
17a0d05  PreferX11OnLinuxWayland fix (PR #457)
3b2d499  VkqLPArfFdc + 3 NID stubs
b451ae9  4 more NID stubs
560301b  PROJECT_STATUS_v0.0.9.md
a9e4186  PROJECT_STATUS_v0.0.10.md (Windows log analysis)
0455370  Remove Harvest Days stubs + fix xk0AcarP3V4 conflict
```

Tags:
```
golden-render-baseline → v0.0.9 (f83b6ea)
v0.0.9  → f83b6ea
v0.0.10 → 560301b
```

---

# 10. Next Steps (Priority Order)

## P0: Protect Dreaming Sarah
- Run golden test before EVERY change
- If it fails, revert immediately

## P1: IL2CPP Bootstrap Investigation (Yatzi/Seeker)
- Do NOT add more NID stubs
- Add Semaphore Lifecycle Analyzer (create/wait/signal/delete per sema)
- Add Thread Dependency Graph (who waits for what)
- Add Last-20-Guest-Calls trace before stall
- Find what IL2CPP runtime thread is waiting for
- Compare with upstream — this is a known limitation

## P2: Port Missing NIDs from Old Source
- 109 NIDs missing (SaveData, AudioPropagation, etc.)
- Must resolve dependency chain (GuestGpuTypes, etc.)
- Port one module at a time, golden test after each

## P3: Arise SIGILL Investigation
- Get crash address, instruction bytes, register state
- Identify unsupported CPU instruction
- Implement instruction or workaround

## P4: Harvest Days
- Needs decrypted PRX files (fSELF)
- Cannot test until PRX decryption is available

---

# 11. Mistakes Documented (Do Not Repeat)

1. **HSV test pattern confused with game output** — GenerateFramePattern() RGB(229,95,68) = HSV(10°,0.7,0.9)
2. **6 false hypotheses wasted days** — scheduler, semaphore deadlock, metadata corruption, missing files, fake stubs, regression
3. **Real fix was one function** — PreferX11OnLinuxWayland() needed DISPLAY check, not WAYLAND_DISPLAY
4. **Harvest Days stubs polluted Yatzi** — 1D0H2KNjshE/hsi9drzHR2k had 0 calls on Windows but 59+21 on our fork
5. **VkqLPArfFdc was a red herring** — 0 calls on Windows; crash reduction was from removing bad stubs, not adding new ones
6. **Multiple systems changed simultaneously** — never change HLE + GPU + VideoOut at the same time
7. **Frame count ≠ game output** — must check distinct color count, not just "frame exists"
8. **DIAG-VERIFY doesn't capture all calls** — Windows log showed 0 for NIDs that ARE called (logging gap)

---

# 12. Repository

```
GitHub: https://github.com/Sh-TB/sharpemuT24
Token: [REDACTED:github_token]
Default branch: main
Source path: work/sharpemuT24/src/
Binary: work/sharpemu-build/SharpEmu
```
