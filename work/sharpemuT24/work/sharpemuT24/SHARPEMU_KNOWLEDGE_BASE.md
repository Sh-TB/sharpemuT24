# SharpEmu Knowledge Base (Permanent — Never Delete)

## Problems, Causes, and Solutions

### Problem: Arise crashes at import #2000 with SIGSEGV
- **Cause**: Refcount array access with bad index (rbx=pointer used as index)
- **Fix**: TryRecoverUnmappedMemoryRead — decode instruction, skip it
- **Games**: Arise

### Problem: Unity games crash at RIP=0 (NULL function pointer)
- **Cause**: IL2CPP stubs return NULL for functions that must return non-NULL
- **Fix**: IL2CPP fake heap with vtable + TryRecoverNullExecuteFault
- **Games**: Harvest Days, New Game

### Problem: Arise can't find game data files
- **Cause**: SHARPEMU_APP0_DIR not set — /app0/ paths don't resolve
- **Fix**: Set SHARPEMU_APP0_DIR to the app0 directory
- **Games**: Arise

### Problem: Arise can't find save data
- **Cause**: Save data path changed between builds
- **Fix**: Create save data at /home/z/my-project/work/sharpemu-build/user/savedata/268435456/{game}/SaveData/
- **Games**: Arise

### Problem: X11 display stale socket
- **Cause**: /tmp/.X1-lock from previous session prevents Xvfb startup
- **Fix**: Use display :99 instead of :1
- **Games**: All

### Problem: NuGet SSL certificate errors
- **Cause**: Repository countersignature timestamping cert not trusted
- **Fix**: Download packages to local feed, use local NuGet source
- **Games**: N/A (build issue)

### Problem: .NET workload SDK missing
- **Cause**: SDK installation missing WorkloadAutoImportPropsLocator
- **Fix**: Create dummy SDK files in /home/z/.dotnet/sdk/10.0.302/Sdks/
- **Games**: N/A (build issue)

### Problem: Disk space full (9.9GB)
- **Cause**: Old reports (4.8GB), game ROMs in git, build artifacts
- **Fix**: Remove download/ directory, untrack upload/ from git, clean artifacts
- **Games**: N/A (environment issue)

## Architecture

### Crash Recovery Pipeline
1. TryRecoverGuestInt41 → INT 41 trap recovery
2. TryRecoverAuxiliaryThreadExecuteFault → TBB thread faults
3. TryRecoverNullExecuteFault → NULL function pointer calls
4. TryRecoverUnmappedMemoryRead → Out-of-bounds array access
5. TryHandleLazyCommittedPage → Lazy page commitment
6. TryRecoverGuestAllocatorHole → Allocator empty node

### IL2CPP Fake Heap Layout
```
0x0000-0x0FFF : Default vtable (512 slots → return-zero stub)
0x1000-0x10FF : "xor eax, eax; ret" stub
0x1100-0x17FF : Fake objects (Domain, Thread, Class, Image, Assembly, Object, Type)
0x2000-0xFFFF : Per-function stubs (16 bytes each, up to 3584 stubs)
```

### Key NIDs
| NID | Function | Game |
|-----|----------|------|
| YaHc3GS7y7g | _Mtx_init | All |
| SreZybSRWpU | _Cnd_init | All |
| iS4aWbUonl0 | _Mtx_lock | All |
| gTuXQwP9rrs | _Mtx_unlock | All |
| 9UK1vLZQft4 | scePthreadMutexLock | All |
| McaImWKXong | (Arise stub) | Arise |
| bRujIheWlB0 | (Arise stub) | Arise |
| Cj+Fw5q1tUo | (Arise stub) | Arise |
| DiGVep5yB5w | (Harvest stub) | Harvest Days |
| MQFPAqQPt1s | (Harvest stub) | Harvest Days |
