# SharpEmuT24 — Boot Diagnostic Pipeline

**Purpose:** A staged diagnostic pipeline that systematically verifies each
layer of the emulator boot process, from environment setup to first frame
render. Each stage produces a PASS/FAIL/BLOCKED/UNKNOWN verdict with
evidence and suggested next actions.

## Pipeline Stages

```
Stage 0: Environment
    ↓
Stage 1: PRX/ELF Load
    ↓
Stage 2: Memory Mapping
    ↓
Stage 3: Module Loading
    ↓
Stage 4: Import Resolution
    ↓
Stage 5: HLE Binding
    ↓
Stage 6: IL2CPP Bootstrap
    ↓
Stage 7: Runtime Initialization
    ↓
Stage 8: GPU Initialization
    ↓
Stage 9: First Frame
```

---

## Stage 0 — Environment

**Goal:** Verify host environment is suitable for SharpEmu.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| OS architecture | `uname -m` | `x86_64` |
| Linux kernel version | `uname -r` | ≥ 5.0 |
| CPU features | `/proc/cpuinfo` | SSE4.2, AVX2 (optional) |
| Memory available | `free -h` | ≥ 4 GB free |
| Dotnet runtime | `dotnet --version` | ≥ 8.0 |
| Game files present | `ls /tmp/games/yatzi/` | eboot.bin + Il2cppUserAssemblies.prx |

**FAIL action:** Install missing dependencies or use different host.

**Status for Yatzi (PPSA02929):** ✅ PASS (verified 2026-07-29)

---

## Stage 1 — PRX/ELF Load

**Goal:** Verify eboot.bin and all PRX modules load as valid ELF files.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| eboot.bin magic | Read first 4 bytes | `0x7F454C46` (ELF) |
| eboot.bin decrypted | Check PT_LOAD segments | No encrypted segments |
| Il2cppUserAssemblies.prx loads | BootDependencyAnalyzer | `Loadable: YES` |
| libc.prx loads | BootDependencyAnalyzer | `Loadable: YES` |
| All critical files present | BootDependencyAnalyzer | `Critical miss: 0` |

**Evidence:** Boot Dependency Report (printed at startup)

**FAIL action:** Check file integrity, decryption status, or path.

**Status for Yatzi:** ✅ PASS (eboot 32MB, prx 75MB, all critical files present)

---

## Stage 2 — Memory Mapping

**Goal:** Verify guest virtual address space is correctly mapped.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| eboot base address | Log: `[LOADER] eboot base = 0x...` | `0x800000000` |
| PRX base address | Log: `[LOADER] prx base = 0x...` | `0x804CD5000` |
| eboot segments mapped | Check PT_LOAD segments | All R/W/X segments mapped |
| PRX segments mapped | Check PT_LOAD segments | All segments mapped |
| Stack allocated | Log: `[LOADER] stack at 0x...` | Non-null |
| TLS allocated | Log: `[LOADER] TLS at 0x...` | Non-null |

**Evidence:** Loader logs at startup

**FAIL action:** Check VirtualMemory allocation, page protection settings.

**Status for Yatzi:** ✅ PASS (eboot @ 0x800000000, prx @ 0x804CD5000)

---

## Stage 3 — Module Loading

**Goal:** Verify all required modules are loaded and initialized.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| eboot DT_INIT runs | Log: `[LOADER] eboot DT_INIT` | No crash |
| libc.prx DT_INIT runs | Log: `[LOADER] libc DT_INIT` | No crash |
| Il2cppUserAssemblies.prx DT_INIT runs | Log: `[LOADER] prx DT_INIT` | No crash |
| Module handles returned | sceKernelLoadStartModule return | Non-zero handle |

**Evidence:** Module load logs

**FAIL action:** Check DT_INIT handlers, missing imports.

**Status for Yatzi:** ✅ PASS (all modules load and DT_INIT runs)

---

## Stage 4 — Import Resolution

**Goal:** Verify all imports are resolved (either HLE or direct-bridged).

| Check | Method | PASS criteria |
|-------|--------|---------------|
| Total imports | Log: `Setup N/M import stubs` | M > 0 |
| Unresolved imports | Log: `Import#X unresolved` | Count = 0 (or only low-priority) |
| HLE stubs created | Log: `HLE stub for NID ...` | All kernel/libc NIDs |
| Direct bridges | Log: `Direct bridge for NID ...` | libc exports direct-bridged |
| Critical NIDs resolved | Check: r8mvOaWdi28, cJ2Y4E-t258 | Both resolved |

**Evidence:** Import resolution logs

**FAIL action:** Check HLE export table, NID database (Aerolib).

**Status for Yatzi:** ✅ PASS (all imports resolved, r8mvOaWdi28 direct-bridged to 0x804ED9B90)

---

## Stage 5 — HLE Binding

**Goal:** Verify HLE functions are correctly bound to guest imports.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| HLE assemblies warmed | Log: `Warmed N type initializers` | N > 0 |
| JIT-compiled methods | Log: `JIT-compiled M methods` | M > 0 |
| HLE dispatch works | First import call returns | No crash |
| Native intrinsics applied | Log: `Native intrinsic for NID ...` | strcmp, memcpy, etc. |

**Evidence:** HLE warmup logs, first import dispatch

**FAIL action:** Check HLE attribute discovery, JIT compiler.

**Status for Yatzi:** ✅ PASS (3632 type initializers warmed, 21590 methods JIT-compiled)

---

## Stage 6 — IL2CPP Bootstrap

**Goal:** Verify IL2CPP runtime initializes correctly.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| register_symbols executes | Log: `[RESOLVER-TRACE] PRE-WRAPPER` | Reached |
| BST tree created | BST-WALK log | 239 nodes (Yatzi) |
| All symbols present | BST-WALK SYMBOL SEARCH | All expected symbols FOUND |
| BST invariant holds | Python verification | 0 violations (inverted BST) |
| Resolver executes | RESOLVER-TRACE Entry/Exit | 232 calls (Yatzi) |
| Resolver returns non-zero | RESOLVER-TRACE Exit RAX | Non-zero for known symbols |

**Evidence:** BST-WALK log, RESOLVER-TRACE log

**FAIL action:** Check register_symbols, BST insertion, resolver algorithm.

**Status for Yatzi:**
- ✅ register_symbols executes (239 nodes created)
- ✅ All symbols present
- ✅ BST invariant holds (0 violations, inverted red-black tree)
- ✅ Resolver executes (232 calls)
- ❌ **Resolver returns 0 for all 232 calls** ← BUG IS HERE

**Diagnostic:** EXP-026 + EXP-027 confirm the bug is in SharpEmu's native
CPU execution of the resolver, not in the algorithm or tree.

---

## Stage 7 — Runtime Initialization

**Goal:** Verify Unity runtime initializes after IL2CPP bootstrap.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| GOT populated | Read 125 global variables | >0 non-zero |
| IL2CPP API calls succeed | Wrapper log | No NULL function calls |
| Domain created | Log: `il2cpp_init` return | Non-zero domain |
| Thread attached | Log: `il2cpp_thread_attach` | Non-zero thread |
| Class metadata loaded | Log: `il2cpp_class_from_name` | Non-zero class |

**Evidence:** Wrapper function logs, GOT dump

**FAIL action:** Check GOT population (Stage 6), check IL2CPP API stubs.

**Status for Yatzi:** ❌ BLOCKED (GOT empty because resolver returns 0)

---

## Stage 8 — GPU Initialization

**Goal:** Verify GPU/video output initializes.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| VideoOut open | Log: `videoOutOpen` | Non-zero handle |
| Flip rate set | Log: `videoOutSetFlipRate` | Returns OK |
| Buffers allocated | Log: `videoOutRegisterBuffers` | Non-zero buffer IDs |
| Render context created | Log: `create render context` | Non-zero |
| First submit | Log: `submit command buffer` | Returns OK |

**Evidence:** VideoOut logs, GPU logs

**FAIL action:** Check Vulkan backend, GPU driver.

**Status for Yatzi:** ❌ BLOCKED (Stage 7 not passed)

---

## Stage 9 — First Frame

**Goal:** Verify first frame is rendered and presented.

| Check | Method | PASS criteria |
|-------|--------|---------------|
| First flip | Log: `videoOutSubmitFlip` | Returns OK |
| Frame presented | Log: `frame N presented` | N ≥ 0 |
| No crashes | Process still running | No SIGSEGV/SIGABRT |
| Render time | PerfOverlay | < 100ms per frame |

**Evidence:** Render logs, performance overlay

**FAIL action:** Check GPU state, shader compilation, framebuffer.

**Status for Yatzi:** ❌ BLOCKED (Stage 8 not passed)

---

## Pipeline Summary

| Stage | Status | Blocker |
|-------|--------|---------|
| 0. Environment | ✅ PASS | — |
| 1. PRX/ELF Load | ✅ PASS | — |
| 2. Memory Mapping | ✅ PASS | — |
| 3. Module Loading | ✅ PASS | — |
| 4. Import Resolution | ✅ PASS | — |
| 5. HLE Binding | ✅ PASS | — |
| 6. IL2CPP Bootstrap | ⚠️ PARTIAL | Resolver returns 0 for all calls |
| 7. Runtime Init | ❌ BLOCKED | GOT empty (Stage 6) |
| 8. GPU Init | ❌ BLOCKED | Stage 7 |
| 9. First Frame | ❌ BLOCKED | Stage 8 |

## Current Focus

**Stage 6 is the blocker.** The resolver at 0x804ED9B90 returns 0 for all
232 calls, preventing GOT population and blocking all subsequent stages.

EXP-026 confirmed the algorithm is correct (synthetic CPU finds all 239
symbols). EXP-027 will pinpoint the exact native CPU emulation bug.

Once Stage 6 passes (resolver returns non-zero for all 232 calls), the
remaining stages should cascade automatically.

## How to Use This Pipeline

1. Run SharpEmu with `--diagnostic` flag (if available) or check logs
2. For each stage, verify the checks listed above
3. The FIRST stage that fails is the current blocker
4. Use the "FAIL action" suggestion to guide debugging
5. Once a stage passes, move to the next

## Regression Test

After fixing the resolver bug (Stage 6), re-run the pipeline to verify:

1. Stage 6 passes: resolver returns non-zero for all 232 calls
2. Stage 7 passes: GOT populated (>0 non-zero globals)
3. Stage 8 passes: GPU initializes
4. Stage 9 passes: first frame rendered

If any subsequent stage fails, the pipeline will identify the new blocker.
