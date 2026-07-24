# Harvest Days (PPSA14677)

## Status: 🟡 RUNNING (IL2CPP Block)

## Boot Progress
```
ELF Loading        100%
Imports            100% (~948)
HLE                80%
Memory             70% (15 NULL recoveries, 45 unmapped)
IL2CPP             BLOCKED
Threads            Stuck (AssetGarbageCollectorHelper)
GPU                Not reached
VideoOut           Not reached
First Frame        NO
```

## Blocker: IL2CPP static initialization loop

### Root Cause
- IL2CPP fake heap prevents crashes but can't execute C# code
- Game stuck calling __cxa_guard_acquire/_release in a loop
- Worker threads waiting on semaphores that never get signaled
- _Execute_once stub marks flag as complete without calling callback

### What's Working
- ELF loading OK
- libc.prx loaded
- IL2CPP fake heap generates 232 stubs
- NULL execute recovery (15 faults recovered)
- Unmapped memory recovery (45 faults recovered)
- Sema fast path bypasses semaphore waits

### What's Missing
- Real IL2CPP runtime (metadata parser, method resolver, static constructor execution)
- _Execute_once callback execution (needs GuestThreadExecution.Scheduler.TryCallGuestFunction)
- Real thread initialization for Unity worker threads

## Key Fixes Applied
1. IL2CPP fake heap (64KB + vtable + fake objects + 232 stubs)
2. NULL execute fault recovery
3. Unmapped memory read/write recovery
4. Sema fast path
5. C11SyncExports (_Mtx_init, _Cnd_init, srand)
6. _Execute_once stub (marks complete without callback)
7. MessengerCompatExports (cosf, puts, time, etc.)

## Test Command
```bash
export SHARPEMU_APP0_DIR=/tmp/games/harvest
export SHARPEMU_SEMA_FAST_PATH=1
./work/sharpemu-build/SharpEmu --log-level=info /tmp/games/harvest/eboot.bin
```

## Next Steps
1. Implement real _Execute_once callback (call guest function)
2. Add more CRT functions (sinf, sqrtf, fabsf, memcpy, memset, strlen)
3. Track IL2CPP static constructor execution
4. Target: Unity worker threads start → VideoOut
