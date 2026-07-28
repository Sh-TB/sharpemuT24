# Game Knowledge Transfer

Game: New Unity Game
TitleID: Unknown

Engine: Unity/IL2CPP

Current State: Running (IL2CPP static init block)

Boot Progress: 60%

First Frame: NO
VideoOut: NO

## Timeline

Import Start: 0
Import Crash: none (1005 NULL recoveries)

Thread Status: Stuck (AssetGarbageCollectorHelper threads waiting)
Memory Status: 1005 NULL recoveries
GPU Status: Not reached

## Root Cause

Problem: Same IL2CPP static initialization deadlock as Harvest Days

Evidence:
- 2 unique NIDs called (tsvEmnenz48, AcslpN1jHR8)
- AcslpN1jHR8 (scePadDeviceClassGetExtendedInformation) still unresolved
- 1005 NULL faults recovered (more than Harvest Days)
- Same Unity/IL2CPP pattern

## Fixed Items

Same as Harvest Days (shared Unity compatibility layer).

## Remaining Blockers

1. Same as Harvest Days — IL2CPP static init deadlock
2. AcslpN1jHR8 (scePadDeviceClassGetExtendedInformation) needs implementation

## Next Experiment

Goal: Same as Harvest Days — fix IL2CPP, this game should follow

## Reproduction Command

```bash
export SHARPEMU_APP0_DIR=/tmp/games/newgame
export SHARPEMU_SEMA_FAST_PATH=1
./work/sharpemu-build/SharpEmu --log-level=info /tmp/games/newgame/eboot.bin
```

## Regression Status

Before: Crash at import #7800
After: Running with 1005 NULL recoveries (no crash)

## Confidence

Medium
