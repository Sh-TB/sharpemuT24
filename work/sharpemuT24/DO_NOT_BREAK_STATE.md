# DO NOT BREAK STATE (Permanent — Never Delete)

## Never Remove These Components

The following fixes are **critical** for game boot. Removing ANY of them will cause regressions:

### 1. Crash Recovery Pipeline
- `TryRecoverNullExecuteFault` in `DirectExecutionBackend.Exceptions.cs`
- `TryRecoverUnmappedMemoryRead` in `DirectExecutionBackend.Exceptions.cs`
- Recovery limit: 100000 (do NOT reduce below 4096)

### 2. IL2CPP Fake Heap
- `GetIl2CppStubForFunction` in `DirectExecutionBackend.Imports.cs`
- `InitIl2CppHeap` with 64KB heap + default vtable + fake objects
- `DecideIl2CppReturnValue` — returns proper non-NULL pointers per function
- `_dumpVideoOut` forced to `true` for frame capture

### 3. PR #542 Compatibility Fixes
- `MessengerCompatExports.cs` — time, cosf, puts, _Getptolower, _Getptoupper
- `_Execute_once` (DiGVep5yB5w) in `CxxAbiExports.cs`
- `__cxa_decrement_exception_refcount` (MQFPAqQPt1s) in `CxxAbiExports.cs`
- IL2CPP dispatch fix: return `resolvedAddress` not `0`
- `EnsureCtypeLowerTable` / `EnsureCtypeUpperTable` in `LibcStdioExports.cs`

### 4. C11 Sync Exports
- `C11SyncExports.cs` — _Mtx_init, _Mtx_lock, _Mtx_unlock, _Cnd_init, srand

### 5. Game-Specific Stubs
- `GameCompatExports.cs` — zlqfTyrQSPk, dZGYu5wObJs, 35NoyMOtYpE, M4YYbSFfJ8g, etc.
- Arise NIDs: McaImWKXong, bRujIheWlB0, Cj+Fw5q1tUo

### 6. AGC Auto-Init
- `sceAgcDriverRegisterOwner` auto-initializes without prior `InitResourceRegistration`

### 7. Sema Fast Path
- `SHARPEMU_SEMA_FAST_PATH=1` env var bypasses semaphore waits for Unity games

### 8. Environment Variables (Required for All Games)
- `SHARPEMU_APP0_DIR` — resolves `/app0/` paths to host filesystem
- `SHARPEMU_SEMA_FAST_PATH=1` — bypass semaphore waits
- `DISPLAY=:99` — Xvfb display (NOT :1, which has stale socket issues)
- `VK_ICD_FILENAMES` — Lavapipe software Vulkan
- Save data at: `work/sharpemu-build/user/savedata/268435456/{game}/SaveData/`

## Before Every Experiment

```bash
git tag backup/pre-test-$(date +%Y%m%d-%H%M)
```

## After Success

```bash
git tag milestone/{description}
git add -A
git commit -m "feat: {description}"
```

## Golden Rule

**Never go below `v0.0.2` / `backup/bringup-state-current`.**

If an experiment breaks Dreaming Sarah or Arise first frame:
1. `git checkout backup/bringup-state-current`
2. Delete the experiment branch
3. Try a different approach
