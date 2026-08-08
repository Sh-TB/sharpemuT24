# SharpEmuT24 — Project Checkpoint v0.0.10

## CRITICAL FINDING: Windows Log Analysis

User provided Windows log (PPSA17697-20260721-152128.log) from upstream SharpEmu
running Yatzi on Windows with GPU. This log shows the **EXACT SAME** stall behavior
as our Linux environment.

### Windows vs Linux Comparison

| Metric | Windows (upstream) | Linux (our fork) |
|--------|-------------------|-----------------|
| VkqLPArfFdc | 0 calls | 0 (after stub) |
| 1D0H2KNjshE | 0 calls | 59 (our stub!) |
| hsi9drzHR2k | 0 calls | 21 (our stub!) |
| WaitSema | 15 | 5 |
| SignalSema | **0** | **0** |
| CreateSema | 28 | 24 |
| sceAgc | 0 | 0 |
| Stall | Yes (20s timeout) | Yes (infinite loop) |

### Key Insights

1. **VkqLPArfFdc was NOT called on Windows** — it was a red herring
2. **1D0H2KNjshE and hsi9drzHR2k are NOT called on Windows** — our Harvest Days stubs are interfering with Yatzi
3. **SignalSema = 0 on BOTH platforms** — this is the real blocker
4. **This is NOT a SharpEmu bug** — upstream has the same issue
5. **All 14 AssetGarbageCollectorHelper threads + 1 IL2CPP thread deadlock on WaitSema**

### What This Means

The Unity IL2CPP runtime creates 28 semaphores but never signals any of them.
This means the IL2CPP bootstrap never completes — something earlier in the
initialization chain is supposed to trigger the first SignalSema but doesn't.

The IL2CPP runtime thread (Thread-1F5968E3CC0) is also blocked, meaning
the runtime itself is waiting for something that never comes.

### Action Items

1. **Remove 1D0H2KNjshE and hsi9drzHR2k stubs** — they're Harvest Days specific, not needed for Yatzi, and may cause interference
2. **Keep VkqLPArfFdc stub** — harmless even if not needed
3. **Investigate why SignalSema is never called** — the IL2CPP runtime needs a trigger
4. **This is an upstream limitation** — not specific to our fork

## Golden Baseline

- Tag: golden-render-baseline (v0.0.9)
- Dreaming Sarah: ✅ PASS (138 frames, 167+ colors)
- Golden test: tests/golden/run-golden-tests.sh

## Game Status

| Game | Engine | Status | Blocker |
|------|--------|--------|---------|
| Dreaming Sarah | Native C++ | ✅ GOLDEN | None |
| Yatzi | Unity IL2CPP | ❌ Same as upstream | SignalSema=0 (IL2CPP bootstrap deadlock) |
| Seeker | Unity IL2CPP | ❌ Same | Same as Yatzi |
| Arise | Native C++ | ❌ | SIGILL crash |
| Harvest Days | Unity IL2CPP | ❌ | Encrypted PRX files |

## NID Stubs Added

| NID | Name | Needed? | Action |
|-----|------|---------|--------|
| VkqLPArfFdc | IL2CPP bootstrap | No (0 calls on Windows) | Keep (harmless) |
| GrQ9s4IrNaQ | sceAudioOutGetPortState | Maybe | Keep |
| MM4IZSEYytQ | sceAgcDriverSetHsOffchipParam | Maybe | Keep |
| XlNp7jzGiPo | sceAgcDriverSetTFRing | Maybe | Keep |
| xk0AcarP3V4 | scePadOpen | Yes (returns error) | Keep |
| 1-LFLmRFxxM | sceKernelMkdir | Yes | Keep |
| rVjRvHJ0X6c | sceKernelFindInternalFile | Yes | Keep |
| BHouLQzh0X0 | sceKernelFindInternalFileVariant | Yes | Keep |
| 1D0H2KNjshE | Harvest Days stub | **NO** (0 calls on Yatzi Windows) | **Remove** |
| hsi9drzHR2k | Harvest Days stub | **NO** (0 calls on Yatzi Windows) | **Remove** |

## Environment

- Linux headless (Debian, no physical GPU)
- Xvfb :99 1920x1080x24
- Lavapipe (llvmpipe, LLVM 19.1.7, software Vulkan)
- .NET SDK 10.0.302
- GLFW 3.4 with X11 platform hint (PR #457 fix)
- libX11 user-local install

## Key Commits

- f83b6ea — v0.0.9 (GLFW X11 fix + real frames)
- 17a0d05 — PreferX11OnLinuxWayland fix (PR #457)
- 3b2d499 — VkqLPArfFdc + 3 NID stubs
- b451ae9 — 4 more NID stubs
- 560301b — PROJECT_STATUS_v0.0.9.md
- golden-render-baseline tag at v0.0.9

## Next Steps

1. Remove 1D0H2KNjshE and hsi9drzHR2k stubs (Harvest Days only)
2. Run golden test to verify Dreaming Sarah still works
3. Investigate why SignalSema is never called in Unity IL2CPP
4. Look at what the IL2CPP runtime thread is waiting for
5. Compare with upstream — this is a known limitation, not our bug
