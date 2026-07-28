# Arise (PPSA06328)

## Status: ✅ FIRST FRAME (Splash)

## Boot Progress
```
ELF Loading        100%
Imports            100% (#114612)
HLE                90%
Memory             90% (10 unmapped recoveries)
GPU Pipeline       100%
VideoOut           100% (3840x2160 splash)
Guest Frame        Partial (splash only)
Gameplay           Blocked
```

## Blocker: Missing game data files

### Required files (not available):
- /app0/resources/cookeddata/bigfile.bfdb
- /app0/resources/shaders/2d/*.ags
- /app0/resources/texts/*.strings

### Workaround: Empty dummy files created
- Game proceeds past file loading but can't render actual content
- Only splash screen (pic0.png) is shown

## Key Fixes Applied
1. SHARPEMU_APP0_DIR set to /tmp/arise-app0
2. Save data at work/sharpemu-build/user/savedata/268435456/arise/SaveData/
3. AGC auto-init for sceAgcDriverRegisterOwner
4. Unmapped memory recovery (10 faults)
5. 3 Arise NID stubs: McaImWKXong, bRujIheWlB0, Cj+Fw5q1tUo
6. Sema fast path enabled

## Test Command
```bash
export SHARPEMU_APP0_DIR=/tmp/arise-app0
# Ensure save data + dummy game data
./work/sharpemu-build/SharpEmu --log-level=info /tmp/arise-app0/eboot.bin
```

## Expected Output
```
Vulkan VideoOut presented first frame: 3840x2160
```

## Next Steps
- Need real game data files (bigfile.bfdb) for gameplay
- Asset loading pipeline investigation
- Shader cache loading
