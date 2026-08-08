# Dreaming Sarah (PPSA02929)

## Status: ✅ COMPLETE (Golden Test)

## Boot Progress
```
ELF Loading        100%
Imports            100% (484 NIDs)
HLE                100%
Memory             100%
GPU Pipeline       100%
VideoOut           100%
Guest Frame        100% (3840x2160)
Gameplay           Running
```

## Blocker: None

## Key Notes
- This is the Golden Regression Test
- Must not break after any change
- Has full game data (images, data.js, etc.)
- Uses libc.prx from its own sce_module

## Test Command
```bash
export SHARPEMU_APP0_DIR=/home/z/my-project/upload/PPSA02929/PPSA02929-app0
./work/sharpemu-build/SharpEmu --log-level=info upload/PPSA02929/PPSA02929-app0/eboot.bin
```

## Expected Output
```
Vulkan VideoOut presented first frame: 3840x2160
Vulkan VideoOut presented guest frame: image=0x... 3840x2160
```
