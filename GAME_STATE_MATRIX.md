# Game State Matrix (Permanent — Never Delete)

## Current Status (as of EXP-015)

| # | Game | Engine | Coverage | Critical miss | First Frame | Status |
|---|------|--------|----------|---------------|-------------|--------|
| 1 | Dreaming Sarah | Native C++ | 75% | 0 | ✅ 3840×2160 | Working (golden test) |
| 2 | Arise | Native C++ | 50% (libc.prx encrypted) | 0 | ✅ 3840×2160 (historically) | ⚠️ SIGILL crash in EXP-015 (regression?) |
| 3 | Yatzi (PPSA17697) | Unity IL2CPP | 77.8% | 0 | ✅ 1920×1080 (Unity splash) | Working |
| 4 | Seeker My Shadow (PPSA12500) | Unity IL2CPP | 66.7% | 0 | ✅ 1920×1080 (Unity splash) | NEW — Working |
| 5 | Harvest Days | Native C++ (libc encrypted) | 75% | 0 | ✅ 1920×1080 (Unity splash) | NEW — Working |
| 6 | PPSA06699 | Unknown | N/A | N/A | N/A | ❌ eboot.bin encrypted |

**5 games now reach first frame!** (was 3 before EXP-015)

## EXP-013 Finding (2026-07-23)

Providing the real `globalgamemanagers` Media files (user uploaded for PPSA17697) lets Unity proceed past the file-open stage on Harvest Days, but the game still crashes in VFX Graph initialization:
- Crash at RIP=0x80081ACFC (`mov edi,[rbx+rcx]`, RBX=0, RCX=0)
- 100,000+ "unmapped read recovery" events in an infinite loop
- Stack strings: "FXExpressionValuesProxy", "Allocator", "ProfilerMarker", "VisualEffectAssetProxy", "Unity.Collections"
- Root cause: SharpEmu's IL2CPP runtime returns NULL for class registry lookups (117 unique icalls return NULL including `il2cpp_class_from_name`, `il2cpp_class_get_methods`, etc.)
- VFX Graph searches the NULL class registry in a loop → infinite loop → crash

**User's hypothesis partially confirmed:** missing Media files were a real blocker, but providing them reveals the next blocker (IL2CPP class registry).

## EXP-014: PPSA17697 (Yatzi) First Frame Achieved (2026-07-23)

User uploaded the 8 required PRX modules (decrypted ELF, magic `0x7f454c46`):
- sce_module/{libc.prx, libSceNpCppWebApi.prx}
- Media/Modules/{Il2cppUserAssemblies.prx (74.7 MB), PS5Util.prx}
- Media/Plugins/{lib_burst_generated.prx, PSNCommon.prx, PSNCore.prx, SaveData.prx}
- sce_sys/about/right.sprx

Also created dummy Unity files: boot.config, RuntimeInitializeOnLoads.json, ScriptingAssemblies.json, Resources/unity default resources, Resources/unity_builtin_extra, UnitySubsystems/, Metadata/, StreamingAssets/aa/.

**Result: 🎉 FIRST FRAME ACHIEVED** at 1920x1080 in headless mode (`SHARPEMU_HEADLESS=1`).
- Frame file: `SharpEmu/headless_frames/frame000001.ppm` (8.3 MB RGBA8)
- PNG converted: `download/ppsa17697_first_frame.png`
- 99.98% of pixels are (229, 95, 68) — Unity orange/red splash background
- 380 pixels are white — likely UI text or splash logo pixels
- Game reaches 500K+ imports processed in main loop (semaphores + mutexes + audio + clock)

**Key insight:** `SHARPEMU_SEMA_FAST_PATH=1` BREAKS Yatzi. The fast-path returns 0 (NULL pointer) which Unity then tries to call through → NULL execute fault. Without fast path, semaphores work correctly via real `sceKernelWaitSema` implementation.

**This is the 3rd game to reach first frame** in SharpEmu:
1. Dreaming Sarah — 3840x2160 (guest frame)
2. Arise — 3840x2160 (splash screen)
3. Yatzi (PPSA17697) — 1920x1080 (Unity splash) ← NEW

## EXP-013c: PPSA17697 (Yatzi) Decrypted eboot Test (2026-07-23)

User uploaded `-PPSA17697-app0-(Fix)decrypted.rar` containing a properly decrypted eboot.bin (ELF magic `0x7f454c46`).
Tested it with the previously-extracted real Media files (globalgamemanagers + .assets + .resS).

**Result:**
- ✅ ELF loads successfully (entry=0x800000070, 605 imports resolved)
- ✅ Gets to Import #1259 (sceSysmoduleLoadModule)
- ❌ Crashes when scheduling `AssetGarbageCollectorHelper` threads with RIP=0x0 (NULL execute fault)
- ❌ Only 1 file open (/dev/urandom) — game never reaches globalgamemanagers loading stage

**Root cause:** Missing 8 PRX modules that must be present in the app0 directory:
1. `sce_module/libc.prx` (5148 symbols)
2. `sce_module/libSceNpCppWebApi.prx` (84974 symbols)
3. `Media/Modules/Il2cppUserAssemblies.prx` (592 symbols, **CRITICAL** — contains IL2CPP compiled code)
4. `Media/Modules/PS5Util.prx` (10 symbols)
5. `Media/Plugins/lib_burst_generated.prx` (80 symbols)
6. `Media/Plugins/PSNCommon.prx` (128 symbols)
7. `Media/Plugins/PSNCore.prx` (18 symbols)
8. `Media/Plugins/SaveData.prx` (56 symbols)

**Evidence:** User's own Windows run (PPSA17697-20260721-152128.log) with the same eboot + full app0 directory loaded all 8 modules, got past the AssetGarbageCollectorHelper thread scheduling, reached Import #100000, allocated direct memory, and scheduled IL2CPP threads. Our run is missing exactly the 8 PRX modules.

**Rule applied (Evidence-Driven File Request):** Requesting these 8 specific PRX files from the user, not the entire 5GB game.

## EXP-013b: Repo Bloat Investigation (2026-07-23)

Release v0.0.3 source archive was 91.5 MB because the git working tree was the entire /home/z/my-project/ workspace and tracked:
- `artifacts/` — 725 files, 311 MB (build output: DLLs, .so, executables)
- `skills/` — 988 files, 33.6 MB (Claude/Z.ai agent skill definitions, not emulator code)
- `scripts/ps5_names.txt` — 11 MB (generated symbol table)
- `logs/` — 5 files, 6 MB (runtime dumps including BMP frames)
- `commands/`, `SharpEmu/diagnostics/`, `scripts/` — small local files

**Fix applied (commit 9dae9e2):**
- Added proper .gitignore at repo root and at work/sharpemuT24/
- `git rm -r --cached` for all workspace-local dirs
- Created GitHub release v0.0.5

**Result:**
- Before: 91.5 MB tar.gz, ~95 MB zip, 1417 tracked files
- After: **931 KB tar.gz, 1.15 MB zip**, 383 tracked files
- **98.98% size reduction**

## What "First Frame" Means

- **Dreaming Sarah**: "presented guest frame" = actual game rendering ✅
- **Arise**: "presented first frame" = splash screen (game's pic0.png). The GPU pipeline works. Game needs real data files to render its own content.

## Last Known Good Commits

- `8a5ef94` — Arise renders first frame (save data path fix)
- `5743683` — All 4 games running, 2 with first frame
- `92c9c23` — Frame dump enabled for debugging

## Backup Tags

- `backup/arise-first-frame-working` — Arise first frame milestone
- `backup/before-next-experiment` — Before any new changes

## Key Environment Variables

```
SHARPEMU_APP0_DIR=/path/to/app0     # Required for /app0/ path resolution
SHARPEMU_SEMA_FAST_PATH=1           # Bypass semaphore waits (Unity games)
SHARPEMU_DUMP_VIDEOOUT=1            # Dump VideoOut frames as BMP
SHARPEMU_HEADLESS=1                 # Use headless presenter (saves PPM)
SHARPEMU_LOG_STDIO=1                # Trace file open/close
VK_ICD_FILENAMES=...lvp_icd.json    # Lavapipe software Vulkan
DISPLAY=:99                         # Xvfb display
```

## Save Data Paths

```
/home/z/my-project/work/sharpemu-build/user/savedata/268435456/{game}/SaveData/
```

## Game Data Files Needed

### Arise
- /app0/resources/cookeddata/bigfile.bfdb
- /app0/resources/shaders/2d/*.ags
- /app0/resources/texts/*.strings

### Harvest Days / New Game (Unity)
- Real IL2CPP runtime (not just fake stubs)
