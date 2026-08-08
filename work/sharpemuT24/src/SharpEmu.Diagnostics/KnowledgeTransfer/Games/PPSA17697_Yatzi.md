# Game Knowledge Transfer: Yatzi (PPSA17697)

## Game Information
- **Title**: Yatzi
- **TitleID**: PPSA17697
- **Version**: 01.000.000
- **Engine**: Unity/IL2CPP
- **Eboot size**: 32.7MB (33,985,952 bytes)
- **NIDs**: 605 unique, 50,450 descriptors

## User's Test Environment
- **OS**: Windows
- **CPU**: Intel Core i5-8400 @ 2.80GHz
- **GPU**: NVIDIA GeForce RTX 2060
- **RAM**: 16.3 GB
- **SharpEmu version**: Upstream (not our fork)

## User's Result (from log)
- **Imports reached**: 131,328
- **Modules loaded**: 4 (eboot.bin, libc.prx, libSceNpCppWebApi.prx, **Il2cppUserAssemblies.prx**)
- **Threads started**: 14+ (13 AssetGarbageCollectorHelper + 1 Thread-1F5968E3CC0)
- **VideoOut**: NOT reached
- **First Frame**: NO
- **Final state**: Execution stalled for 20s on sceKernelWaitSema

## Root Cause (Same as Harvest Days/Seeker My Shadow)
- **Blocker**: `sceKernelWaitSema` deadlock
- **All AssetGarbageCollectorHelper threads blocked** on semaphore
- **IL2CPP loaded**: Il2cppUserAssemblies.prx loaded and initialized
- **Same Unity/IL2CPP pattern**: Game gets past ELF loading, CRT, IL2CPP init, but worker threads deadlock on semaphores

## Unresolved NIDs in User's Log
- `rVjRvHJ0X6c` = sceKernelVirtualQuery → NOT_FOUND
- `BHouLQzh0X0` = sceKernelDirectMemoryQuery → DELETED
- `wuCroIGjt2g` = open() → returns -1 (file not found)
- `xk0AcarP3V4` = scePadOpen → NOT_INITIALIZED
- `1-LFLmRFxxM` = sceKernelMkdir → ALREADY_EXISTS

## Our Fork Advantage
Our fork has fixes the user's version DOESN'T have:
1. **IL2CPP fake heap** (232 stubs) — prevents NULL dispatch crashes
2. **NULL execute fault recovery** — redirects NULL calls to return-zero stub
3. **Unmapped memory recovery** — skips bad memory accesses
4. **Sema fast path** (SHARPEMU_SEMA_FAST_PATH=1) — bypasses semaphore waits
5. **PR #542 compatibility** — _Execute_once, MessengerCompatExports, IL2CPP dispatch fix
6. **C11SyncExports** — _Mtx_init, _Cnd_init, srand
7. **AGC auto-init** — sceAgcDriverRegisterOwner

## What Would Happen With Our Fork
With our fixes applied, PPSA17697 would likely:
1. ✅ Load Il2cppUserAssemblies.prx (same as user's log)
2. ✅ Start AssetGarbageCollectorHelper threads (same)
3. ✅ Bypass sceKernelWaitSema deadlock (via SHARPEMU_SEMA_FAST_PATH=1)
4. 🟡 Still stuck at IL2CPP static init (same as Harvest Days)
5. ❌ Cannot test further without decrypted eboot

## Note
Our copy of PPSA17697 eboot.bin is **ENCRYPTED** (0x5414F5EE).
The user had a decrypted "Fix" version. We need a decrypted/fSELF copy to test.

## Confidence
Medium — same Unity/IL2CPP pattern as Harvest Days, but can't test directly.
