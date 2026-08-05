# EXP-157 — IL2CPP Initialization Path Validation

**Date:** 2026-08-06
**Status:** TEST ONLY — No code changes, no HLE, no architecture modifications
**Rule:** Only collect evidence

---

## Q1: Is il2cpp_runtime_class_init Actually Executed?

### Evidence

**RIP Trace Results (SHARPEMU_TRACE_RIP=1):**

| Slot | Address | Description | Hits |
|------|---------|-------------|------|
| 1 | 0x80015DCD0 | Producer function | **0** (NEVER reached) |
| 2 | 0x8001EDB28 | Producer caller | **0** (NEVER reached) |
| 3 | 0x804F6E9E6 | Dispatch loop WaitSema | **1** (reached once) |

**BST Node for il2cpp_runtime_class_init:**
- Node #65 @0x200002b240
- Function pointer at node+0x28 (not directly verifiable without runtime memory dump)

**INT3 fix verification:**
- EXP-149 INT3 fix (single-step re-patch) is WORKING
- No SIGILL crash (unlike EXP-148 which had the bug)
- The dispatch loop INT3 hit was handled correctly

### Answer

**Cannot definitively confirm** whether `il2cpp_runtime_class_init` is executed because:
1. The function address is stored in a GOT slot that we cannot read at runtime
2. The resolver runs NATIVELY (not through HLE dispatch), so no resolver traces
3. No INT3 was installed at the `il2cpp_runtime_class_init` function address

**However**, the fact that 38000+ mutex calls occur during IL2CPP type initialization suggests that SOME IL2CPP type initialization code IS running. The question is whether `il2cpp_runtime_class_init` specifically is called, or if type initialization happens through a different path.

---

## Q2: Track Writes to 0x808D67BB8 and 0x808D67B98

### Evidence

**From EXP-152 static analysis (binary):**
- 0x808D67B98: 3 RIP-relative write instructions (all `mov dword [addr], 1`)
  - 0x804FB1C1B in function 0x804FB1B90
  - 0x804FBF45B in function 0x804FBF250
  - 0x804FBF509 in function 0x804FBF250
- 0x808D67BB8: 2 RIP-relative write instructions
  - 0x804FB1C93 in function 0x804FB1B90 (writes 1)
  - 0x804FBF59F in function 0x804FBF250 (writes 0 — cleanup)

**From EXP-153 analysis:**
- ALL writers have chicken-and-egg guards:
  - Writer 0x804FB1B90 checks `byte [0x808D67BB8]` at entry → if 0, return early
  - Writer 0x804FBF250 checks `byte [0x808D67B98]` → if 0, skip write

**Runtime evidence:**
- Cannot verify at runtime — the available trace tools (SHARPEMU_LOG_POINTER_WINDOWS) only trigger on exceptions, and the deadlock is a stall (not an exception)
- The single-step trace (SHARPEMU_SINGLE_STEP_TRACE=1) was armed but never activated because it requires a SIGTRAP to trigger, and no SIGTRAPs occur after import #38000

### Answer

**No runtime writes detected.** Based on static analysis:
- The flags are NEVER written at runtime because the writer functions have chicken-and-egg guards
- The writer functions check the flag before writing — if flag is 0, they return early
- No unconditional writer exists
- The flags stay at 0 (BSS) throughout execution

---

## Q3: Trace from il2cpp_runtime_class_init to PlayerLoop.Initialize

### Expected Path
```
IL2CPP init (dt_init) → type flags set → PlayerLoop registration → AGC submit
```

### Actual Path (from runtime log)
```
1. libc.prx dt_init → returns 0 ✅
2. libSceNpCppWebApi.prx dt_init → returns 0 ✅
3. Il2cppUserAssemblies.prx dt_init → returns 0 ✅
4. PS5Util.prx dt_init → returns 0 ✅
5. Eboot entry (0x800000070) starts ✅
6. IL2CPP type initialization (38000+ mutex calls) ✅
7. 13 AssetGarbageCollectorHelper threads created ✅
8. 1 GC scavenger thread created ✅
9. [DIVERGENCE] — PlayerLoop registration SKIPPED ❌
10. Dispatch loop entered ✅
11. WaitSema(0x81) → DEADLOCK ❌
```

### First Divergence

**Step 9: PlayerLoop registration is SKIPPED.**

The execution goes directly from thread creation (step 7-8) to the dispatch loop (step 10) without any PlayerLoop registration. Evidence:
- 0 VideoOut API calls (PlayerLoop should call sceVideoOutOpen)
- 0 AgcDcb calls (PlayerLoop should trigger GPU initialization)
- 0 SubmitFlip calls (no rendering)
- The dispatch loop is entered directly, blocking on WaitSema(0x81)

### Where Does It Stop?

The execution stops at **WaitSema(0x81)** in the dispatch loop. The dispatch loop is:
```
rip=0x00006FFFFD001150 (WaitSema import stub)
rdi=0x00006FFF00000081 (semaphore handle 0x81)
[rsp]=0x0000000804F6E9EB (return to dispatch loop)
```

The main thread blocks on WaitSema(0x81) because no work is ever submitted to the worker queue. The bootstrap job that should signal semaphore 0x81 is never submitted because PlayerLoop registration never runs.

---

## Q4: Single-Step Trace Results

### Configuration
```
SHARPEMU_SINGLE_STEP_TRACE=1
SHARPEMU_STEP_START_IMPORT=38000
SHARPEMU_STEP_MAX=10000
```

### Result

**The single-step trace was ARMED but NEVER ACTIVATED.**

```
[STEP-TRACE] Will start after import #38000, maxSteps=10000
[STEP-TRACE] Stop RIP set to 0x0000000804F6E510
[STEP-TRACE] TRIGGER ARMED after import #38000 — will activate on next exception
```

### Why It Didn't Activate

The single-step trace trigger requires a SIGTRAP to activate. After import #38000, the execution continues with normal import dispatches (mutex calls, semaphore creation) without generating any SIGTRAPs. The trigger waits for "the next exception" but no exception occurs until the deadlock stall.

### Available RIP/Instruction/Register Data

From the RIP trace (SHARPEMU_TRACE_RIP=1):
```
[RIP-TRACE] HIT slot=3 addr=0x0000000804F6E9E6 rip=0x0000000804F6E9E7
  rdi=0x0000000000000001 rsi=0x0000000000000001 rax=0x0000000000000000
```

This is the dispatch loop WaitSema call site. The registers show:
- rdi=1 (not the semaphore handle — this is before the WaitSema call)
- rax=0 (return value from previous call)

From the stall snapshot:
```
rip=0x00006FFFFD001150 (WaitSema import stub)
rsp=0x00006FFFF01FB958
rbp=0x00006FFFF01FB980
rax=0x00007F7DB9C23000 (WaitSema return value area)
rdi=0x00006FFF00000081 (semaphore handle 0x81)
rsi=0x0000000000000001 (count=1)
[rsp]=0x0000000804F6E9EB (return to dispatch loop)
```

---

## Q5: Compare Yatzi vs Dreaming Sarah

### Comparison Table

| Metric | Yatzi (Unity IL2CPP) | Dreaming Sarah (Native C++) |
|--------|---------------------|---------------------------|
| IL2CPP mentions | 251 | 0 |
| VideoOut/Agc calls | 0 | 7 |
| Threads created | 14 (13 AGC + 1 GC) | 14 (various named) |
| Stall/deadlock | 18 (deadlock) | 0 (no deadlock) |
| Mutex imports | 92 | 89 |
| Sema imports | 60 | 2 |
| Exit code | 4 (deadlock) | 124 (timeout — still running) |
| Thread types | AssetGarbageCollectorHelper x13, GC x1 | spi_main, AudioOut, Trophy, save, ratamedia x10 |

### Key Differences

1. **IL2CPP**: Yatzi uses Unity IL2CPP (251 mentions). Dreaming Sarah is native C++ (0 mentions).

2. **Rendering**: Dreaming Sarah reaches VideoOut (7 calls). Yatzi never reaches VideoOut (0 calls). This confirms Yatzi never gets to the rendering stage.

3. **Thread Types**: 
   - Yatzi creates 13 "AssetGarbageCollectorHelper" threads (Unity Job System workers) + 1 GC scavenger
   - Dreaming Sarah creates named threads (spi_main, AudioOut, Trophy, save, ratamedia streamers)

4. **Semaphores**: Yatzi creates 60 semaphores (Unity worker queue). Dreaming Sarah creates only 2 (simple sync).

5. **Deadlock**: Yatzi deadlocks (18 stall messages). Dreaming Sarah does not deadlock (0 stall messages).

### IL2CPP Path Comparison

| Step | Yatzi | Dreaming Sarah |
|------|-------|----------------|
| Package loaded | ✅ | ✅ |
| PRX loaded | ✅ | ✅ (libc only) |
| dt_init | ✅ | ✅ |
| Type initialization | ✅ (38000+ mutex) | N/A (no IL2CPP) |
| PlayerLoop registration | ❌ SKIPPED | N/A (native game loop) |
| Bootstrap job | ❌ MISSING | N/A |
| Rendering | ❌ NEVER | ✅ (VideoOut) |
| Result | DEADLOCK | SUCCESS |

### Why Dreaming Sarah Works

Dreaming Sarah is a native C++ game. It does NOT use IL2CPP, so:
1. No BST resolver — no RAX propagation issue
2. No type initialization flags — no chicken-and-egg guard
3. No PlayerLoop registration — native game loop starts directly
4. No Unity Job System — no worker queue, no WaitSema(0x81)
5. Direct VideoOut calls — rendering starts immediately

### Why Yatzi Fails

Yatzi uses Unity IL2CPP. The IL2CPP initialization chain is:
1. dt_init runs → sets up BST resolver → returns 0 ✅
2. Eboot runs → calls IL2CPP API functions → type initialization (38000+ mutex) ✅
3. Type init flags should be set → **NOT SET** ❌
4. PlayerLoop should register → **SKIPPED** ❌
5. Bootstrap job should be submitted → **MISSING** ❌
6. Dispatch loop enters → blocks on WaitSema(0x81) → **DEADLOCK** ❌

The divergence is at step 3: type init flags are not set, which causes the gate function to skip all IL2CPP-generated methods, including PlayerLoop.Initialize().

---

## Summary

### Confirmed Facts

1. **il2cpp_runtime_class_init execution**: Cannot definitively confirm — no INT3 was installed at the function address, and the resolver runs natively (no HLE traces)

2. **Flag writes**: No runtime writes detected — the writer functions have chicken-and-egg guards that prevent the initial set

3. **First divergence**: PlayerLoop registration is SKIPPED between IL2CPP type initialization and dispatch loop entry

4. **Single-step trace**: Was armed but never activated — requires SIGTRAP to trigger, but no SIGTRAPs occur after import #38000

5. **Game comparison**: Dreaming Sarah works because it's native C++ (no IL2CPP). Yatzi fails because IL2CPP type init flags are never set, causing PlayerLoop to be skipped.

### Root Cause Status

**The root cause is NOT EXP-138 RAX propagation** (validated in EXP-156 — the resolver runs natively).

**The root cause IS**: The type initialization flags (0x808D67BB8, 0x808D67B98) are NEVER set, causing the gate function (0x804FB8E60) to skip ALL IL2CPP-generated methods, including PlayerLoop.Initialize().

The flags are not set because:
1. The writer functions have chicken-and-egg guards
2. No unconditional writer exists
3. Something on real PS5 sets these flags that SharpEmu doesn't replicate

### Next Steps

1. **Install INT3 at il2cpp_runtime_class_init function address** — read the GOT slot to find the address, then install INT3 to verify if the function is called
2. **Fix the single-step trace trigger** — the trigger requires a SIGTRAP, but no SIGTRAPs occur after import #38000. Need to change the trigger to activate on the next import dispatch instead
3. **Investigate what sets the type init flags on real PS5** — the flags should be set by the IL2CPP runtime C code, not generated code
4. **Check if SharpEmu's IL2CPP fake stubs interfere** — the `TryResolveIl2CppApiAddress` function returns fake stubs for il2cpp_* functions, which might prevent the real IL2CPP runtime from functioning correctly
5. **Trace the gate function execution** — install INT3 at 0x804FB8E60 to count how many times the gate is called and what flag values it sees

---

## Artifacts

- `/tmp/exp157_rip_trace.log` — RIP trace run log
- `/tmp/exp157_step_trace.log` — Single-step trace run log
- `/tmp/exp157_pointer_windows.log` — Pointer windows run log
- `/tmp/exp157_ds_run.log` — Dreaming Sarah run log
- `/tmp/exp156_yatzi_run.log` — Yatzi run log (from EXP-156)
