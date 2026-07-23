# Game Knowledge Transfer

Game: Arise
TitleID: 
Engine: Native C++

Current State: First Frame (Splash)
Boot Progress: 85%
First Frame: YES
VideoOut: YES

## Blocker
Missing game data files (bigfile.bfdb)

## Notes
Splash 3840x2160

## Reproduction
```bash
export SHARPEMU_APP0_DIR=/path/to/app0
export SHARPEMU_SEMA_FAST_PATH=1
./SharpEmu --log-level=info /path/to/eboot.bin
```

## Confidence
High
