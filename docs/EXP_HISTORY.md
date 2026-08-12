# EXP History — SharpEmuT24 / Yatzi (PPSA17697)

**Last updated:** EXP-200 (2026-08-13)
**Total experiments:** EXP-026 through EXP-199 (145+ report files)

---

## Initialization Lifecycle (Confirmed Working)

```
ELF loading (eboot.bin at 0x800000000)
  ↓
PRX mapping (8 modules: libc, libSceNpCppWebApi, Il2cppUserAssemblies, etc.)
  ↓
RELA relocation (400,000+ R_X86_64_RELATIVE applied)
  ↓
Import resolution (3652 stubs, 2516 LLE redirects, 91007 runtime symbols)
  ↓
TLS initialization (per-module TLS templates)
  ↓
DT_INIT execution (two-table walker at vaddr 0x10 in each PRX)
  ↓
IL2CPP bootstrap:
  cJ2Y4E-t258 (il2cpp_api_register_symbols) → builds BST at [0x808B53708]
  r8mvOaWdi28 (resolver) → walks BST, populates API table at 0x801ED6320
  ↓
Game engine entry (EXECUTE_ONCE callback at 0x8007DEE60)
  ↓
Worker thread startup (13 AssetGarbageCollectorHelper threads)
  ↓
IL2CPP GC thread startup (entry 0x804F88AA0 in PRX)
  ↓
GC stop-the-world (sceKernelRaiseException) ← CURRENT BLOCKER
  ↓
GPU initialization (NOT YET REACHED)
  ↓
First frame (NOT YET REACHED)
```

---

## Confirmed Discoveries (Chronological)

### EXP-026..EXP-035: IL2CPP Resolver & Hash Table
- IL2CPP metadata hash-table resolver uses a **Red-Black Tree** (inverted BST)
- Node struct: `[0x00]=right, [0x08]=parent, [0x10]=left, [0x18]=color, [0x19]=matched, [0x20]=symbol_name_ptr, [0x28]=function_ptr`
- `strcmp` works correctly (native intrinsic applied to PRX PLT)
- Native resolver was returning 0 for all 232 calls — root cause unknown at the time

### EXP-036..EXP-078: Unity Bring-Up Arc
- argc=1 blocks `[0x801E518C8]` initialization; `SHARPEMU_GUEST_ARGS="dummy_arg"` fixes it (argc=2)
- real_init has 164 call instructions; call #7 is indirect callback into eboot.bin
- Registration chain runs to completion: `real_init → 0x804F527C0 → 0x804FA20E0 → 0x804F889D0 → 0x804FC33B0`

### EXP-079..EXP-117: Import Resolution & Dispatch
- 24 C++ operator new/delete HLE handlers implemented (EXP-179)
- WaitSema(0x81) deadlock broken by operator new/delete HLE
- `__stack_chk_guard` GLOB_DAT resolution fix (EXP-181)
- Import dispatch gateway manages all HLE calls through trampolines

### EXP-118..EXP-178: Module Loading & Initialization
- Game directory structure verified (sce_module/, Media/Modules/, Media/Plugins/, Media/Metadata/)
- `SHARPEMU_SEMA_FAST_PATH=0` required for correct semaphore behavior
- Bootstrap bridge (NID `Qhv5ARAoOEc`) dispatches dlsym calls
- KernelDynlibDlsym (NID `LwG8g3niqwA`) resolves dynamic symbols

### EXP-179: C++ Operator New/Delete HLE
- Implemented 24 operator new/delete variants
- **Broke WaitSema(0x81) deadlock** — game progressed to VideoOut/Vulkan init
- Permanent fix in `KernelMemoryCompatExports.cs`

### EXP-181: __stack_chk_guard Resolution
- Fixed GLOB_DAT relocation for `__stack_chk_guard` at `0x801D1A558`
- Permanent fix in `SelfLoader.cs`

### EXP-182..EXP-186: Path B & IL2CPP API Chain
- Path B confirmed: consumer takes success path, skips init writer at +0x3969
- `[0x801E51240]` = Il2CppClass* (LATER REVISED in EXP-194)
- IL2CPP API chain (il2cpp_domain_get, il2cpp_class_from_name) NEVER called before crash

### EXP-187..EXP-190: DT_SCE_INIT_ARRAY Investigation
- **REJECTED**: `0x61000017` is `DT_SCE_EXPORT_LIB_ATTR`, NOT init_array
- Prosper comparison confirmed: standard `DT_INIT`/`DT_INIT_ARRAY` only
- RELA relocations populate DT_INIT function pointer tables

### EXP-191: DT_INIT Validation
- 400,000+ R_X86_64_RELATIVE relocations applied successfully
- Table 2 at `0x8089247D8` has 29 function pointers
- DT_INIT calls callbacks from Table 2

### EXP-192: DT_INIT Abort (WRONG ROOT CAUSE)
- **REJECTED**: Abort was caused by INT3 instrumentation interference, NOT missing `__cxa_throw`
- INT3 single-step re-patch mechanism corrupts execution state

### EXP-193: C++ Exception ABI Implementation
- Implemented 15 C++ exception ABI functions in `CxxAbiExports.cs`
- DT_INIT completes without abort (all 4 modules return 0)
- `__cxa_throw` NOT called during normal init — exception ABI is NOT the blocker

### EXP-194: IL2CPP Registration Chain Mapping
- `Il2CppCodegenRegistration` @ `0x804D9C620` (3 LEAs + JMP, 22 bytes)
- `MetadataCache::Register` @ `0x804F23280` (stores 3 args to BSS globals)
- Registration call site @ `0x804F04C5C` inside `Runtime::Init` @ `0x804F04BA0`
- CodeRegistration @ `0x8086E9010` (v29.1, 17 fields, valid)
- MetadataRegistration @ `0x80885C598` (v29, 16 fields, valid)
- `[0x801E51240]` is NOT Il2CppClass* — it's a lazy cache for return of `0x4BD620`

### EXP-195: Wrong Root Cause (il2cpp_init stub)
- **REJECTED**: `il2cpp_init` stub at `DecideIl2CppReturnValue` line 2411 is NEVER REACHED
- EBOOT does NOT use dlsym for IL2CPP — it uses the API table at `0x801ED6320`
- Zero `IL2CPP_NULL`/`IL2CPP_STUB`/`RESOLVER-TRACE` log entries

### EXP-197: Corrected Root Cause
- EBOOT calls `cJ2Y4E-t258` at `0x8013FB24F` → PLT `0x19374C0` → GOT `0x801D1ACD8`
- EBOOT calls `r8mvOaWdi28` at `0x8013FB25B` → PLT `0x19374D0` → GOT `0x801D1ACE0`
- API table population: 64+ slots at `0x13FB254` via resolver calls
- `r8mvOaWdi28` IS direct-bridged to `0x804ED9B90` (PRX resolver)
- `cJ2Y4E-t258` was NOT direct-bridged (dispatched to HLE stub returning 0)

### EXP-198: ROOT CAUSE PROVEN AND FIXED
- **ROOT CAUSE**: `cJ2Y4E-t258` HLE stub at `GameCompatExports.cs:37-38` returned 0 without running PRX function
- HLE stub in HLE table → `TryResolveDirectImportTarget` returns false → Trampoline (dispatch)
- Dispatch calls HLE stub → `ctx.SetReturn(0)` → BST never built → API table all NULL → crash
- **FIX**: Comment out `[SysAbiExport]` for `cJ2Y4E-t258` → falls through to runtime symbol → direct-bridge to `0x804ED3AE0`
- **RUNTIME VALIDATED**: BST populated, API table populated, old crash eliminated, game runs 30s without crashing
- `1D0H2KNjshE`/`hsi9drzHR2k` stubs also commented out (Harvest Days-specific, corrupt Yatzi state)

### EXP-199: Post-IL2CPP Investigation
- Game reaches: IL2CPP init → EXECUTE_ONCE → worker threads → IL2CPP GC thread
- **BLOCKER**: IL2CPP GC stop-the-world deadlocks
  - `sceKernelRaiseException` doesn't actually interrupt target threads
  - All 14 threads block on `sceKernelWaitSema`
  - GC thread blocks on semaphore 0x83 (waiting for acknowledgments)
  - Worker threads block on their own semaphores (waiting for GC to complete)
  - Prosper warns: "A stubbed RaiseException left every thread un-acked -> deadlock"
- No GPU activity (all pipeline counters = 0)

---

## Rejected Hypotheses (DO NOT REINVESTIGATE)

| Hypothesis | Rejected By | Evidence |
|-----------|-------------|----------|
| RELA relocations not applied | EXP-191 | 400,000+ applied successfully |
| DT_INIT tables empty | EXP-191 | Table 2 has 29 valid function pointers |
| DT_INIT doesn't call callbacks | EXP-191 | INT3 at call rax was HIT |
| `DT_SCE_INIT_ARRAY` (0x61000017) is init_array | EXP-190 | Tag is `DT_SCE_EXPORT_LIB_ATTR` |
| `__cxa_throw` root cause | EXP-193 | DT_INIT completes without exceptions |
| INT3 abort root cause | EXP-193 | INT3 instrumentation interference, not real exception |
| `il2cpp_init` stub root cause | EXP-197 | Stub NEVER REACHED (0 log entries) |
| `[0x801E51240]` is Il2CppClass* | EXP-194 | It's a lazy cache for return of `0x4BD620` |
| `0x804FC2470` is registration initializer | EXP-194 | It's a timer calibration function |
| `0x804FC1EA0` is registration initializer | EXP-194 | It's a `__cxa_atexit` call |
| Prosper PT_DYNAMIC mis-based offset applies to Yatzi | EXP-194 | All Yatzi modules have sane p_offset |
| Initializer ordering problem | EXP-191 | DT_INIT two-table walker works correctly |
| TLS initialization problem | EXP-191 | TLS handler set up, 0 TLS loads patched |
| Missing IL2CPP exports as primary cause | EXP-198 | cJ2Y4E-t258 direct-bridge is the fix |
| argc as final root cause | EXP-079+ | argc=2 fix (`SHARPEMU_GUEST_ARGS`) resolved early blocker |

---

## Key Addresses Reference

### PRX (Il2cppUserAssemblies.prx, base `0x804CD5000`)

| Address | Purpose |
|---------|---------|
| `0x804CD5010` | DT_INIT function (two-table walker) |
| `0x804D9C620` | `Il2CppCodegenRegistration` (3 LEAs + JMP) |
| `0x804ED3AE0` | `il2cpp_api_register_symbols` (cJ2Y4E-t258, builds BST) |
| `0x804ED9B90` | IL2CPP API resolver (r8mvOaWdi28, walks BST) |
| `0x804F04BA0` | `Runtime::Init` (contains registration call) |
| `0x804F04C5C` | Registration call site (`call [rax]`) |
| `0x804F23280` | `MetadataCache::Register` (stores 3 args to globals) |
| `0x804F88AA0` | IL2CPP GC thread entry |
| `0x8086E9010` | CodeRegistration struct (v29.1, 17 fields) |
| `0x80885C598` | MetadataRegistration struct (v29, 16 fields) |
| `0x8089247D8` | Table 2 end (first entry = `0x804FC2470`) |
| `0x808B53708` | BST root pointer (populated by cJ2Y4E-t258) |
| `0x808B542E8` | `s_Il2CppCodeRegistration` (BSS, NULL until Register runs) |
| `0x808B542F0` | `s_Il2CppMetadataRegistration` (BSS) |
| `0x808B542F8` | `s_Il2CodegenOptions` (BSS) |

### EBOOT (base `0x800000000`)

| Address | Purpose |
|---------|---------|
| `0x8013FB24F` | `call cJ2Y4E-t258` (il2cpp_api_register_symbols) |
| `0x8013FB254` | Start of API table population (64+ resolver calls) |
| `0x8013FB25B` | `call r8mvOaWdi28` (resolver, 232 callers) |
| `0x8017DEE60` | EXECUTE_ONCE callback (Unity init) |
| `0x801D1ACD8` | GOT slot for cJ2Y4E-t258 |
| `0x801D1ACE0` | GOT slot for r8mvOaWdi28 |
| `0x801E51240` | Lazy cache for return of `0x4BD620` (NOT Il2CppClass*) |
| `0x801ED6320` | IL2CPP API table (64+ slots, populated by resolver) |

### Critical NIDs

| NID | Symbol | Resolution | Status |
|-----|--------|-----------|--------|
| `cJ2Y4E-t258` | il2cpp_api_register_symbols | Direct bridge to `0x804ED3AE0` | ✅ FIXED (EXP-198) |
| `r8mvOaWdi28` | IL2CPP API resolver | Direct bridge to `0x804ED9B90` | ✅ Working |
| `il03nluKfMk` | sceKernelRaiseException | HLE stub (TryRaiseGuestException) | ❌ BLOCKER (EXP-199) |
| `tsvEmnenz48` | __cxa_atexit | HLE stub (no-op, returns 0) | ✅ Working |
| `1D0H2KNjshE` | (Harvest Days-specific) | NOT HLE'd (commented out) | ✅ Fixed (EXP-198) |
| `hsi9drzHR2k` | (Harvest Days-specific) | NOT HLE'd (commented out) | ✅ Fixed (EXP-198) |

---

## Build Environment

| Component | Value |
|-----------|-------|
| .NET SDK | 10.0.x (installed via dotnet-install.sh) |
| Target Framework | net10.0 |
| NuGet packages | Local `.packages/` cache (packages don't support net10.0 via nuget.org) |
| Source tree (with fix) | `sharpemuT24_backup/` (has cJ2Y4E-t258 commented out) |
| Pre-built binary (old, no fix) | `sharpemu-build/SharpEmu.bin` |
| Build command | `dotnet build src/SharpEmu.CLI/SharpEmu.CLI.csproj -c Release --source .packages --runtime linux-x64` |

### Build Notes
- `ps5_names.txt` must be in `scripts/` directory
- `LICENSE.txt` must be in repo root
- `createdump` must be copied from .NET SDK to packages cache
- `_Exp027*`/`_Exp028*` tracer files may need removal (compilation errors with `TryWriteByte`)
