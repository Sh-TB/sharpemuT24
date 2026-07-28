# Game Knowledge Transfer

Game: SeekerMyShadow
TitleID: 
Engine: Unity/IL2CPP

Current State: Running
Boot Progress: 60%
First Frame: NO
VideoOut: NO

## Blocker
IL2CPP static init deadlock

## Notes
2 NIDs, 1005 NULL rec

## Reproduction
```bash
export SHARPEMU_APP0_DIR=/path/to/app0
export SHARPEMU_SEMA_FAST_PATH=1
./SharpEmu --log-level=info /path/to/eboot.bin
```

## Confidence
Medium
