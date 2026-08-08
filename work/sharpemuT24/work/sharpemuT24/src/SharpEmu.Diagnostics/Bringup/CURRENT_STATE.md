# Current State — SharpEmu Bringup

## Last Updated: 2026-07-23T18:20:00Z
## Commit: 28c09db

## Game Status

| Game | TitleID | Engine | Status | First Frame | Boot % |
|------|---------|--------|--------|-------------|--------|
| Dreaming Sarah | PPSA02929 | Native C++ | ✅ Working | ✅ 3840x2160 (guest) | 100% |
| Arise | PPSA06328 | Native C++ | ✅ First Frame | ✅ 3840x2160 (splash) | 85% |
| Harvest Days | PPSA14677 | Unity/IL2CPP | 🟡 Running | ❌ | 60% |
| Seeker My Shadow | PPSA12500 | Unity/IL2CPP | 🟡 Running | ❌ | 60% |
| Yatzi | PPSA17697 | Unity/IL2CPP | 🟡 Running (user) | ❌ | 70% |
| PPSA06699 | PPSA06699 | Unknown | ❌ Encrypted | N/A | 0% |

## Common Blocker: Unity/IL2CPP Startup Deadlock

Three Unity games (Harvest Days, Seeker My Shadow, Yatzi) share the same pattern:

```
ELF Load          ✅
Imports Resolve   ✅
CRT/C++ ABI       ✅
IL2CPP Load       ✅
Unity Threads     ✅ (with SHARPEMU_SEMA_FAST_PATH=1)
Static Init       ⚠️ (IL2CPP fake stubs return NULL)
Semaphore Sync    ❌ (deadlock without fast path)
VideoOut          ❌
First Frame       ❌
```

## Root Cause Analysis

### Problem 1: IL2CPP Fake Heap Returns NULL
- IL2CPP fake stubs return 0 for functions that should return Unity objects
- Game stores NULL pointers and loops on field access from NULL
- Example: `cmp byte ptr [rdi+0x1836], 0` where rdi=0 (NULL)
- Results in 100,000+ unmapped memory recoveries before crash

### Problem 2: Semaphore Deadlock (without fast path)
- Without SHARPEMU_SEMA_FAST_PATH=1, game blocks on sceKernelWaitSema
- Worker threads are created but scheduler may not switch to them
- Game deadlocks waiting for semaphore signal that never comes

### Problem 3: _Execute_once Stub
- Current stub marks once_flag as complete without calling guest callback
- Unity expects callback to execute for static initialization
- Without real callback, static constructors never run

## Next Experiments (Priority Order)

### EXP-009: Semaphore Investigation
- Test with SHARPEMU_LOG_SEMA=1 to trace all semaphore operations
- Determine if worker threads actually run when main thread blocks
- Check if GuestThreadExecution.RequestCurrentThreadBlock yields properly

### EXP-010: Real _Execute_once Callback
- Implement real callback execution using GuestThreadExecution.Scheduler.TryCallGuestFunction
- This is the upstream PR #542 approach
- May unlock Unity static initialization

### EXP-011: Guest Thread Scheduler Verification
- Verify that Pump() actually runs ready threads when a thread blocks
- Add logging: [GUEST_THREAD_CREATE], [GUEST_THREAD_START], [SEMA_WAIT], [SEMA_SIGNAL]
- Determine if threads are created but never started

### EXP-012: IL2CPP Fake Object Enhancement
- Make fake objects larger (8KB each instead of 256 bytes)
- Or: return a pointer to a pre-mapped zeroed region for field accesses
- This would prevent the NULL+0x1836 crash loop
