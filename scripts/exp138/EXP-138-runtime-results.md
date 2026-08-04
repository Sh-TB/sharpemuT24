# EXP-138 Runtime Validation

**Date:** 2026-08-04
**Commit:** `9cef960` (EXP-138 patch) / `feeb6c9` (latest — docs English-only)

---

## Environment

| Check | Result |
|-------|--------|
| `dotnet --version` | `command not found` (exit 127) |
| `which dotnet` | not found (exit 1) |
| `/usr/share/dotnet/` | does not exist |
| `/usr/lib/dotnet/` | does not exist |
| `/opt/dotnet/` | does not exist |
| `~/.dotnet/` | does not exist |
| Filesystem search (`find / -maxdepth 5 -name dotnet -type f`) | 0 results |
| `dpkg -l \| grep dotnet` | 0 results |
| `apt list --installed \| grep dotnet` | 0 results |
| `snap list \| grep dotnet` | 0 results |

**Conclusion:** No dotnet SDK installed in sandbox. Cannot build SharpEmu. Cannot run any runtime test.

---

## Build

**Status:** BLOCKED

**Reason:** No dotnet SDK in sandbox.

**Evidence:**
```
$ dotnet --version
bash: dotnet: command not found

$ which dotnet
(exit code 1)

$ find / -maxdepth 5 -name "dotnet" -type f
(no output)
```

---

## Dreaming Sarah

**Status:** BLOCKED

**Reason:** Cannot build SharpEmu without dotnet SDK. No built binary exists to run.

**Required command (cannot execute):**
```bash
SHARPEMU_HEADLESS=1 SHARPEMU_CAPTURE=1 ./SharpEmu.CLI --game dreaming-sarah --timeout 30
```

**Expected PASS criteria (not verifiable):**
- Frames >= 138
- Colors >= 167
- Crash = 0

---

## Arise

**Status:** BLOCKED

**Reason:** Cannot build SharpEmu without dotnet SDK. No built binary exists to run.

**Required command (cannot execute):**
```bash
./SharpEmu.CLI --game arise --timeout 30
```

**Expected check items (not verifiable):**
- No GPU memory fault
- No new unresolved NID
- Framebuffer valid

---

## Yatzi

**Status:** BLOCKED

**Reason:** Cannot build SharpEmu without dotnet SDK. No built binary exists to run. Also gated on Dreaming Sarah + Arise PASS (which are also BLOCKED).

**Required command (cannot execute):**
```bash
SHARPEMU_SEMA_FAST_PATH=0 ./SharpEmu.CLI --game yatzi --timeout 60
```

**Expected evidence collection (cannot execute):**
```bash
grep "RESOLVER-TRACE" yatzi-exp138.log
grep "RAX=0x0000000000000000" yatzi-exp138.log | wc -l
grep "sema.signal handle=0x81" yatzi-exp138.log
grep "sema.signal handle=0x84" yatzi-exp138.log
```

**Expected result (not verifiable):**
- Before: NULL resolver = 232
- After EXP-138: NULL resolver should decrease significantly or become zero

---

## Evidence

### Static Verification (completed in previous session)

**Status:** PASS

| Check | Result |
|-------|--------|
| `CallNativeEntry` returns `ulong` | PASS — line 879 |
| Delegate signature `(delegate* unmanaged[Cdecl]<ulong>)` | PASS — line 882 |
| `ExecuteGuestThreadEntry` writes `context.Rax` | PASS — line 5043 |
| `ExecuteGuestContinuationEntry` writes `context.Rax` | PASS — line 5216 |
| Entry path `num6` is `ulong` | PASS — line 5506 |
| `NativeWorker.cs` `RunGuestEntryStub` returns `ulong` | PASS — line 59 |
| No remaining `int CallNativeEntry` patterns | PASS — grep returns 0 |
| All `CallNativeEntry` callers updated | PASS — 4 call sites verified |

### Runtime Verification (this session)

**Status:** BLOCKED

No runtime tests could be executed. Evidence:
- `dotnet: command not found` (verified 6 different ways — see Environment table above)
- No built `SharpEmu.CLI` binary exists in sandbox
- No game dumps accessible at expected runtime paths

---

## Final Verdict

**EXP-138 Runtime Validation: BLOCKED**

| Component | Status |
|-----------|--------|
| Patch applied | ✅ COMPLETE (commit `9cef960`) |
| Static verification | ✅ PASS (all 7 checks) |
| Build | ❌ BLOCKED (no dotnet SDK) |
| Dreaming Sarah Golden Test | ❌ BLOCKED (no build) |
| Arise Regression | ❌ BLOCKED (no build) |
| Yatzi FAST_PATH=0 | ❌ BLOCKED (no build + no regression gate) |

**The patch is applied to source code and statically verified. All runtime validation is BLOCKED because the sandbox has no dotnet SDK.**

**Required maintainer action:**
1. `git pull origin main`
2. `dotnet build -c Release`
3. Run Dreaming Sarah Golden Test (Frames >= 138, Colors >= 167, Crash = 0)
4. Run Arise Regression (no GPU fault, no new NID)
5. If both PASS: run Yatzi with `SHARPEMU_SEMA_FAST_PATH=0`
6. Collect evidence (grep commands documented above)
7. Update this file with actual results and commit

**If Dreaming Sarah or Arise regresses:**
- `git revert 9cef960` immediately
- Report regression with metrics

**If Yatzi still deadlocks after EXP-138:**
- Proceed to EXP-139 (arch_init_gc HLE stub)
- Then EXP-140 (Unity Job System icall HLE stubs) if needed
