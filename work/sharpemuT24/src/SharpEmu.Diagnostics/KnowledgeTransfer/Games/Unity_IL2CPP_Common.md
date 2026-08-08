# Unity/IL2CPP Common Issue — Knowledge Transfer

## Affected Games
- Harvest Days (PPSA14677)
- Seeker My Shadow (PPSA12500)
- Yatzi (PPSA17697)

## Common Pattern
All three games are Unity/IL2CPP and share the same boot progression:
1. ELF Loading ✅
2. Import Resolution ✅
3. CRT/C++ ABI ✅
4. IL2CPP PRX Load ✅
5. Unity Thread Creation ✅ (with SHARPEMU_SEMA_FAST_PATH=1)
6. Static Init ⚠️ (IL2CPP stubs return NULL)
7. Semaphore Sync ❌ (deadlock without fast path)
8. VideoOut ❌

## Root Cause
IL2CPP fake heap stubs return 0 (NULL) for functions that should return
real Unity objects (Il2CppClass, Il2CppObject, etc.). The game stores these
NULLs and loops on field access from NULL, causing infinite unmapped memory
faults.

## Evidence
- RDI=0x0000000000000000 at crash site
- Instruction: `cmp byte ptr [rdi+0x1836], 0` — accessing field at offset 0x1836 from NULL
- 100,000+ unmapped memory recoveries before process crash
- Same pattern in all three games

## Applied Fixes (Do Not Remove)
1. IL2CPP fake heap (64KB, 232 stubs, vtable, fake objects)
2. NULL execute fault recovery (TryRecoverNullExecuteFault)
3. Unmapped memory read/write recovery (TryRecoverUnmappedMemoryRead)
4. Sema fast path (SHARPEMU_SEMA_FAST_PATH=1)
5. _Execute_once stub (marks complete without callback)
6. C11SyncExports (_Mtx_init, _Cnd_init, srand)
7. MessengerCompatExports (time, cosf, puts, _Getptolower, _Getptoupper)
8. PR #542 IL2CPP dispatch fix

## Suspected Solution
1. Implement real _Execute_once callback via GuestThreadExecution.Scheduler.TryCallGuestFunction
2. Verify guest thread scheduler actually runs worker threads when main thread blocks
3. Make IL2CPP fake objects larger or return valid mapped memory for field accesses
4. Implement real semaphore scheduling (not just fast path bypass)

## Do Not Retry
- Import resolution (all NIDs resolved)
- CRT stubs (cosf, time, puts, etc. working)
- AGC initialization (not reached yet)
- GPU pipeline (not reached yet)
