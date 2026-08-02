# Independent Validation Report — EXP-005 Style Claims

**Date:** 2026-08-02
**Commit:** 52b4d4f
**Method:** Evidence compiled from EXP-095 through EXP-109 (runtime traces + static analysis)

---

## Validation Result 1: "Unity Asset Loading was the blocker"

### Claim:
"Unity Asset Loading was the blocker. Game runs past initialization because missing game data files were the issue."

### Verdict: REJECTED

### Evidence:
1. **Required YATZI files ARE present:**
   - `eboot.bin`: 32,697,964 bytes (SHA256 matches master state)
   - `global-metadata.dat`: 10,669,264 bytes at `Media/Metadata/`
   - `Il2cppUserAssemblies.prx`: present at `Media/Modules/`

2. **fopen/path resolution works:**
   - Metadata IS loaded correctly (EXP-095: `il2cpp_class_get_method_from_name` succeeds, `rax=0x6007E64D0`)
   - PRX loads, DT_INIT_ARRAY executes (EXP-092)

3. **Media files ARE found:**
   - The PRX reads `global-metadata.dat` successfully (EXP-060 confirmed)

4. **Execution does NOT progress because of asset loading:**
   - The blocker is `WaitSema(0xA6)` — a ThreadPool synchronization deadlock
   - All 15 threads block on semaphore handles
   - Exit code: 4 (stall)
   - No rendering, no frame generation, no GPU submission

5. **First frame IS still blocked — for a different reason:**
   - Blocker: work-submission function `0x804F6EC20` never reached (EXP-096: 0 INT3 hits)
   - Callback `0x804FA1FE0` registered but never invoked (EXP-106..108)
   - PLT 218 never reached (EXP-107: 0 INT3 hits)
   - All 18 callers of `0x804F760B0` have 0 callers (EXP-109)

### Impact:
Does NOT change debugging direction. The ThreadPool deadlock is the real blocker, not asset loading.

---

## Validation Result 2: "ThreadPool is working"

### Claim:
"ThreadPool is working."

### Verdict: REJECTED

### Evidence:
1. **Worker threads ARE created:**
   - 13 `AssetGarbageCollectorHelper` workers + 1 GC thread
   - Semaphores created (handles 0xA5..0xB5)

2. **Work submission function 0x804F6EC20 NEVER reached:**
   - EXP-096: INT3 at all 3 call sites (0x804F4571A, 0x804F9FAAA, 0x804FA14C8) — **ZERO hits**
   - The 3 containing functions have 0 direct callers

3. **SignalSema NEVER called:**
   - No `sema.signal` entries for handle 0xA6 in any log
   - All 15 threads block on `WaitSema(0xA6)` forever
   - Exit code: 4 (stall)

### Verdict:
ThreadPool infrastructure exists (workers + semaphores), but work execution path is NOT validated. ThreadPool is NOT working.

### Impact:
Confirms current debugging direction. The deadlock is real and unchanged.

---

## Validation Result 3: Callback Chain

### Claim:
"Callback registration and invocation work correctly."

### Verdict: PARTIALLY CONFIRMED (registration works, invocation does NOT)

### Evidence:
1. **Callback IS stored correctly:**
   - EXP-098: registration path (`0x804FA20E0`) IS reached
   - EXP-099: once-init primitive returns SUCCESS (eax=0)
   - EXP-101: all PLT stubs succeed (eax=0)
   - EXP-103 (corrected): callback stored at valid address `0x20337660` (NOT NULL — EXP-102's r14=0 was a tracer bug)

2. **Callback is NEVER invoked:**
   - `0x804FA1FE0` (callback function): 0 direct callers, 0 runtime hits
   - `0x804F88AD0` (callback invoker): 0 direct callers, 0 INT3 hits (EXP-107)
   - `0x804FA84E0` (trampoline): 0 INT3 hits (EXP-107)
   - PLT 218 (`0x804FC3720`): 0 INT3 hits (EXP-107)
   - `0x804F760B0` (most promising caller path): all 18 callers have 0 callers (EXP-109)

3. **Callback chain IS connected to work submission (static):**
   - `0x804FA1FE0` → `0x804F9FA80` (at 0x804FA2089) ✓ verified (EXP-106/108)
   - `0x804F9FA80` → `0x804F6EC20` (at 0x804F9FAAA) ✓ verified (EXP-106/108)
   - But this chain is NEVER executed at runtime

### Impact:
Confirms that the callback registration subsystem and the work-submission path are the correct investigation target, but the invocation mechanism is entirely missing.

---

## Validation Result 4: "PLT218 is the missing link"

### Claim:
"PLT218 is the missing link that should invoke the callback."

### Verdict: REJECTED

### Evidence:
- `0x804FC3720` (PLT 218): 0 INT3 hits (EXP-107)
- `0x804FA84E0` (trampoline to PLT 218): 0 INT3 hits (EXP-107)
- `0x804F88AD0` (calls the trampoline): 0 INT3 hits (EXP-107)
- The entire chain is never reached at runtime

### Impact:
EXP-106's claim was based on static analysis only. Runtime evidence disproves it. The gap is upstream — nothing calls `0x804F88AD0`.

---

## Validation Result 5: "IL2CPP imports resolve (466/466)"

### Claim:
"IL2CPP: 466/466 imports resolve"

### Verdict: PARTIALLY CONFIRMED

### Evidence:
- Most imports DO resolve (the emulator boots, IL2CPP initializes, method lookups succeed)
- However, some imports are unresolved: `nid=J3edELK4FvM` (EXP-100) — though this was proven NOT to be the blocker
- The 466/466 count may be from a different run or configuration

### Impact:
Import resolution is not the blocker. The blocker is the missing callback invocation mechanism.

---

## Final Trust Assessment

| Claim | Verdict | Confidence |
|-------|---------|-----------|
| "Asset loading was the blocker" | REJECTED | High (files present, metadata loads, deadlock is ThreadPool) |
| "ThreadPool is working" | REJECTED | High (0x804F6EC20 never reached, SignalSema never called) |
| "Callback registration works" | CONFIRMED | High (all PLT stubs succeed, callback stored at valid address) |
| "Callback invocation works" | REJECTED | High (0 INT3 hits on all invocation path addresses) |
| "PLT218 is the missing link" | REJECTED | High (0 INT3 hits, never reached at runtime) |
| "466/466 imports resolve" | PARTIALLY CONFIRMED | Medium (most resolve, some unresolved but not blockers) |

**Overall:** The Minimax EXP-005 style claims have NO factual value for the current debugging state. The real blocker is a missing indirect call dispatch mechanism that should invoke registered IL2CPP callbacks, triggering the work-submission path that calls `SignalSema`.
