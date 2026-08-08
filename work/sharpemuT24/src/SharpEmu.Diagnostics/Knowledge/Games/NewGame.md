# New Unity Game (Unknown Title ID)

## Status: 🟡 RUNNING (IL2CPP Block)

## Boot Progress
```
ELF Loading        100%
Imports            100% (~773)
HLE                80%
Memory             70% (1005 NULL recoveries)
IL2CPP             BLOCKED
Threads            Stuck (AssetGarbageCollectorHelper)
GPU                Not reached
VideoOut           Not reached
First Frame        NO
```

## Blocker: IL2CPP static initialization loop (same as Harvest Days)

### Root Cause
- Same Unity/IL2CPP pattern as Harvest Days
- Game stuck in static init loop
- 1005 NULL faults recovered (more than Harvest Days)

### What's Different from Harvest Days
- More NULL recoveries (1005 vs 15)
- Same 5 unique NIDs called
- Same IL2CPP stubs generated (228)

## Key Fixes Applied
- Same as Harvest Days (shared Unity compatibility layer)

## Test Command
```bash
export SHARPEMU_APP0_DIR=/tmp/games/newgame
export SHARPEMU_SEMA_FAST_PATH=1
./work/sharpemu-build/SharpEmu --log-level=info /tmp/games/newgame/eboot.bin
```

## Next Steps
- Same as Harvest Days
- If Harvest Days reaches VideoOut, this game likely will too
