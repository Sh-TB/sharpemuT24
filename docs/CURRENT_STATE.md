# CURRENT STATE — SharpEmuT24 / Yatzi (PPSA17697)

**Last updated:** EXP-200 (2026-08-13)
**Single entry point for future AI agents and developers**

---

## Where Are We Now?

SharpEmuT24 successfully reaches **post-IL2CPP execution**. The game's IL2CPP runtime initializes correctly, worker threads start, and the Unity engine begins its initialization sequence. The remaining blocker is **async exception delivery during GC stop-the-world**.

### Lifecycle Status

```
ELF loaded              ✅ PASS
PRX mapped              ✅ PASS
RELA applied            ✅ PASS
Imports resolved        ✅ PASS
BST populated           ✅ PASS (232+ IL2CPP functions)
IL2CPP initialized      ✅ PASS (cJ2Y4E-t258 direct-bridged, API table populated)
Game engine entered     ⚠️ PARTIAL (EXECUTE_ONCE ran, worker threads started)
GPU initialized         ❌ NOT REACHED (all counters = 0)
First frame attempted   ❌ NOT REACHED
```

### Current Blocker

**IL2CPP GC semaphore deadlock.** The IL2CPP Garbage Collector thread tries to stop worker threads via `sceKernelRaiseException` (GC stop-the-world), but the exception delivery mechanism doesn't actually interrupt the target threads. Without acknowledgment, the GC thread blocks forever on semaphore `0x83`. Worker threads also block waiting for the GC to complete. Classic deadlock → stall watchdog triggers after 20s.

---

## What Is Already Solved?

### EXP-198 Fix (CRITICAL — MUST PRESERVE)

The `cJ2Y4E-t258` (il2cpp_api_register_symbols) HLE stub in `GameCompatExports.cs` was intercepting EBOOT's call and returning 0 without running the PRX's function. This prevented the BST from being built.

**Fix**: Comment out the `[SysAbiExport]` attribute for `cJ2Y4E-t258` so it falls through to runtime symbol resolution → direct-bridge to `0x804ED3AE0` (the PRX's actual function).

**Source**: The fix is in the `sharpemuT24_backup/` source tree (already applied). The `sharpemuT24-broken/` source tree has the stub ACTIVE (needs the fix applied).

**Runtime validated**: BST populated, API table populated, old crash at `0x80080684D` eliminated, game runs 30s without crashing.

### Other Permanent Fixes

| Fix | EXP | File | Description |
|-----|-----|------|-------------|
| C++ operator new/delete HLE | EXP-179 | `KernelMemoryCompatExports.cs` | 24 operator variants, broke WaitSema(0x81) deadlock |
| `__stack_chk_guard` GLOB_DAT | EXP-181 | `SelfLoader.cs` | Fixed stack canary resolution |
| C++ exception ABI | EXP-193 | `CxxAbiExports.cs` | 15 functions (not currently needed but valuable for future) |
| `cJ2Y4E-t258` direct-bridge | EXP-198 | `GameCompatExports.cs` | Commented out HLE stub, enabled PRX function |
| `1D0H2KNjshE`/`hsi9drzHR2k` removal | EXP-198 | `GameCompatExports.cs` | Harvest Days-specific stubs removed |

### Runtime Configuration

```bash
SHARPEMU_GUEST_ARGS="dummy_arg"  # argc=2 (required)
SHARPEMU_SEMA_FAST_PATH=0        # Correct semaphore behavior
SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1  # Headless mode
DISPLAY=:99                      # Xvfb for headless
```

---

## What Must NOT Be Investigated Again?

### Rejected Hypotheses (Permanently Closed)

| Hypothesis | Rejected By | Reason |
|-----------|-------------|--------|
| RELA relocations broken | EXP-191 | 400,000+ applied successfully |
| DT_INIT broken | EXP-191 | Two-table walker works, 29 callbacks called |
| `DT_SCE_INIT_ARRAY` (0x61000017) is init_array | EXP-190 | Tag is `DT_SCE_EXPORT_LIB_ATTR` |
| `__cxa_throw` root cause | EXP-193 | DT_INIT completes without exceptions |
| INT3 abort root cause | EXP-192 | INT3 instrumentation interference |
| `il2cpp_init` stub root cause | EXP-195/197 | Stub NEVER REACHED (EBOOT uses API table, not dlsym) |
| `[0x801E51240]` is Il2CppClass* | EXP-194 | It's a lazy cache for return of `0x4BD620` |
| Initializer ordering problem | EXP-191 | DT_INIT two-table walker works correctly |
| TLS initialization problem | EXP-191 | TLS handler set up correctly |
| Missing IL2CPP exports as primary cause | EXP-198 | cJ2Y4E-t258 direct-bridge is the fix |
| argc as final root cause | EXP-079+ | argc=2 fix resolved early blocker |
| Prosper PT_DYNAMIC mis-based offset | EXP-194 | Yatzi modules have sane p_offset |

---

## What Is the Next Evidence Target?

### Trace `sceKernelRaiseException` Path

The `sceKernelRaiseException` HLE stub is in `KernelExceptionCompatExports.cs` (NID `il03nluKfMk`). It calls `scheduler.TryRaiseGuestException()`. This likely fails to actually interrupt the target thread.

**Evidence to collect:**
1. Does `TryRaiseGuestException` return success or `ORBIS_GEN2_ERROR_BUSY`?
2. Is the target thread actually interrupted?
3. Does the installed exception handler run on the target thread?
4. Does the handler signal the GC acknowledgment semaphore?

### Compare with Prosper Implementation

Prosper's `hle_kernel.cpp:3072-3198` implements `sceKernelRaiseException` with:
- **Linux**: Targeted POSIX signals (SIGUSR1) to interrupt the target thread
- **Windows**: Suspends the target thread, redirects its CONTEXT through a thunk
- Both paths synthesize a FreeBSD amd64 mcontext and run the real guest handler on the target thread

**Key Prosper comment** (`hle_kernel.cpp:3080`):
> "A stubbed RaiseException left every thread un-acked -> deadlock."

This is exactly the symptom we observe.

### Verify Thread Interruption Mechanism

SharpEmu uses direct execution (guest x86_64 code runs natively on the host CPU). To interrupt a guest thread:
1. The host thread must be physically interrupted (via signal on Linux)
2. The signal handler must save the guest's register state
3. The guest's RIP must be redirected to the installed exception handler
4. After the handler returns, the original register state must be restored

If `TryRaiseGuestException` doesn't implement steps 1-4, the GC deadlock is unavoidable.

---

## Build Instructions

```bash
# Install .NET 10 SDK
curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
chmod +x /tmp/dotnet-install.sh
/tmp/dotnet-install.sh --channel 10.0 --install-dir /tmp/dotnet

# Set up environment
export DOTNET_ROOT=/tmp/dotnet
export PATH=/tmp/dotnet:$PATH
export NUGET_PACKAGES=/path/to/.packages

# Build from the FIXED source tree (sharpemuT24_backup)
cd sharpemuT24_backup
dotnet build src/SharpEmu.CLI/SharpEmu.CLI.csproj -c Release \
    --source .packages --runtime linux-x64

# Run Yatzi
cd artifacts/bin/Release/net10.0/linux-x64
mkdir -p SharpEmu/diagnostics
SHARPEMU_GUEST_ARGS="dummy_arg" \
SHARPEMU_SEMA_FAST_PATH=0 \
SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1 \
DISPLAY=:99 \
dotnet SharpEmu.dll /path/to/yatzi/eboot.bin --log-level=info
```

### Build Notes
- `ps5_names.txt` must be in `scripts/` directory
- `LICENSE.txt` must be in repo root
- `createdump` must be copied from .NET SDK to packages cache
- `_Exp027*`/`_Exp028*` tracer files may need removal (compilation errors)
- `.packages` folder is the NuGet source (Avalonia/Silk.NET don't support net10.0 via nuget.org)
