---
Task ID: EXP-019 to EXP-040 (comprehensive diagnostic sweep)
Agent: main (SharpEmu bringup)
Task: Run all diagnostic experiments user requested. NO code changes — only log analysis and metadata validation.

User-uploaded new files:
- eker My Shadow 01.002 PPSA12500 level10.rar (172KB) → level10 + level10.resS for Seeker
- level0 (1404 bytes) → Unity scene file for Seeker (contains "2022.3.5f1" Unity version string)
- sharedassets0.assets (1548 bytes) → smaller sharedassets (kept the larger 26MB one already present)

Added these to Seeker app0 → ALL file opens now succeed for Seeker.

=== EXP-019: Metadata Validation ===
- Header dump: Magic 0xAF1BB1FA, version 0x1D (29) — newer IL2CPP metadata format
- Entropy: 5.54 bits/byte (Yatzi), 5.53 (Seeker) — STRUCTURED, NOT encrypted
- Strings scan: Both files contain valid Unity strings:
  * Yatzi: 4822 UnityEngine, 599 Camera, 259 GameObject, 370 Transform, 4 VisualEffectAsset, 19 SceneManager
  * Seeker: 3245 UnityEngine, 232 Camera, 141 GameObject, 346 Transform, 4 VisualEffectAsset, 16 SceneManager
- Conclusion: ✅ metadata files are VALID and UNENCRYPTED

=== EXP-020: IL2CPP Import Audit ===
- SHARPEMU_LOG_IL2CPP_NULL=1 and SHARPEMU_LOG_IL2CPP_STUBS=1 enabled
- Result: ZERO IL2CPP_NULL events, ZERO IL2CPP_STUB events
- Root cause: SharpEmu's IL2CPP fake heap is NEVER initialized
- Game's IL2CPP runtime is REAL code inside Il2cppUserAssemblies.prx (592 exports)
- Game does NOT call il2cpp_api_lookup_symbol — fake stubs are NEVER used
- Conclusion: ❌ Fake stubs are irrelevant; game uses its own real IL2CPP runtime

=== EXP-021 (CORRECTED): Semaphore Audit ===
- Earlier count was wrong (searched wrong text pattern)
- Correct counts from sema.* trace events:
  * sema.create: 340 (336 Baselib_SystemSemaphore, 4 FMOD Semaphore)
  * sema.wait-block: 4832
  * sema.wait-wake: 4785 (98.8% of waits were satisfied)
  * sema.signal: 4831 (signals DO happen — game logic IS running)
  * sema.wait-timeout: 0
  * sema.delete: 78
- Conclusion: ✅ NO DEADLOCK. Kernel scheduler works correctly. Game runs its main loop.

=== EXP-024: Semaphore Ownership Graph ===
- 47 semaphores have stuck waiters (never woken up at end of run)
- All stuck semaphores are "Baselib_SystemSemaphore" (Unity worker pool semaphores)
- Stuck handles: 0x5C, 0x5E, 0x60, 0x62, ... (each AssetGarbageCollectorHelper creates 2 semaphores)
- Pattern: each worker creates a "ready" sema (signaled immediately) and a "work" sema (never signaled)
- Conclusion: Workers are idle because main thread never dispatches GC work to them
- This is NORMAL — workers are SUPPOSED to wait for work. NOT a deadlock.

=== EXP-026: First Missing Signal ===
- First stuck semaphore: 0x5C
- Lifecycle: created → waited → never signaled
- Caller: thread 0x00007F4F50F1F950 (AssetGarbageCollectorHelper)
- Entry: 0x800BB06A0 (inside eboot.bin — Unity's thread wrapper)
- Conclusion: Workers are at expected "wait for work" state. Main thread is the bottleneck.

=== EXP-028: Asset Resolution ===
- Yatzi opens: RuntimeInitializeOnLoads.json, ScriptingAssemblies.json, globalgamemanagers, .assets, .resS
- Yatzi FAILS to open: level0, sharedassets0.assets (not in upload)
- Yatzi NEVER TRIES to open: global-metadata.dat (IL2CPP runtime never reaches that phase)
- Seeker opens ALL files successfully (level0 now present)
- Conclusion: For Yatzi, missing level0/sharedassets0 is the blocker. For Seeker, all assets present.

=== EXP-029: IL2CPP Runtime Phase ===
- Il2cppUserAssemblies.prx loads successfully (592 symbols, 295 imports)
- Module init runs (dt_init at 0x804CD5010)
- NO "Fake runtime heap" message — SharpEmu's IL2CPP fake stubs never used
- NO il2cpp_api_lookup_symbol calls
- Game's REAL IL2CPP runtime runs as native code inside Il2cppUserAssemblies.prx
- SharpEmu doesn't instrument this real IL2CPP runtime
- Conclusion: IL2CPP runtime phase is invisible to SharpEmu's logging

=== EXP-030: Export Resolution Audit ===
- Il2cppUserAssemblies.prx has 592 exports (real C++ game functions)
- eboot does NOT directly call into Il2cppUserAssemblies via import stubs
- All AssetGarbageCollectorHelper threads enter at 0x800BB06A0 (inside eboot.bin)
- This is Unity's standard thread wrapper that eventually calls into Il2cppUserAssemblies
- Conclusion: Module loading and dispatch works correctly

=== EXP-031: Scheduler Verification ===
- READY always 0 (in all 20 samples)
- RUNNING: 1 or 2
- BLOCKED: monotonically increases 0 → 9 (workers parking)
- Conclusion: ✅ Scheduler is NOT the issue. Kyty-style pump would NOT help.

=== Seeker with level0/level10 ===
- ALL file opens succeed (no _open fail events)
- Game still produces Unity splash frame (RGB 224,88,64, 99.98% coverage)
- Draw calls: 0 (SharpEmu's GPU/AGC is stub-only)
- Conclusion: For Seeker, the bottleneck is SharpEmu's GPU emulation (no real rendering)

=== FINAL CONCLUSIONS ===
1. SharpEmu's kernel/scheduler/semaphore layer works correctly (signals happen)
2. SharpEmu's filesystem works correctly (all asset files open)
3. SharpEmu's module loading works correctly (PRX loaded, init runs)
4. SharpEmu's IL2CPP fake stubs are NEVER USED by these games (they have real IL2CPP runtime)
5. SharpEmu's GPU/AGC is stub-only (draws=0 always) → can't render scenes
6. Yatzi specifically: missing level0 and sharedassets0.assets (user didn't upload these for Yatzi)
7. Seeker: ALL files present, but SharpEmu can't render the scene content

=== RECOMMENDED NEXT STEP (single item) ===
The fundamental blocker for getting past Unity splash is SharpEmu's GPU/AGC emulation.
Currently draws=0 always — SharpEmu submits no draw calls to the (stub) GPU.
To get real game content rendering, SharpEmu needs real AGC (PS5 GPU) command buffer
parsing and execution, OR at minimum, hook the game's rendering calls to detect when
a scene would be drawn and emit a placeholder.

Alternative (smaller scope): Implement real IL2CPP metadata parsing so the game's own
IL2CPP runtime can build a proper class registry. This would let the game execute more
of its own logic. But without GPU, scenes still can't render.
