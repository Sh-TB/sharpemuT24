# Latest Test Report

Date: 2026-07-22T21:41:00Z
Commit: 60b18f0
Build: SharpEmu 53MB (fresh build at 21:41)

## Results

| Game | VideoOut | First Frame | NULL Rec | Unmapped Rec | Unique NIDs | Unresolved |
|------|----------|-------------|----------|--------------|-------------|------------|
| Dreaming Sarah | ✅ | ✅ (guest) | 0 | 0 | 484 | 0 |
| Arise | ✅ | ✅ (splash) | 0 | 6 | many | 0 |
| Harvest Days | ❌ | ❌ | 15 | 1005 | 1 | 0 |
| New Game | ❌ | ❌ | 1005 | 0 | 2 | 1 |

## Key Progress (EXP-008)

After fixing C11SyncExports access modifiers:
- Harvest Days: 3 unique NIDs → 1 (only __cxa_atexit remains)
- New Game: 5 unique NIDs → 2 (__cxa_atexit + scePadDeviceClassGetExtendedInformation)
- _Mtx_init and _Cnd_init are now RESOLVED
- _Getptolower is now RESOLVED

## Next Steps

1. Implement real _Execute_once callback (call guest function via scheduler)
2. Add more CRT functions (sinf, sqrtf, fabsf, memcpy, memset, strlen)
3. Implement scePadDeviceClassGetExtendedInformation for New Game
4. Target: Unity worker threads start → VideoOut
