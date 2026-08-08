# AI Context — SharpEmuT24 (Read this first)

## Project
SharpEmu PS5 Emulator (C#/.NET 10)
Fork: https://github.com/Sh-TB/sharpemuT24
Release: v0.0.3 (https://github.com/Sh-TB/sharpemuT24/releases/tag/v0.0.3)

## Current Milestone
2/5 games render first frame

## Known Working (DO NOT BREAK)
- Dreaming Sarah: First frame 3840x2160 (guest frame) — Golden Test
- Arise: First frame 3840x2160 (splash screen) — GPU pipeline proven

## Running (IL2CPP block)
- Harvest Days: Running, 1 NID, unmapped recovers, IL2CPP static init deadlock
- Seeker My Shadow: Running, 2 NIDs, 1005 NULL recovers, same IL2CPP block

## Cannot Test
- PPSA06699: Encrypted retail eboot (needs fSELF/decryption)

## Never Remove
- IL2CPP fake heap (64KB, 232 stubs, vtable, fake objects)
- NULL execute fault recovery (TryRecoverNullExecuteFault)
- Unmapped memory read/write recovery (TryRecoverUnmappedMemoryRead)
- C11SyncExports (_Mtx_init, _Cnd_init, srand)
- MessengerCompatExports (time, cosf, puts, _Getptolower, _Getptoupper)
- _Execute_once (DiGVep5yB5w) in CxxAbiExports
- AGC auto-init for sceAgcDriverRegisterOwner
- Sema fast path (SHARPEMU_SEMA_FAST_PATH=1)
- SHARPEMU_APP0_DIR env var for /app0/ path resolution

## Key Environment
- DISPLAY=:99 (Xvfb, NOT :1)
- VK_ICD_FILENAMES=lvp_icd.json (Lavapipe software Vulkan)
- SHARPEMU_APP0_DIR=<per-game app0 directory>
- SHARPEMU_SEMA_FAST_PATH=1
- Save data: work/sharpemu-build/user/savedata/268435456/{game}/SaveData/

## Key Commits
- v0.0.3: All fixes + 5 game test + GitHub release
- milestone/2-games-first-frame: 2 games first frame proven
- milestone/pr542-applied: PR #542 compatibility applied

## Build
dotnet publish src/SharpEmu.CLI/SharpEmu.CLI.csproj -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true -o build

## Next Priority
1. Harvest Days → VideoOut (IL2CPP runtime)
2. Seeker My Shadow → VideoOut (same fix)
3. Arise → Gameplay (asset loading)
4. Keep Dreaming Sarah regression

## Main Blocker
IL2CPP static init deadlock: _Execute_once stub doesn't call guest callback.
Need GuestThreadExecution.Scheduler.TryCallGuestFunction for real callback execution.
