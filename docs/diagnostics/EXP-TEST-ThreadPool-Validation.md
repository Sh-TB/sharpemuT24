# EXP-TEST-ThreadPool-Validation — External Claim REJECTED

**Identity:** Yatzi / PPSA17697 / verified
**Configuration:** Evidence compiled from EXP-095 through EXP-105 (no new runtime test needed — existing evidence is conclusive)
**Path:** B (real metadata path)

**Test Goal:** Verify or reject external claim: "ThreadPool is working" and "First frame is only blocked by missing game data files."

**Verdict:** **B) External claim REJECTED:** "ThreadPool initializes but work execution path is still blocked."

---

## External Claims Under Test

1. "ThreadPool is working"
2. "First frame is only blocked by missing game data files"

## Runtime Evidence (from EXP-095 through EXP-105)

### ThreadPool Worker Creation: YES

Workers ARE created during initialization:
- 13 `AssetGarbageCollectorHelper` worker threads created
- 1 GC thread created (`Thread-*`, entry `0x804F88AA0`)
- Semaphores created (handles 0xA5..0xB5, SuspendSemaphore 0xA8, ResumeSemaphore 0xA9)

### Work Item Submission: NO

The work-submission function `0x804F6EC20` (which calls `SignalSema` to wake workers) was **NEVER reached**:
- INT3 at all 3 call sites (`0x804F4571A`, `0x804F9FAAA`, `0x804FA14C8`): **ZERO hits** (EXP-096)
- The 3 containing functions (`0x804F456E0`, `0x804F9FA80`, `0x804FA1440`) have **0 direct callers** (EXP-096)

### Callback Execution: NO

The `_ThreadPoolWaitCallback` lookup succeeds (EXP-095: `rax=0x6007E64D0`), but:
- The callback function `0x804F52820` has **0 direct callers** (EXP-105)
- The callback registration succeeds (EXP-098..101: all PLT stubs return 0, `xchg [r14], rax` stores at valid address)
- But no external code invokes the stored callback

### SignalSema: NEVER CALLED

`SignalSema(0xA6)` is never called by any thread. All 15 threads block on `WaitSema(0xA6)` and related semaphores forever. Exit code: 4 (stall).

### Game Data Files: PRESENT

- `eboot.bin`: 32,697,964 bytes, SHA256 matches master state
- `global-metadata.dat`: 10,669,264 bytes, at `Media/Metadata/`
- `Il2cppUserAssemblies.prx`: present
- Metadata IS loaded correctly (EXP-095: `il2cpp_class_get_method_from_name` succeeds)
- The blocker is NOT a missing file — it's a ThreadPool synchronization deadlock

## Addresses Reached

| Address | Function | Reached? | EXP |
|---------|----------|----------|-----|
| `0x804F04BA0` | real_init | YES | EXP-040 |
| `0x804F04C5C` | call#7 (il2cpp_codegen_register) | YES | EXP-041 |
| `0x804F04C70` | call to 0x804F51020 (working once-init) | YES | EXP-098 |
| `0x804F055D6` | _ThreadPoolWaitCallback lookup | YES | EXP-095 |
| `0x804FA20E0` | registration function | YES | EXP-098 |
| `0x804F889D0` | registration helper | YES | EXP-098 |
| `0x804F88A00` | once-init primitive call | YES | EXP-099 |
| `0x804F88A3F/55/67` | PLT stubs in registration | YES | EXP-101 |
| `0x804F88A76` | xchg [r14], rax (callback storage) | YES | EXP-103 |
| `0x804F6E510` | ThreadPool dispatch (WaitSema) | YES (blocks) | EXP-088 |
| `0x804F88AA0` | GC thread entry | YES | EXP-099 |

## Addresses NOT Reached

| Address | Function | Reached? | EXP |
|---------|----------|----------|-----|
| `0x804F6EC20` | work-submission (SignalSema caller) | **NO** (0 hits) | EXP-096 |
| `0x804F4571A` | call site 1 for work submission | **NO** (0 hits) | EXP-096 |
| `0x804F9FAAA` | call site 2 for work submission | **NO** (0 hits) | EXP-096 |
| `0x804FA14C8` | call site 3 for work submission | **NO** (0 hits) | EXP-096 |
| `0x804F52820` | callback function | **NO** (0 direct callers) | EXP-105 |

## Additional Finding: Callback Chain Is Independent from Work Submission

Static analysis confirms:
1. `0x804F6EC20` (work submission) does NOT reference the callback structure global (`0x808B54898`)
2. The 3 callers of `0x804F6EC20` (`0x804F456E0`, `0x804F9FA80`, `0x804FA1440`) do NOT reference the callback global
3. `0x804FA84E0` (callback invoker) does NOT directly call `0x804F6EC20`

**EXP-102..105 investigated the wrong subsystem.** The callback registration chain is a parallel IL2CPP mechanism, NOT the ThreadPool work-submission path. The work-submission function (`0x804F6EC20`) and its callers are still unreachable (EXP-096's original finding stands).

## Accepted/Rejected Claims

| Claim | Verdict | Evidence |
|-------|---------|----------|
| "ThreadPool is working" | **REJECTED** | Workers created but work submission (0x804F6EC20) NEVER reached. SignalSema NEVER called. All threads deadlock on WaitSema(0xA6). |
| "First frame is blocked by missing game data files" | **REJECTED** | Game data files ARE present and loaded correctly. The blocker is a ThreadPool synchronization deadlock (WaitSema(0xA6) never signaled). |

## Conclusion

**B) External claim REJECTED:** "ThreadPool initializes but work execution path is still blocked."

The ThreadPool creates workers but never submits work. The work-submission function (`0x804F6EC20`) is unreachable — its entire call chain is dead code (0 direct callers). The callback registration mechanism (EXP-098..105) works correctly but is an independent subsystem, not the work-submission path. The blocker is the absence of any code that invokes the work-submission function.
