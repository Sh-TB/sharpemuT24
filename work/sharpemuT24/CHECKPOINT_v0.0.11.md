# SharpEmuT24 — Definitive Checkpoint for Next Chat
## Version: v0.0.11 (post 0455370)
## Date: 2026-07-24

---

# 1. Golden Baseline (NON-NEGOTIABLE)

```
Tag: golden-render-baseline (v0.0.9, commit f83b6ea)
Game: Dreaming Sarah (PPSA02929)
Engine: Native C++
Result: ✅ PASS (138 frames, 167+ colors, real game content)
Test: tests/golden/run-golden-tests.sh
```

**Rule: Every change must pass Dreaming Sarah Golden Test before merge.**

---

# 2. What We Proved

## GLFW X11 Fix (PR #457)
- Root cause: PreferX11OnLinuxWayland() required WAYLAND_DISPLAY to request X11
- Fix: Always request X11 when DISPLAY is set
- Result: Vulkan surface created → real framebuffer → actual game image

## Real Game Frames
- Dreaming Sarah produces 138 real framebuffer dumps
- Frame 138 has 167+ distinct colors (real game content, not test pattern)
- Pipeline: Game → AGC → DCB → Vulkan → Swapchain → Framebuffer → Image

## Test Pattern Bug (Fixed)
- GenerateFramePattern() produced HSV color cycle (RGB 229,95,68 for frame 1)
- This was confused with "Unity splash" for days
- Now: FrameAnalyzer classifies frames (splash vs real content)

---

# 3. Game Status Matrix

| # | Game | Engine | Status | Blocker | Next Step |
|---|------|--------|--------|---------|-----------|
| 1 | Dreaming Sarah | Native C++ | ✅ GOLDEN | None | Protect |
| 2 | Yatzi (PPSA17697) | Unity IL2CPP | ❌ IL2CPP bootstrap barrier | SignalSema=0 | NID signature capture + sync trace |
| 3 | Seeker (PPSA12500) | Unity IL2CPP | ❌ Same | Same as Yatzi | After Yatzi |
| 4 | Arise (PPSA06328) | Native C++ | ❌ | SIGILL crash | Crash analyzer |
| 5 | Harvest Days (PPSA14677) | Unity IL2CPP | ❌ | Encrypted PRX | Need fSELF |

---

# 4. Windows Log Comparison (CRITICAL)

User provided upstream Windows log (PPSA17697-20260721-152128.log).

| Metric | Windows (upstream) | Linux (our fork) |
|--------|-------------------|-----------------|
| VkqLPArfFdc | 0 | 0 |
| SignalSema | **0** | **0** |
| CreateSema | 28 | 24 |
| sceAgc calls | 0 | 0 |
| Stall | Yes (20s timeout) | Yes (infinite loop) |
| All threads blocked | Yes (WaitSema) | Yes (WaitSema) |

## IMPORTANT: Conclusion correction

Previously stated: "This is an upstream SharpEmu limitation"

**Corrected**: This is an upstream gap under investigation.

What we KNOW:
- SignalSema = 0 on BOTH platforms
- Not caused by fork-specific stubs (removing them didn't change behavior)
- Not caused by Harvest Days NID additions
- All 14 AssetGarbageCollectorHelper threads + 1 IL2CPP thread deadlock on WaitSema

What we DON'T KNOW yet:
- Whether missing signal path is caused by unimplemented IL2CPP NID
- Whether 1D0H2KNjshE/hsi9drzHR2k (return-zero fallback) should actually
  trigger a signal as part of their real implementation
- Whether deeper SharpEmu Unity bootstrap limitation exists
- Whether signal comes through a different API (scePthreadCondSignal, etc.)

SignalSema = 0 may be a SYMPTOM, not the ROOT CAUSE.
The IL2CPP thread may never reach the signal code because an earlier
NID returned zero instead of doing real work.

---

# 5. IL2CPP Bootstrap Investigation Plan

## Phase 1 — NID Signature Capture (DO THIS FIRST)

For NIDs 1D0H2KNjshE and hsi9drzHR2k, log on every call:
```
NID, Thread ID, RIP, Return Address
RDI, RSI, RDX, RCX, R8, R9
Return Value
```

Then classify the NID by its argument pattern:
- Pattern A (semaphore-like): RDI=handle, RSI=count → missing HLE implementation
- Pattern B (runtime helper): RDI=object, RSI=callback → IL2CPP internal function
- Pattern C (bootstrap): RDI=context, RSI=config → Unity internal bootstrap

## Phase 2 — Caller Module Mapping

Map Return Address to module:
- Inside eboot.bin? → Unity engine code
- Inside Il2cppUserAssemblies.prx? → IL2CPP compiled game code
- Inside libc.prx? → C runtime wrapper

## Phase 3 — Synchronization Trace (Mini Semaphore Tracker)

Lightweight log for ALL sync primitives:
```
CreateSema(handle, name, thread) → record
WaitSema(handle, thread) → record
SignalSema(handle, thread) → record
scePthreadCondSignal(handle, thread) → record
scePthreadMutexUnlock(handle, thread) → record
sceKernelWakeupThread(handle, thread) → record
```

Output:
```
Semaphore 0x31
  Created by: MainThread
  Waiters: Thread#14, Thread#15, ...
  Signals: NONE
  Possible blocker: IL2CPP bootstrap
```

## Phase 4 — Last-20-Guest-Calls Before Stall

Record the last 20 guest function calls before the stall:
```
T0 MainThread → sceKernelCreateSema(0x31)
T1 AssetGC → sceKernelWaitSema(0x31)
T2 IL2CPP Worker → call NID 1D0H2KNjshE
T3 fallback return 0
STALL
```

---

# 6. NID Stubs (Current State after 0455370)

## Kept (verified needed or harmless)

| NID | Name | Justification |
|-----|------|---------------|
| VkqLPArfFdc | IL2CPP bootstrap | 0 calls on Windows, harmless non-NULL return |
| GrQ9s4IrNaQ | sceAudioOutGetPortState | Called by Yatzi |
| MM4IZSEYytQ | sceAgcDriverSetHsOffchipParam | Called by Yatzi |
| XlNp7jzGiPo | sceAgcDriverSetTFRing | Called by Yatzi |
| rVjRvHJ0X6c | sceKernelFindInternalFile | Called by Yatzi |
| BHouLQzh0X0 | sceKernelFindInternalFileVariant | Called by Yatzi |
| 1-LFLmRFxxM | sceKernelMkdir | Called by Yatzi |

## Removed (Harvest Days only)

| NID | Name | Reason |
|-----|------|--------|
| 1D0H2KNjshE | HarvestMemOp1 | 0 calls on Yatzi Windows log (but IS in import table — resolves to return-zero fallback) |
| hsi9drzHR2k | HarvestMemOp2 | Same |
| AcslpN1jHR8 | PadDeviceClassGetExtendedInfo | Harvest Days specific |
| 5TjaJwkLWxE | HarvestStub5Tja | Harvest Days specific |
| 3BytPOQgVKc | HarvestStub3Byt | Harvest Days specific |
| pztV4AF18iI | HarvestStubPztV | Harvest Days specific |
| xk0AcarP3V4 | scePadOpen | Conflicts with real PadExports implementation |

## Stub Policy v2 (NEW RULE)

Before adding any NID stub, verify ALL of:
1. NID exists in game's import table
2. NID is actually called (not just imported)
3. Current fallback (return-zero) causes failure
4. API behavior is known

If upstream doesn't resolve the NID and the game runs the same → do NOT stub.

---

# 7. NID Coverage Gap

```
Old working source (e3bbe69): 1029 unique NIDs
Current source (0455370):     ~920 unique NIDs
Missing:                       ~109 NIDs
```

Missing NIDs are in: SaveData (34), AudioPropagation (39), KernelPthread (15+3),
Font (8), Net (4), Pad (2), Ngs2 (2), Ajm (2), and others.

Porting these requires resolving dependency chain (GuestGpuTypes, GuestBlendConstant, etc.)

---

# 8. Diagnostics Inventory

## Source Files
```
src/SharpEmu.Core/Loader/BootDependencyAnalyzer.cs
src/SharpEmu.Core/Loader/ExecutableFormatDetector.cs
src/SharpEmu.Libs/VideoOut/FrameAnalyzer.cs
src/SharpEmu.CLI/DiagnosticEngine.cs
src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Diagnostics.cs
src/SharpEmu.Libs/Agc/AgcExports.Diagnostics.cs
src/SharpEmu.Diagnostics.Contracts/DiagnosticAdapter.cs
src/SharpEmu.Logging/IDiagnosticSink.cs
```

## Golden Test
```
tests/golden/GOLDEN_BASELINE.md
tests/golden/run-golden-tests.sh
```

## Environment Variables
```
SHARPEMU_LOG_SEMA          — Semaphore trace
SHARPEMU_LOG_OPEN          — File open trace
SHARPEMU_LOG_IL2CPP_NULL   — IL2CPP NULL return trace
SHARPEMU_LOG_IL2CPP_STUBS  — IL2CPP stub trace
SHARPEMU_LOG_GUEST_THREADS — Thread state trace
SHARPEMU_LOG_GUEST_EXCEPTIONS — Exception trace
SHARPEMU_LOG_POSIX_SIGNALS — Signal trace
SHARPEMU_DUMP_VIDEOOUT     — BMP frame dump
SHARPEMU_TRACE_GUEST_IMAGES — Swapchain dump
SHARPEMU_GUEST_IMAGE_DUMP_DIR — Dump directory
SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS — Continuous dump
SHARPEMU_STALL_WATCHDOG_SECONDS — Stall detection
SHARPEMU_DUMP_FAULT_STACK_WINDOW — Crash stack dump
SHARPEMU_WRITABLE_APP0 — Allow writes to /app0/
SHARPEMU_HEADLESS — Use headless presenter (no Vulkan)
SHARPEMU_SEMA_FAST_PATH — Bypass semaphore waits (BREAKS Unity)
```

---

# 9. Environment Setup

```bash
# Xvfb
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset &

# Vulkan (Lavapipe software renderer)
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build

# Display
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg

# Game
export SHARPEMU_APP0_DIR=/tmp/games/dreaming-sarah/PPSA02929-app0
export SHARPEMU_WRITABLE_APP0=1

# Frame capture
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/framebuffers
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1

# Run (NOT headless — must use Vulkan for real frames)
unset SHARPEMU_HEADLESS
./SharpEmu --log-level=info eboot.bin
```

---

# 10. Key Commits

```
f83b6ea  v0.0.9 release (GLFW X11 fix + real frames)
17a0d05  PreferX11OnLinuxWayland fix (PR #457)
3b2d499  VkqLPArfFdc + 3 NID stubs
b451ae9  4 more NID stubs
560301b  PROJECT_STATUS_v0.0.9.md
a9e4186  PROJECT_STATUS_v0.0.10.md (Windows log analysis)
0455370  Remove Harvest Days stubs + fix xk0AcarP3V4 conflict
ed0f945  CHECKPOINT_v0.0.11.md (first version — conclusion corrected below)
```

Tags:
```
golden-render-baseline → v0.0.9 (f83b6ea)
v0.0.9  → f83b6ea
v0.0.10 → 560301b
```

---

# 11. Next Steps (Priority Order)

## P0: Protect Dreaming Sarah
- Run golden test before EVERY change
- If it fails, revert immediately

## P1: IL2CPP Bootstrap Investigation (Yatzi/Seeker)
### Phase 1: NID Signature Capture (FIRST)
- Log all arguments for 1D0H2KNjshE and hsi9drzHR2k calls
- Classify NID by argument pattern (semaphore-like vs runtime helper vs bootstrap)

### Phase 2: Caller Module Mapping
- Map return addresses to modules (eboot, Il2cppUserAssemblies, libc)

### Phase 3: Synchronization Trace
- Track ALL sync primitives (semaphores, condvars, mutexes, thread wakeups)
- Build semaphore lifecycle graph
- Identify which semaphore is blocking and who should signal it

### Phase 4: Last-20-Calls Before Stall
- Record last 20 guest calls before stall point
- Identify the missing step in the IL2CPP bootstrap chain

- Do NOT add more NID stubs until Phase 1-4 are complete
- Do NOT conclude "upstream limitation" until root cause is proven

## P2: Port Missing NIDs from Old Source
- 109 NIDs missing (SaveData, AudioPropagation, etc.)
- Must resolve dependency chain (GuestGpuTypes, etc.)
- Port one module at a time, golden test after each

## P3: Arise SIGILL Investigation
- Get crash address, instruction bytes, register state
- Identify unsupported CPU instruction
- Implement instruction or workaround

## P4: Harvest Days
- Needs decrypted PRX files (fSELF)
- Cannot test until PRX decryption is available

---

# 12. Mistakes Documented (Do Not Repeat)

1. **HSV test pattern confused with game output** — GenerateFramePattern() RGB(229,95,68) = HSV(10°,0.7,0.9)
2. **6 false hypotheses wasted days** — scheduler, semaphore deadlock, metadata corruption, missing files, fake stubs, regression
3. **Real fix was one function** — PreferX11OnLinuxWayland() needed DISPLAY check, not WAYLAND_DISPLAY
4. **Harvest Days stubs polluted Yatzi** — 1D0H2KNjshE/hsi9drzHR2k had 0 calls on Windows log but ARE in Yatzi's import table (resolving to return-zero fallback)
5. **VkqLPArfFdc was a red herring** — 0 calls on Windows; crash reduction was from removing bad stubs, not adding new ones
6. **Multiple systems changed simultaneously** — never change HLE + GPU + VideoOut at the same time
7. **Frame count ≠ game output** — must check distinct color count, not just "frame exists"
8. **DIAG-VERIFY doesn't capture all calls** — Windows log showed 0 for NIDs that ARE called (logging gap)
9. **Premature conclusion about "upstream limitation"** — SignalSema=0 may be a symptom, not root cause. An unimplemented NID returning zero may be preventing the IL2CPP thread from reaching the signal code.

---

# 13. Repository

```
GitHub: https://github.com/Sh-TB/sharpemuT24
Default branch: main
Source path: work/sharpemuT24/src/
Binary: work/sharpemu-build/SharpEmu
```

---

# 14. CRITICAL UPDATE: Semaphore Analysis (commit 881591a)

## Previous conclusion CORRECTED

Previous: "SignalSema = 0 → upstream limitation"
**CORRECTED**: SignalSema = 4009 — signals ARE happening!

## Semaphore Lifecycle Data (from SEMA-LIFE tracker)

| Event | Count |
|-------|-------|
| create | 340 |
| wait | 100 |
| **signal** | **4009** |
| wake | 0 |
| delete | 78 |

## Three distinct semaphore groups found

### Group 1: PAIRED (0x5C-0x75) — WORKING
13 pairs: wait on EVEN handle, signal on ODD handle (handle+1)
```
0x5C waited → 0x5D signaled ✅
0x5E waited → 0x5F signaled ✅
0x60 waited → 0x61 signaled ✅
...
0x74 waited → 0x75 signaled ✅
```
This is Unity's normal "worker wait / completion signal" pattern.

### Group 2: DEADLOCKED (0x81-0x8D) — ALL BLOCKED
13 semaphores waited on, NONE ever signaled
```
0x81 waited → 0x82 also waited (NOT paired, both blocked)
0x82 waited → 0x83 also waited
...
0x8D waited → 0x8E also waited
```
These are the ACTUALLY DEADLOCKED semaphores.
13 different threads are blocked, each waiting on its own semaphore.

### Group 3: MIXED (0x93-0xA2) — PARTIALLY WORKING
These have both waits AND signals, but wait_count > signal_count
```
0x93: 2 waits, 1 signal (1 still blocked)
0x94: 5 waits, 4 signals (1 still blocked)
...
```

## Key Insight

The previous analysis that said "signals go to wrong handle" was PARTIALLY correct:
- Group 1 signals DO go to a different handle than the wait — but this is BY DESIGN (paired semaphores)
- Group 2 semaphores have NO signals at all — these are the real deadlock

## Next Step

The 0x81-0x8D semaphores are created with init=0, max=int.MaxValue.
13 threads each wait on their own semaphore and nobody signals them.
Need to find: WHO is supposed to signal these semaphores?
- Is it a different thread that hasn't been created yet?
- Is it a callback that never fires?
- Is it a NID that returns zero instead of doing work?

---

# 15. CRITICAL UPDATE: Thread-Semaphore Correlation

## All 13 deadlocked semaphores (0x81-0x8D) are waited on by Job.worker 0-12

| Sema | Waiter Thread | Thread Name |
|------|---------------|-------------|
| 0x81 | 0x...BF7DC0 | Job.worker 0 |
| 0x82 | 0x...BFA340 | Job.worker 1 |
| 0x83 | 0x...5648D0 | Job.worker 2 |
| ... | ... | ... |
| 0x8D | 0x...D87160 | Job.worker 12 |

## Interpretation

These 13 semaphores are the Unity C# Job System worker wait semaphores.
Each Job.worker creates its own semaphore and waits on it for work dispatch.

**These workers are NOT deadlocked — they are IDLE.**
They are correctly waiting for the main thread to dispatch C# Job System work.
Nobody is dispatching jobs because the main thread is stuck in bootstrap.

## The REAL bottleneck is the MAIN THREAD

The main thread is stuck somewhere else (not on these semaphores).
The workers are just idle waiting for work that never comes.

## Thread inventory (52 threads total)

| Thread Type | Count | Status |
|-------------|-------|--------|
| AssetGarbageCollectorHelper | 13 | ✅ Working (group 1 paired semaphores) |
| Job.worker 0-12 | 13 | 🟡 Idle (waiting for work, group 2 semaphores) |
| Background Job.worker 0-15 | 16 | 🟡 Partially working (group 3) |
| FMOD threads | 3 | Running |
| Unity engine threads | 7 | Running |

## Next Step

Find what the MAIN THREAD is doing.
The main thread is NOT waiting on any semaphore — it's in a busy loop:
- Calling 1D0H2KNjshE_stub (59 times)
- Calling hsi9drzHR2k_stub (21 times)
- Calling scePthreadMutexLock, sceKernelClockGettime, sceAudioOutOutput

The main thread is stuck in a loop, not in a semaphore wait.
Need to trace what the main thread is actually executing.

---

# 16. NID Argument Analysis (commit 7012c3e)

## Corrected: R8 is NOT a double

Previous analysis incorrectly said R8=0x3FF0000000000000 (1.0 as double) was dominant.
**Corrected**: R8=0x100 (256) is the dominant value (82% of calls).

## 1D0H2KNjshE (60,343 calls in 15s)

| Register | Value | Frequency | Interpretation |
|----------|-------|-----------|----------------|
| RDI | 0x601183C90 | 99.97% | Guest heap object (IL2CPP runtime) |
| R8 | 0x100 (256) | 99.97% | Cache line size or buffer size |
| R9 | 0x40 (64) | 99.97% | Alignment or secondary size |
| RDX | 3-13 | varying | Small indices |
| RCX | 0x17-0x3F | varying | Small indices |

## hsi9drzHR2k (19,968 calls in 15s)

| Register | Value | Frequency | Interpretation |
|----------|-------|-----------|----------------|
| RDI | 0x601183C90 | 82% | Same object as 1D0H2KNjshE |
| R8 | 0x100 (256) | 82% | Same as 1D0H2KNjshE |
| R8 | 1.0-7.0 (double) | 18% | Initialization phase only |
| RCX | 0x10, 0x2D-0x3F | varying | Indices/sizes |

## Interpretation

R8=0x100 (256) and R9=0x40 (64) strongly suggest:
- 256 = PS5 GPU cache line size or buffer allocation size
- 64 = CPU cache line size or alignment

Both NIDs operate on the SAME guest object (0x601183C90).
This is likely an IL2CPP GC heap object or thread-local storage.

The main thread is in a tight polling loop (~4000 calls/second).
Return-zero prevents the loop from exiting.

## Next Step

Need caller mapping (return address → module) to determine:
- Is the caller inside eboot.bin (Unity engine code)?
- Is the caller inside Il2cppUserAssemblies.prx (IL2CPP compiled game code)?
- What is the loop structure (cmp/test after call)?
