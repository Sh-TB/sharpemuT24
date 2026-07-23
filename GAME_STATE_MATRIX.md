# Game State Matrix (Permanent — Never Delete)

## Current Status

| Game | Status | First Frame | Import Count | Blocker |
|------|--------|-------------|--------------|---------|
| Dreaming Sarah | ✅ Working | ✅ 3840x2160 (guest frame) | 484 NIDs | None |
| Arise | ✅ First Frame | ✅ 3840x2160 (splash) | #114612 | Game data files |
| Harvest Days | 🟡 Running | ❌ | ~948 + 7172 unresolved | VFX Graph / IL2CPP class registry (EXP-013) |
| Seeker My Shadow | 🟡 Running | ❌ | ~773 | Same as Harvest Days (presumed) |
| Yatzi (PPSA17697) | ❌ Cannot test | N/A | N/A | **eboot.bin encrypted** (magic 0x5414F5EE) — need fSELF |
| PPSA06699 | ❌ Cannot test | N/A | N/A | **eboot.bin encrypted** — need fSELF |

## EXP-013 Finding (2026-07-23)

Providing the real `globalgamemanagers` Media files (user uploaded for PPSA17697) lets Unity proceed past the file-open stage on Harvest Days, but the game still crashes in VFX Graph initialization:
- Crash at RIP=0x80081ACFC (`mov edi,[rbx+rcx]`, RBX=0, RCX=0)
- 100,000+ "unmapped read recovery" events in an infinite loop
- Stack strings: "FXExpressionValuesProxy", "Allocator", "ProfilerMarker", "VisualEffectAssetProxy", "Unity.Collections"
- Root cause: SharpEmu's IL2CPP runtime returns NULL for class registry lookups (117 unique icalls return NULL including `il2cpp_class_from_name`, `il2cpp_class_get_methods`, etc.)
- VFX Graph searches the NULL class registry in a loop → infinite loop → crash

**User's hypothesis partially confirmed:** missing Media files were a real blocker, but providing them reveals the next blocker (IL2CPP class registry).

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
