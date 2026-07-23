---
Task ID: EXP-013c
Agent: main (SharpEmu bringup)
Task: Test PPSA17697 (Yatzi) with the user-provided decrypted eboot.bin (Fix .rar) and verify whether the game can run further than the encrypted version.

Work Log:
- User uploaded `-PPSA17697-app0-(Fix)decrypted.rar` containing a decrypted eboot.bin (32,697,964 bytes).
- Extracted to /tmp/games/ppsa17697-decrypted/eboot.bin.
- Verified magic bytes: `7f454c46` = ELF magic. This is a real decrypted ELF (not encrypted SELF).
- Copied the previously-extracted real Media files (globalgamemanagers + globalgamemanagers.assets + globalgamemanagers.assets.resS) from /tmp/games/ppsa17697/Media/ into /tmp/games/ppsa17697-decrypted/Media/.
- Ran SharpEmu with SHARPEMU_APP0_DIR=/tmp/games/ppsa17697-decrypted, SHARPEMU_SEMA_FAST_PATH=1, SHARPEMU_LOG_OPEN=1, SHARPEMU_LOG_IL2CPP_NULL=1, 90s timeout.
- Result:
  - ✅ ELF loads successfully (entry=0x800000070)
  - ✅ 605 imports resolved
  - ✅ Reach Import #1259 (sceSysmoduleLoadModule call)
  - ❌ Crashes immediately when scheduling `AssetGarbageCollectorHelper` threads
  - Crashes with RIP=0x0 (NULL execute fault), 100,000+ recoveries in infinite loop
  - Only 1 file open (`/dev/urandom`) — game never tries to open globalgamemanagers
  - Crash host thread name: 'SharpEmu-AssetGarbageCollectorHelper'
- Compared against the user's own PPSA17697 run log (PPSA17697-20260721-152128.log) which they ran on Windows with the FULL app0 directory including sce_module/, Media/Modules/, Media/Plugins/.
- The user's run got dramatically further:
  - Loaded 8 PRX modules: libc.prx, libSceNpCppWebApi.prx, Il2cppUserAssemblies.prx, PS5Util.prx, lib_burst_generated.prx, PSNCommon.prx, PSNCore.prx, SaveData.prx
  - Module preload summary: loaded=8, failed=0, merged_imports=3047, merged_symbols=91001
  - Reached the same AssetGarbageCollectorHelper thread scheduling point but threads actually executed
  - Got to Import #100000 (memcpy)
  - Allocated direct memory (allocate_direct/map_direct sequence)
  - Scheduled Thread-1F5968E3CC0 with entry=0x000001FD92DF3AA0 (inside Il2cppUserAssemblies.prx)
- Root cause of our crash:
  - We only have eboot.bin in our app0 directory
  - The loader searches for PRX modules in: <app0>/sce_module/, <app0>/Media/Modules/, <app0>/Media/Plugins/
  - None of these directories exist in our setup
  - Without Il2cppUserAssemblies.prx (which contains the actual IL2CPP compiled code + Unity assemblies), the AssetGarbageCollectorHelper thread entry point resolves to NULL → NULL execute fault
  - This is NOT an emulator bug — it's missing game data

Stage Summary:
- ✅ User's "Fix" decrypted eboot.bin IS valid and decryptable by SharpEmu (ELF magic 0x7f454c46).
- ✅ The crash we see now is purely due to missing PRX modules — game data issue, not emulator issue.
- The user's tree structure (provided in chat) shows the decrypted app0 contains:
  - decrypted/eboot.bin
  - decrypted/Media/Modules/{Il2cppUserAssemblies.prx, PS5Util.prx}
  - decrypted/Media/Plugins/{lib_burst_generated.prx, PSNCommon.prx, PSNCore.prx, SaveData.prx}
  - decrypted/sce_module/{libc.prx, libSceNpCppWebApi.prx}
- These 8 PRX files are mandatory for SharpEmu to proceed past the AssetGarbageCollectorHelper scheduling stage.
- Next step: request the user to upload these specific 8 PRX files (not the entire 5GB game).
- Artifacts produced:
  - /home/z/my-project/SharpEmu/diagnostics/exp-013c/exp-013c-ppsa17697-decrypted.log
  - /tmp/PPSA17697-20260721-152128.log (extracted user log for comparison)
