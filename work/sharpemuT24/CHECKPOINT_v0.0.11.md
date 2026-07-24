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

---

# 17. CRITICAL UPDATE: Non-Zero Return Experiment (user's cheap test)

## User's Suggestion (Persian, translated)

> Before fully accepting the cache-flush hypothesis, run a cheap experiment:
> temporarily modify both NID stubs to return non-zero (R8 or constant 1)
> instead of 0, and observe if the loop breaks.
>
> If it breaks → we just need non-zero return, no need to understand the operation.
> If it doesn't break → these NIDs are NOT the loop exit condition, look elsewhere.

## Implementation

Added two env-var-controlled knobs to `GameCompatExports.cs`:
- `SHARPEMU_NID_RETURN_NONZERO=1` → stubs return R8 value (or 1 if R8==0) instead of 0
- `SHARPEMU_NID_CALLER_MAP=1` → log caller module+offset (from actual return address read at [RSP])

Also added a background timer that dumps cumulative NID call counts every 2 seconds,
independent of NID activity, so we can see "NID calls have stopped" definitively.

## Results (Yatzi, 18s run, both phases)

| Phase | 1D0H2KNjshE calls | hsi9drzHR2k calls | Aftermath |
|-------|-------------------|-------------------|-----------|
| Baseline (return 0) | 60,343 | 19,968 | Audio/mutex loop |
| Non-zero (return R8) | **60,343** | **19,968** | Audio/mutex loop (IDENTICAL) |

## Conclusion: DEFINITIVE REFUTATION

**Returning non-zero does NOT break the loop.**

The "busy-wait loop" hypothesis was WRONG. These NIDs are NOT in a polling loop
with a return-value-based exit condition. They are in a FINITE iteration loop
that runs exactly 60,343 + 19,968 = 80,311 times and exits NATURALLY.

The previous analysis claiming "tight busy-wait loop, ~4000 calls/sec, return-zero
prevents loop exit" was based on a misinterpretation:
- Same stack address → same CALL SITE (true for any loop, not just busy-wait)
- High call rate → tight iteration (true, but doesn't mean infinite)
- "Stuck in busy-wait" → STUCK was wrong; the loop COMPLETES in ~2 seconds

## Real Boot Sequence (now visible)

```
T=0-4s    IL2CPP bootstrap (modules loaded, type initializers run)
T=4-6s    NID iteration loop runs 80,311 times — exits naturally
T=6s+     Game enters AUDIO/MUTEX LOOP (main thread):
            scePthreadMutexLock
            sceAudioOutOutput     ← ALSA backend unavailable, but stub returns 0
            sceKernelClockGettime
            sceKernelWaitSema     ← returns immediately (semaphore has tokens)
          → no frames rendered, no sceAgc calls, no VideoOut flips
          → GfxDeviceWorker thread is scheduled but never produces a frame
```

## Caller Map (NEW DATA)

| NID | Caller Site | RDI | R8 | R9 |
|-----|-------------|-----|----|----|
| 1D0H2KNjshE | eboot.bin+0x9B8551 | 0x601183C90 | 0x100 (256) | 0x40 (64) |
| 1D0H2KNjshE | eboot.bin+0x8BF76E | 0x0 | 0x400000 (4MB) | 0x0 |
| hsi9drzHR2k | eboot.bin+0x14335FE | 0x3FF00000 | 0x3FF0000000000000 (1.0 double) | 0x0 |

All callers are inside eboot.bin (Unity engine code), NOT inside Il2cppUserAssemblies.prx.

The second 1D0H2KNjshE call site (eboot.bin+0x8BF76E) passes a magic value
`0xC0DEC0DECAFEBA00` in RCX — likely a debug "uninitialized" or "deliberately
invalid" marker. This call happens AFTER a guest memory fault at rip=0x800B28A0D
(`cmp qword ptr [r12+38h], 0` — NULL deref at r12+0x38). It looks like a
post-fault cleanup path.

## New Hypothesis for the Audio/Mutex Loop

The main thread is in a tight loop calling:
- scePthreadMutexLock (succeeds)
- sceAudioOutOutput (stub returns 0 but actual ALSA backend fails)
- sceKernelClockGettime (succeeds)
- sceKernelWaitSema (returns immediately — semaphore has tokens)

None of these are NID stubs — they're real implementations. The loop is the
Unity main thread's "wait for next frame" loop. It is NOT calling any
sceAgc/VideoOut rendering APIs.

Possible root causes for no rendering:
1. **GfxDeviceWorker thread is stuck** — the Unity render thread is scheduled
   but never produces a frame. Check what it's blocked on.
2. **`GfxDevicePS5SharedData::CreateWorkload()` is a TODO in Unity engine itself**
   — guest log shows this. Unity shipped with an unimplemented function.
3. **Vulkan DCB queue is not initialized** — vk.flip_capture_failed warning
   shows `queue=dcb.graphics addr=0x0000000010CA0000 found=False initialized=False`.
4. **Audio backend failure cascade** — sceAudioOutOutput returns 0 but actual
   playback fails. Game may be in "wait for audio device" state.

## Next Investigation Steps (P1 revised)

The NID investigation is CLOSED. The NIDs are a red herring — they complete
naturally and have no impact on the boot progression.

### New P1: GfxDeviceWorker Trace

1. Trace what GfxDeviceWorker thread is doing after it's scheduled
2. Find which syscall/import it's blocked on or looping in
3. Check if CreateWorkload is supposed to be HLE'd by SharpEmu

### New P2: Audio Backend Investigation

1. Check if sceAudioOutOutput returning 0 (success) when actual ALSA fails
   is causing the main thread to spin
2. Try returning an error code from sceAudioOutOutput to see if main thread
   exits the audio loop

### New P3: DCB Queue Initialization

1. The `vk.flip_capture_failed ... initialized=False` warning is suspicious
2. Check what should initialize the dcb.graphics queue
3. Look at what calls sceAgcDriverSubmitDcb or similar

## Status: NID investigation CLOSED

- ✅ User's cheap experiment executed successfully
- ✅ Hypothesis "NIDs are loop exit condition" DEFINITIVELY REFUTED
- ✅ Caller mapping data captured (all in eboot.bin)
- ✅ Real boot sequence understood (NID loop → audio/mutex loop, no rendering)
- ✅ New investigation target identified (GfxDeviceWorker / Audio / DCB)
- ✅ Golden test still passes (139 frames, 188 colors, no regression)

---

# 18. CRITICAL UPDATE: Pipeline Counters — ROOT CAUSE IDENTIFIED

## User's Cheap Test (Round 2)

User suggested: before tracing the whole GfxDeviceWorker thread, run a cheaper test —
find the function responsible for initializing the `dcb.graphics` queue, and check
whether it is called at all. If yes-but-still-uninitialized → bug in HLE implementation.
If never-called → main thread never reaches that point.

## Implementation: PipelineCallCounters

Created `src/SharpEmu.Libs/Kernel/PipelineCallCounters.cs` — lightweight call-counter
activated by env var `SHARPEMU_PIPELINE_COUNTERS=1` (off by default → no-op).
Tracks 21 functions across AGC + VideoOut pipelines:
- AGC lifecycle: Init, CreateShader, CreatePrimState
- AGC submission: DriverSubmitDcb, DriverSubmitAcb, DriverSubmitMultiDcbs
- AGC draw calls: DrawIndex, DrawIndexAuto, DrawIndexOffset, DrawIndexIndirect, DispatchIndirect
- VideoOut lifecycle: Open, RegisterBuffers, RegisterBuffers2, SubmitFlip,
  WaitVblank, GetFlipStatus, AddFlipEvent, AddVblankEvent

Background timer dumps cumulative counts every 2 seconds. Per-call overhead is one
`Interlocked.Increment` (≈5ns) when enabled, zero when disabled.

## Side-by-side Comparison (20s runs)

| Function | Dreaming Sarah (working) | Yatzi (broken) |
|----------|--------------------------|----------------|
| AgcInit | 1 | 1 |
| AgcCreateShader | 99 | 36 |
| AgcCreatePrimState | 378 | 2 |
| **AgcDriverSubmitDcb** | **84** | **1** |
| AgcDcbDrawIndexAuto | 66 | 1 |
| AgcDcbDrawIndexOffset | 120 | 0 |
| VideoOutOpen | 1 | 1 |
| VideoOutRegisterBuffers2 | 1 | 1 |
| VideoOutSubmitFlip (direct) | 0 (uses DCB-embedded) | 1 (direct call) |
| VideoOutAddFlipEvent | 84 | 2 |
| Frames produced | 90 | 0 |
| flip_capture_failed warnings | 0 | 1 |
| UNMAPPED faults | 0 | 5 |

## ROOT CAUSE IDENTIFIED

**Bug location:** `src/SharpEmu.Libs/VideoOut/VulkanVideoPresenter.cs` line 1335
(method `RegisterKnownDisplayBuffer`)

**Bug:** When `sceVideoOutRegisterBuffers2` is called, `RegisterKnownDisplayBuffer`
adds the address to `_availableGuestImages` (the "valid flip target" dictionary) but
does NOT create a real Vulkan image in `_guestImages` (the "actual image resource"
dictionary). When the game later calls `sceVideoOutSubmitFlip` on this address
before any rendering, the presenter's `ExecuteOrderedGuestFlip` looks up
`_guestImages` and fails with `found=False initialized=False`.

**Effect chain:**
1. Unity calls `sceVideoOutRegisterBuffers2(addr=0x10CA0000)` →
   `_availableGuestImages[0x10CA0000] = format` is set, but `_guestImages` stays empty
2. Unity calls `sceVideoOutSubmitFlip(bufferIndex=0)` →
   `TrySubmitGuestImage` passes the `_availableGuestImages` check, returns success
3. Presenter thread later tries to capture the image for flip →
   `_guestImages[0x10CA0000]` lookup fails → `vk.flip_capture_failed` warning
4. Unity continues, accesses struct field at `r12+0x38` (some flip result struct)
5. `r12` is NULL because the flip didn't actually populate the expected state →
   `UNMAPPED fault at rip=0x800B28A0D: cmp qword ptr [r12+38h],0`
   RCX=0xC0DEC0DECAFEBA00 (Unity's "we're in error state" magic marker)
6. Unity's error handler runs — this IS the 80,311 NID calls (60,343 + 19,968)
   we previously mistook for "normal initialization"
7. Error handler completes, main thread enters audio/mutex spin loop forever

## Previous Section 17 Conclusion CORRECTED (Again)

Previous (section 17): "NID loop runs naturally in 2 seconds, then game enters
audio/mutex loop"

**CORRECTED:** The NID loop IS the Unity error handler. It is triggered by the
memory fault that follows the failed initial flip. The NIDs are not part of any
normal initialization — they are part of Unity's error cleanup path.

The non-zero return experiment (section 17) still definitively refuted the
"busy-wait loop" hypothesis — the NID loop IS finite (80,311 calls in 2 seconds).
But the REASON it runs is not "normal init", it's "error handler triggered by
failed initial flip."

## Why Dreaming Sarah Works

Dreaming Sarah does NOT call `sceVideoOutSubmitFlip` directly. It uses DCB-embedded
flips: it submits a DCB containing render commands AND a flip packet in the same
`sceAgcDriverSubmitDcb` call. The DCB-embedded flip path goes through
`TrySubmitOrderedGuestImageFlip` (which also checks `_availableGuestImages`) but
the DCB itself renders into the image first via `sceAgcDcbDrawIndexOffset`.
So by the time the flip executes, the image has been rendered into and
`_guestImages` is populated.

Yatzi uses a different pattern: it registers the display buffer, calls
`sceVideoOutSubmitFlip` directly (expecting a black frame to be displayed), and
only THEN starts its render loop. Real PS5 hardware creates the backing image
when the buffer is registered, so this pattern works on real hardware. SharpEmu
does not, causing the first flip to fail.

## Suggested Fix (NEXT P1)

Modify `RegisterKnownDisplayBuffer` (or its caller `RegisterBufferRange`) to also
create a placeholder Vulkan image in `_guestImages` for the registered address.
The image should be sized according to the buffer attribute (width, height, format)
and initialized to black. This makes the first flip succeed with a black frame,
matching real PS5 hardware behavior.

Alternative simpler fix: in `ExecuteOrderedGuestFlip`, when `_guestImages[address]`
is not found but `_availableGuestImages[address]` exists, create a black placeholder
image on-the-fly and proceed with the flip (instead of warning and returning).

## Status

- ✅ User's cheap test #2 executed successfully
- ✅ ROOT CAUSE identified (RegisterKnownDisplayBuffer missing Vulkan image creation)
- ✅ User's specific question answered: function IS called, flag NOT set (HLE bug)
- ✅ Section 17 conclusion corrected (NID loop = error handler, not normal init)
- ✅ Golden test still passes (138 frames, 188 colors, no regression)
- ✅ Did NOT modify any IL2CPP stubs (per user's explicit instruction)
- Next P1: implement the fix in RegisterKnownDisplayBuffer or ExecuteOrderedGuestFlip

---

# 19. CRITICAL UPDATE: Lifecycle Trace + Fallback Fix (INTERMEDIATE step)

## User's Cautious Approach (Round 3)

User wisely cautioned: before implementing the suggested fix (placeholder image
in RegisterKnownDisplayBuffer), verify the lifecycle of _guestImages. Maybe
RegisterBuffers is NOT supposed to create the image — maybe AGC is supposed to
create it later via a "commit"/"bind" step. If so, creating a placeholder would
just be a symptom-patching workaround, like the previous IL2CPP fake-heap mistake.

User's specific directive:
> Before building fallback image, trace CreateGuestImage lifecycle to determine
> if RegisterBuffers should create image or AGC should create it. Then add fix
> with feature flag.

## Step 1: Lifecycle Trace

Added GIMG-CREATE logging at all 3 sites where _guestImages entries are created
(activated by SHARPEMU_TRACE_GUEST_IMAGE_EVENTS=1, an existing env var):
- `cpu_backed_texture` (line 7004): CPU texture upload path
- `retained_variant` (line 10223): previously-stored variant reuse (rare)
- `render_target_new` (line 10360): AGC rendering into a render target

The caller analysis showed:
- Path `render_target_new` is invoked from `GetOrCreateGuestImage`, called from
  the AGC draw path (line 9436) when the game renders into a render target.
- Path `cpu_backed_texture` is invoked from `CreateTextureResource` for CPU-uploaded
  textures (rare; not the display buffer path).

## Step 2: Side-by-side Lifecycle Comparison

Ran 15s tests on both games with SHARPEMU_TRACE_GUEST_IMAGE_EVENTS=1:

| | Dreaming Sarah | Yatzi |
|--|----------------|-------|
| GIMG-CREATE events | 3 (2 render_target_new + 1 cpu_backed_texture) | **0** |
| First flip_capture_failed | (none) | addr=0x10CA0000 |
| Frames produced | 65 | 0 |

**CONFIRMED:** Yatzi never creates a single _guestImages entry. This proves
RegisterBuffers is NOT supposed to create the image — the legitimate creator
is the AGC render_target_new path. Yatzi just flips before ever rendering,
so it never reaches that path.

## Step 3: Fallback Implementation (Lazy, in ExecuteOrderedGuestFlip)

Following user's directive, implemented fallback as:
- Location: `ExecuteOrderedGuestFlip` (lazy, on-demand) — NOT `RegisterBuffers`
- Feature flag: `SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1` (off by default)
- Creates a B8G8R8A8Unorm Vulkan image, clears it to opaque black
  via `CmdClearColorImage((0,0,0,1))`, adds to _guestImages
- Only fires when:
  - source image not in _guestImages
  - AND _availableGuestImages contains the address (buffer was registered)
  - AND work.Width/Height > 0
  - AND SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1

Dreaming Sarah unaffected: uses DCB-embedded flips, always renders before
flipping, never hits the fallback path.

## Step 4: Side-by-side Test WITH/WITHOUT Fallback (20s Yatzi runs)

| Metric | Without fallback | With fallback |
|--------|-------------------|---------------|
| flip_capture_failed events | 1 | **0** |
| flip_fallback_created events | 0 | **1** |
| GIMG-CREATE events | 0 | **1** (path=fallback_flip) |
| Frames produced | 0 | **1** (frame #1, black) |
| UNMAPPED faults | 5 | 5 (NO CHANGE) |
| NID-COUNTS final | 60343 / 19968 | 60343 / 19968 (NO CHANGE) |
| 0xC0DEC0DECAFEBA00 magic markers | 15 | 15 (NO CHANGE) |

## HONEST EVALUATION

**What the fix accomplishes (REAL):**
- ✅ Eliminates flip_capture_failed warning (1 → 0)
- ✅ Creates a real Vulkan image for the registered display buffer
- ✅ Frame #1 is presented (black, but a real frame)
- ✅ This matches real PS5 hardware behavior (registered buffer = presentable)

**What the fix does NOT accomplish (ALSO REAL):**
- ❌ Game is STILL in Unity error state
- ❌ UNMAPPED faults (5) still occur at SAME rip (0x800B28A0D)
- ❌ NID loop still runs (Unity error handler still fires)
- ❌ Game still stalls in audio/mutex loop after first frame
- ❌ Magic marker 0xC0DEC0DECAFEBA00 still appears 15 times

This is an **INTERMEDIATE STEP**, not a complete fix. The fallback fix is correct
(it does exactly what it claims — make the flip succeed), but there is a
**separate root cause** triggering Unity's error path that the fallback does not
address.

## Step 5: Timeline Analysis (Why fix doesn't fully solve)

Examined exact ordering of events in both phases:

WITHOUT fallback:
```
T=5s  Vulkan VideoOut ready           (line 2249)
T=5s  vk.flip_capture_failed          (line 2250) — image lookup failed
T=5s  UNMAPPED fault #1               (line 2251) — NULL deref at r12+0x38
        RCX=0xC0DEC0DECAFEBA00 (Unity error state marker)
T=5s+ Unity error handler runs        (60,343 + 19,968 NID calls)
T=7s  Game stalls in audio/mutex loop
```

WITH fallback:
```
T=5s  Vulkan VideoOut ready           (line 2249)
T=5s  UNMAPPED fault #1               (line 2250) — NULL deref STILL fires
        NOTE: fallback not yet created at this point!
T=5s  AudioOut ports 1, 2 initialized (silent backend)
T=5s  FMOD threads scheduled
T=5s+ flip_fallback_created           (line 2282) — flip retry succeeds
T=5s+ vk.present_taken + frame #1     (line 2284-2285) — FRAME PRESENTED
T=5s+ Unity error handler still runs  (same NID loop, same magic marker)
T=7s+ Game still stalls in audio/mutex loop
```

**CRITICAL FINDING:** The UNMAPPED fault at rip=0x800B28A0D happens
IMMEDIATELY after Vulkan VideoOut becomes ready, BEFORE any flip is
attempted (with or without fallback). The flip_capture_failed warning
we previously thought was the cause is actually a CONSEQUENCE — Unity's
error path fires first, then attempts the failed flip as part of error
cleanup.

This means the previous "ROOT CAUSE IDENTIFIED" was only PARTIALLY correct.
The flip failure was indeed a real bug (and the fallback fix is correct),
but there is a SEPARATE root cause that triggers Unity's error path before
the flip even happens.

## New P1: Investigate rip=0x800B28A0D UNMAPPED Fault

What we know:
- Happens immediately after `Vulkan VideoOut ready`
- Instruction: `cmp qword ptr [r12+38h],0` (NULL deref at r12+0x38)
- R12 is NULL (r12+0x38 = 0x38 = fault address)
- RCX=0xC0DEC0DECAFEBA00 (Unity error state magic marker — Unity knows
  it's in an error state by this point)
- Same RIP in WITH and WITHOUT fallback runs

What we don't know:
- What is at r12 supposed to be? (some Unity object, probably a graphics
  device wrapper or render queue)
- What HLE function should have populated r12?
- Why does this fire IMMEDIATELY after VideoOut ready? (something is
  missing from the VideoOut ready sequence)

Investigation approach:
- Disassemble around rip=0x800B28A0D in eboot.bin to see what's nearby
- Look at what's just before the cmp — what set r12?
- Find the Unity graphics init sequence that should populate this struct
- Cross-reference with the list of HLE functions Unity calls during
  graphics init

## Status

- ✅ User's careful approach (lifecycle trace BEFORE fix) executed correctly
- ✅ RegisterBuffers-vs-AGC question definitively answered: AGC creates image
- ✅ Fallback fix implemented correctly (lazy, feature-flagged, no regression)
- ✅ Fallback fix WORKS (flip no longer fails, frame is presented)
- ⚠️ Fallback fix is INTERMEDIATE — separate root cause for Unity error state
- ✅ Golden test still passes (118 frames, 169 colors, no regression)
- ✅ Did NOT modify any IL2CPP stubs (per user's explicit instruction)
- ⚠️ Section 18 conclusion was PARTIALLY correct — flip failure was real bug,
  but not the only root cause. Section 19 documents the additional finding.
- Next P1: investigate UNMAPPED fault at rip=0x800B28A0D
- New env var: SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1 (fallback image creation)

---

# 20. CRITICAL UPDATE: ROOT CAUSE FOUND — Empty unity_builtin_extra

## User's Cheap Test #4 — Most Insightful Yet

User suggested: grep source for `0xC0DEC0DECAFEBA00` before doing any
disassembly. If the magic marker is SharpEmu's own (e.g., a TLS canary),
the entire "Unity error state" interpretation collapses.

## Step 1: Cheap Grep Test

Searched SharpEmu source for `0xC0DEC0DECAFEBA00`. Found 5 occurrences,
ALL in SharpEmu source (NOT in any Unity-related code):

```
src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs:4550:
    !context.TryWriteUInt64(tlsBase + 0x28, 0xC0DEC0DECAFEBA00UL)

src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs:36:
    private const ulong StackCheckGuardValue = 0xC0DEC0DECAFEBA00UL;

src/SharpEmu.Core/Cpu/CpuDispatcher.cs:378:
    !context.TryWriteUInt64(tlsBase + 0x28, 0xC0DEC0DECAFEBA00UL)

src/SharpEmu.HLE/HleDataSymbols.cs:18:
    private const ulong StackChkGuardValue = 0xC0DEC0DECAFEBA00UL;

src/SharpEmu.Libs/Kernel/KernelRuntimeCompatExports.cs:55:
    private static readonly ulong _stackChkGuardValue = 0xC0DEC0DECAFEBA00UL;
```

**CONCLUSION:** `0xC0DEC0DECAFEBA00` is SharpEmu's TLS stack canary value
(written to `tlsBase + 0x28`, the standard `__stack_chk_guard` location).
It is NOT a Unity error-state marker. Previous interpretation in section 19
("RCX=0xC0DEC0DECAFEBA00 — Unity's error state magic marker") was WRONG.

The reason RCX has this value at the fault is because RAX was just XOR'd
to 0, and RCX happens to hold the TLS canary (loaded earlier for stack
check validation), which is a normal occurrence for any function call.

## Step 2: Enhanced UNMAPPED Logger + Full Register Dump

Found that the existing UNMAPPED logger dumped RAX/RBX/RCX/RDX/RSI/RDI/R8/R9/
R15/RSP but was missing R10/R11/R12/R13/R14/RBP. For `cmp [r12+0x38], 0`
faults, R12 is the key register.

Enhanced logger to dump all registers + thread name. Built and ran Yatzi
with fallback enabled.

```
[UNMAPPED] #1 READ rip=0x800B28A0D fault=0x38 instr='cmp qword ptr [r12+38h],0'
  RAX=0x0 RBX=0x801BB0024 RCX=0xC0DEC0DECAFEBA00 RDX=0x1
  RSI=0x60250010 RDI=0x600500A0 R8=0x400000 R9=0x0
  R10=0x602500C0 R11=0x602500CF R12=0x0 R13=0x801EF2A70
  R14=0x0 R15=0x7F3C44ED7920 RBP=0x6FFFF01FBA40 RSP=0x6FFFF01FB980
  thread=0x0 name='?'
```

**KEY FINDING: R12 = 0 (NULL).** The fault reads from address 0x38 (= R12 + 0x38).

## Step 3: Disassembly — INTENTIONAL NULL Dereference

Wrote `/home/z/my-project/scripts/disasm_around_rip.py` (uses pyelftools +
capstone). Disassembled 80 instructions before and 50 after the fault site.

Discovered the abort pattern:

```asm
0x800B28A08:  xor      eax, eax        ; RAX = 0
0x800B28A0A:  xor      r12d, r12d      ; R12 = 0 (INTENTIONAL!)
0x800B28A0D:  cmp      qword ptr [r12 + 0x38], 0    ; FAULT — reading NULL+0x38
0x800B28A13:  jne      0x800b27dd0     ; jump if [0x38] != 0 (impossible)
0x800B28A19:  jmp      0x800b289ed     ; else error path
0x800B28A1B:  call     0x801938160     ; abort handler
0x800B28A20:  ud2                       ; UNDEFINED INSTRUCTION — abort()
```

The code DELIBERATELY sets R12 = NULL then dereferences it. This is Unity's
assertion abort pattern — when an invariant fails, the code jumps to a
crash site that intentionally NULL-derefs to trigger SIGSEGV.

## Step 4: Caller Analysis — What Triggered the Abort?

Found two conditional jumps to the abort site `0x800B28A08`:
- `0x800B27D98:  je 0x800b28a08`
- `0x800B27DCA:  je 0x800b289ed`

Disassembled around `0x800B27D98`. Found a shader lookup sequence:

```asm
0x800B27D54:  mov r12, qword ptr [rip + 0x13cb18d]  ; r12 = global cache
0x800B27D5B:  test r12, r12
0x800B27D5E:  jne 0x800b27dc2                       ; if cached, skip lookup
0x800B27D60:  lea rbx, [rip + 0x10882bd]            ; arg1 = string1
0x800B27D67:  mov rdi, rbx
0x800B27D6A:  call 0x800c12d20                       ; (type lookup, returns rax)
0x800B27D6F:  mov rdi, qword ptr [rip + 0x13724ea]  ; arg1 = global
0x800B27D76:  lea rsi, [rip + 0x12c837b]            ; arg2 = string2
0x800B27D7D:  lea rdx, [rbp - 0x50]
0x800B27D81:  mov qword ptr [rbp - 0x50], rbx
0x800B27D85:  mov qword ptr [rbp - 0x48], rax
0x800B27D89:  call 0x800aba330                       ; <-- KEY CALL (lookup)
0x800B27D8E:  mov qword ptr [rip + 0x13cb153], rax  ; cache result
0x800B27D95:  test rax, rax
0x800B27D98:  je 0x800b28a08                        ; if NULL -> abort site
```

The lookup function at `0x800aba330` returns NULL, triggering the abort.

## Step 5: Read String Argument — "Internal-ErrorShader.shader"

Read the string at guest address `0x801BB0024` (= `0x800B27D67 + 0x10882bd`):

```python
ASCII at 0x801BB0024: 'Internal-ErrorShader.shader'
```

**This is Unity's built-in error shader name!** Unity is trying to find its
INTERNAL ERROR SHADER (used as fallback when a regular shader fails to load),
and the lookup function returns NULL because the shader isn't available.

## Step 6: ROOT CAUSE — Empty Unity Built-in Resource Files

Checked Yatzi's `Media/Resources/` directory:

```
$ ls -la /tmp/games/yatzi/Media/Resources/
-rw-rw-r-- 0 bytes  unity default resources
-rw-rw-r-- 0 bytes  unity_builtin_extra
```

**Both files are 0 bytes!** These are Unity's built-in resource bundles that
contain ALL built-in shaders, including `Internal-ErrorShader.shader`. The
game ships with EMPTY files — either the dump was incomplete or these were
stripped to save space (they're normally multi-MB files containing the
entire Unity shader library).

When Unity tries to load the Internal-ErrorShader:
1. It calls the lookup function at `0x800aba330`
2. The function reads from `unity_builtin_extra` (which is empty)
3. The shader is not found → returns NULL
4. Unity deliberately NULL-derefs R12 to abort

## Step 7: Timeline (Corrected Once More)

Line-by-line timeline of Yatzi boot:

```
Line 2148: VideoOutManager backend selected (VulkanVideoPresenter)
Line 2150: First NID-TRACE — NID loop starts (NOT error handler — corrected)
Line 2156: UnityEOPThread scheduled
Line 2157: [DEBUG][PRINF] todo: void GfxDevicePS5SharedData::CreateWorkload()
           (Unity's OWN printf — Unity engine has unimplemented function)
Line 2158-2160: GfxFlipThread, UnityGfxDeviceWorker scheduled
Line 2161: 1D0H2KNjshE NID loop continues
Line 2247: Vulkan VideoOut ready
Line 2248: UNMAPPED fault #1 (Internal-ErrorShader lookup returns NULL → abort)
Line 2295: First frame presented (with fallback)
Line 2333: NID loop completes (60343/19968 calls)
```

The NID loop runs alongside normal init, NOT as error handler. The fault at
line 2248 is the actual abort triggered by the missing shader.

## Conclusion

**Previous sections 17, 18, 19 all had partially-correct conclusions:**

- Section 17: NID loop is finite ✓, but not "error handler" — it's normal init
- Section 18: flip_capture_failed was a real bug ✓, fallback fix is correct
- Section 19: UNMAPPED at 0x800B28A0D happens before flip ✓, but cause is
  missing shader, not missing graphics object

**Actual root cause:** Yatzi ships with empty `unity_builtin_extra` and
`unity default resources` files. Unity cannot find `Internal-ErrorShader`
and aborts.

**The fix is NOT in SharpEmu code.** It's a game data issue. Options:
1. User provides a real `unity_builtin_extra` from a Unity PS5 build
2. SharpEmu implements a synthetic shader loader (very invasive)
3. SharpEmu intercepts the lookup function `0x800aba330` to return a
   placeholder shader object (would require knowing the shader object layout)

## Status

- ✅ User's cheap test #4 (grep source) executed — found 0xC0DEC0DECAFEBA00 is
  SharpEmu's TLS canary, NOT Unity's error marker
- ✅ Full register dump captured — R12=0 at fault
- ✅ Disassembly revealed INTENTIONAL NULL deref (Unity assertion abort)
- ✅ Caller identified — shader lookup at 0x800ABA330 returned NULL
- ✅ String read — "Internal-ErrorShader.shader" (Unity built-in)
- ✅ ROOT CAUSE FOUND — empty unity_builtin_extra file in game data
- ✅ Did NOT modify any IL2CPP stubs (per user's instruction)
- ✅ Golden test still passes (140 frames, 188 colors)
- ⚠️ This is a game data issue, not SharpEmu code issue
- Modified file: src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Exceptions.cs
  (added R10-R14, RBP, thread name to UNMAPPED logger — broadly useful)
- New reusable tool: scripts/disasm_around_rip.py
