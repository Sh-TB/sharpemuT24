# Game Knowledge Transfer

Game: [name]
TitleID: [PPSAxxxxx]
Engine: [Unity/IL2CPP/Native C++/Unknown]

Current State: [Crash/Boot/VideoOut/Splash/First Frame/Gameplay]
Boot Progress: [X]%
First Frame: [YES/NO]
VideoOut: [YES/NO]

## Timeline
Import Start: [number]
Import Crash: [number or "none"]
Thread Status: [running/blocked/stuck]
Memory Status: [OK/faults/recoveries]
GPU Status: [not reached/submitted/rendered]

## Root Cause
Problem: [description]
Evidence: [log lines, register state]
Crash Address: [0x... or "none"]

## Fixed Items
Commit: [hash]
Changed Files: [list]
Reason: [why this fix works]

## Remaining Blockers
1. [blocker 1]
2. [blocker 2]

## Next Experiment
Goal: [what to achieve]
Expected Result: [import count / VideoOut / first frame]
Files To Modify: [list]

## Reproduction Command
```bash
export SHARPEMU_APP0_DIR=/path/to/app0
export SHARPEMU_SEMA_FAST_PATH=1
./SharpEmu --log-level=info /path/to/eboot.bin
```

## Regression Status
Before: [PASS/FAIL for each game]
After: [PASS/FAIL for each game]

## Confidence
[Low / Medium / High]
