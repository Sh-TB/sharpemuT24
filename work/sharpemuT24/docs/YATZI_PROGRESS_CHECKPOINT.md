# Yatzi Progress Checkpoint

**Date:** 2026-07-25
**Game:** Yatzi (PPSA17697)
**Engine:** Unity IL2CPP 2022.3.5f1

---

## Environment

| Component | Value |
|-----------|-------|
| SharpEmu commit | `e650fe6` (main branch) |
| Binary MD5 | `fe5280e375cb2563c84f2ba7eedabce0` |
| Build date | 2026-07-25 |
| .NET version | 10.0.302 |
| Xvfb | Running on `:99` (1920x1080x24) |
| Vulkan | Lavapipe (mesa-vulkan-drivers 25.0.7-2+deb13u1, LLVM 19.1.7) |
| Vulkan ICD | `/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json` |

---

## Yatzi Test Status

```
BOOT → UNITY INIT → VIDEOOUT FRAME PRESENTED
```

### Reproducibility (3 runs, 15s each)

| Metric | Run 1 | Run 2 | Run 3 |
|--------|-------|-------|-------|
| UNMAPPED faults (ErrorShader) | 0 | 0 | 0 |
| VideoOut first frame | ✅ | ✅ | ✅ |
| Threads scheduled | 52 | 52 | 52 |
| NID loop (1D0H2KNjshE) | 60343 | 60343 | 60343 |
| NID loop (hsi9drzHR2k) | 19968 | 19968 | 19968 |
| CreateWorkload TODO printed | ✅ | ✅ | ✅ |

**Result: 100% reproducible. No crashes in any run.**

---

## Confirmed Fixes (without code changes)

All fixes were achieved by providing missing game data files. No SharpEmu source code was modified for these fixes.

| Fix | How | Verification |
|-----|-----|--------------|
| ✅ PRX decoded loading | User provided `decrypted.part01-04.rar` with real ELF PRX files | Il2cppUserAssemblies.prx (74MB) loads as ELF, not encrypted SELF |
| ✅ IL2CPP initialization | PRX loading enables IL2CPP bootstrap | IL2CPP class loading reaches VFX Graph types |
| ✅ globalgamemanagers loading | User provided `globalgamemanagers.assets.zip` (3 files) | hash_lookup crash (0x80080684D) resolved |
| ✅ unity_builtin_extra loading | User provided real 820KB file | File opened (fd=9), stat=found, parsed by Unity |
| ✅ unity default resources loading | User provided real 859KB file | Contains `Hidden/InternalErrorShader` string |
| ✅ Internal-ErrorShader crash resolved | Both resource files now have real content | UNMAPPED at 0x800B28A0D = 0 (was 5) |
| ✅ hash_lookup NULL crash resolved | globalgamemanagers.assets provides type registry | UNMAPPED at 0x80080684D = 0 |
| ✅ UNMAPPED faults = 0 | All resource files present | Zero UNMAPPED events in all 3 runs |
| ✅ VideoOut first frame presented | Game reaches rendering init | "Vulkan VideoOut presented first frame: 1920x1080" |
| ✅ 52+ Unity threads created | Full Unity runtime active | AssetGC(13), Job.workers(10+16), GfxDeviceWorker, GfxFlipThread, FMOD(3), etc. |

---

## Asset Integrity (SHA256)

```
eboot.bin:                          d17fba4abc7858495c6f6e207b5c38961eec0c4639b04369f0c7b06866d80b6c
globalgamemanagers:                 00222aed9de394c23e801dac7eb3845dddf879ff0effd0d43358b87433a01642
globalgamemanagers.assets:          5d1b9a14413a039a8e583509ebebbb5dcfa59e45bc77b608dee264540c57828a
globalgamemanagers.assets.resS:     dfc02544d0e2cfb668c0c33199b41f5254250778490a38b68413eb20ba360cc3
unity_builtin_extra:                4a2bc13172ebd82941dba212504e7f16aee9cccbf622560c678f62cac26ac16d
unity default resources:            bee4d14e68eeda4b99de49b7b6183cd1a4050797f66b4e660192de7ef08453d3
level0:                             dc06e3a01c1ffd111d19d3ad9735e9092fe4d693f0a3bfd9defbb0ca124c4064
sharedassets0.assets:               df0b186426fd401c3df95053c0c193f61b168800d139a1db62e743084d7a517b
global-metadata.dat:                4c85fdec4efdb59534ab20af49615a36cbeef549f2f8de0431d78dbc5f21d918
Il2cppUserAssemblies.prx:           d73b3fc7236fb2ee68e979bc96f169ac5a3c26df4036dfdb9424f28643b9598d
libc.prx:                           0848522a4532aca6e64f6208483f678633dac7bb65f08910f29716a7da5090d6
```

**Note:** `unity default resources` has Unity version 2022.3.2f1 (not 2022.3.5f1).
This is a minor version mismatch but the file works because built-in shaders
are compatible across 2022.3.x patch versions.

---

## Diagnostic Snapshot

### NID unresolved count
3 unresolved imports (same as before — not game-blocking)

### NID loop counters
```
1D0H2KNjshE = 60343 calls
hsi9drzHR2k = 19968 calls
```
These are Unity's internal processing loop (NOT error handler — corrected from
previous analysis). The loop completes naturally in ~2 seconds.

### AGC/GPU counters
```
sceAgcDriverSubmitDcb = 0
sceAgcDcbDrawIndexOffset = 0
sceVideoOutSubmitFlip = 0
```
**No AGC calls. No GPU rendering.** Game reaches render initialization but
does not submit any GPU work.

### VideoOut counters
```
presented first frame = 1 (1920x1080)
presented guest frame = 1 (image=0x10B20000)
```

### Thread list (52 threads)

| Thread type | Count |
|-------------|-------|
| AssetGarbageCollectorHelper | 13 |
| Background Job.worker | 16 |
| Job.worker | 10 |
| FMOD (mixer, AudioOut, stream) | 3 |
| UnityGfxDeviceWorker | 1 |
| UnityEOPThread | 1 |
| GfxFlipThread | 1 |
| Loading.PreloadManager | 1 |
| Loading.AsyncRead | 1 |
| BatchDeleteObjects | 1 |
| Other | 3 |

### File opens (successful)

| fd | Path |
|----|------|
| 5 | `/app0/Media/globalgamemanagers` |
| 6 | `/app0/Media/Resources/unity default resources` |
| 7,8 | `/app0/Media/globalgamemanagers.assets` |
| 9 | `/app0/Media/globalgamemanagers.assets.resS` |
| 10 | `/app0/Media/Resources/unity_builtin_extra` |
| 11 | `/app0/Media/sharedassets0.assets` |
| 12 | `/app0/Media/level0` |

### Crash state
**No crashes.** Zero UNMAPPED faults. Game runs indefinitely in audio/mutex loop.

### CreateWorkload
```
[DEBUG][PRINF] todo: void GfxDevicePS5SharedData::CreateWorkload()
```
This is a **Unity engine stub** (in eboot.bin) that prints a warning and
**continues execution**. It is NOT a crash, NOT an abort, and NOT confirmed
as the blocker. Game execution continues past it.

---

## Current Blocker

```
No crash.
Game reaches render initialization.

Remaining issue:
No AGC/DCB submission.
AGC counters remain zero.

Observed loop:
scePthreadMutexLock
  → sceAudioOutOutput
  → sceKernelClockGettime
  → sceKernelWaitSema
  → repeat
```

### CreateWorkload is NOT confirmed blocker

CreateWorkload TODO is a printf stub in Unity engine code.
Observed execution continues after it.
The PLT call at `0x8019369b0` (immediately after CreateWorkload printf)
resolves to an imported function that needs investigation.

### Next investigation step

1. Resolve PLT call `0x8019369b0` to its NID
2. Check if that NID is a stub returning NULL/0 in SharpEmu
3. If so, implement proper HLE for it
4. Test if AGC calls start happening after the fix

---

## Golden Test Result (Dreaming Sarah)

| Metric | Value |
|--------|-------|
| Frame count | 288 (min: 50) ✅ |
| Max distinct colors | 910 (min: 50) ✅ |
| GLFW X11 backend | ✅ |
| Vulkan VideoOut | ✅ |
| **Result** | **✅ GOLDEN TEST PASSED** |

No regression. Dreaming Sarah renders correctly with 910 distinct colors.

---

## Milestone Summary

```
Phase 1: Boot + PRX + IL2CPP                    ✅ Complete
Phase 2: Unity Assets + Shader Resources        ✅ Complete
Phase 3: Unity Runtime → GPU Workload           ⬅️ Current
```

Yatzi is the first Unity IL2CPP game to reach VideoOut frame presentation
in SharpEmu. This checkpoint establishes it as a regression test for
future Unity IL2CPP compatibility work.
