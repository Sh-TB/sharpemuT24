# Game State Matrix (Permanent — Never Delete)

## Current Status

| Game | Status | First Frame | Import Count | Blocker |
|------|--------|-------------|--------------|---------|
| Dreaming Sarah | ✅ Working | ✅ 3840x2160 (guest frame) | 484 NIDs | None |
| Arise | ✅ First Frame | ✅ 3840x2160 (splash) | #114612 | Game data files |
| Harvest Days | 🟡 Running | ❌ | ~948 | IL2CPP init loop |
| New Game | 🟡 Running | ❌ | ~773 | IL2CPP init loop |

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
