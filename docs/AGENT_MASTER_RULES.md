# SharpEmuT24 Agent Master Rules

**Purpose:** The single permanent file every agent MUST read at the start of every session, before any code change, debug, test, or architecture decision.

**Companion documents:**
- `docs/AGENT_CORE_RULES.md` — 6 Golden Rules (detailed version)
- `docs/SOP/SHARPEMU_DEBUG_PROTOCOL.md` — Full 15-rule SOP
- `.agent_state/` — Investigation memory (current_state, known_facts, closed_paths, experiment_history, next_actions)

---

## Part 1 — Core Rules (must always be read and followed)

This file must be read before any code change, debug, test, or architecture decision.

### 6 Golden Rules (permanent golden rules)

#### Rule 1 — Golden Test First (most important rule)

Before any change:
- Existing Golden Tests must be checked.
- Any game that has previously PASSed is no longer a hypothesis; it is a confirmed fact.
- Something that has already run must not be reported again as a "possibility."

Example — Dreaming Sarah:

Wrong:
```
Execution probability 70-80%
```

Correct:
```
Dreaming Sarah = CONFIRMED GOLDEN BASELINE
```

Every change must check:
- Has the Golden Test been broken?
- Has previous behavior been preserved?

#### Rule 2 — GitHub Commit Required

No work is complete unless:
1. Changes are committed.
2. Changes are pushed.
3. GitHub URL is provided.
4. Commit result is reported.

Report format:
```
Commit:
Hash:
Files Changed:
GitHub URL:
HTTP Status:
```

If push fails:
- The exact reason must be written.

#### Rule 3 — Runtime Test Over Static Guess

No result may be declared without a real test.

Three result levels:
- **PASS** — test was executed and succeeded.
- **FAIL** — test was executed and failed.
- **BLOCKED** — test could not be executed.

Example:

Wrong:
```
The problem is probably solved
```

Correct:
```
Static verification PASS
Runtime validation BLOCKED (missing dotnet SDK)
```

#### Rule 4 — Suspicious Issue = Immediate Test

If a suspicious item is observed at any stage:
- It must not just be logged.
- Immediately:
  1. Form a hypothesis.
  2. Write a minimal test.
  3. Record the result.

Cycle:
```
Observation
 ↓
Hypothesis
 ↓
Minimal Test
 ↓
Evidence
 ↓
Decision
```

#### Rule 5 — Existing Diagnostics First

Before building new debug code, existing systems must be checked.

Use first:
- DebugIntelligenceEngine
- Guest Call Stack
- HLE Debugger
- Missing Function Tracker
- Memory Fault Analyzer
- Resolver Trace
- Frame Capture
- Crash Analyzer

Rule: **New Debug Code = Last Option**

#### Rule 6 — No Re-investigation of Closed Paths

Paths that have been previously investigated and rejected:
- Must not be re-investigated unless there is new evidence.

Before starting an investigation, read:
- `.agent_state/closed_paths.md`
- `.agent_state/known_facts.md`
- `.agent_state/experiment_history.json`

---

## Part 2 — Periodic Rules (to be reviewed every few sessions)

The agent should re-read this section every few sessions.

### SHARPEMU_DEBUG_PROTOCOL

#### 1. Evidence First
Every claim must have one of:
- Log
- Test result
- Code reference
- Commit

#### 2. Experiment Numbering
Every investigation: `EXP-XXX`

Structure:
```
EXP-138
 ├── Hypothesis
 ├── Change
 ├── Test
 ├── Result
 └── Verdict
```

#### 3. Smallest Possible Change
A patch must:
- Be limited in scope.
- Be revertible.
- Test only one hypothesis.

#### 4. Regression Order
Test order is always:
1. Golden Game (Dreaming Sarah)
2. Known Working Games (Arise)
3. Regression Games
4. New Target (Yatzi)

#### 5. Dreaming Sarah Rule
- Status: **CONFIRMED WORKING**
- Duty: after every change, run for regression check.
- Check items: Frames, Colors, Crash, Framebuffer, Resolver

#### 6. Arise Rule
- Goal: check GPU Memory Regression
- Check: GPU mapping, Memory fault, NID resolve, Framebuffer

#### 7. Yatzi Rule
- Yatzi only after Dreaming Sarah and Arise PASS.
- Check: Resolver, IL2CPP, Semaphore, Rendering Pipeline

#### 8. Build Requirement
Before runtime:
```bash
dotnet build -c Release
```
If build fails: no runtime conclusion may be drawn.

#### 9. Sandbox Limitation Reporting
If the environment is limited (e.g., dotnet SDK missing, No GPU, No Vulkan device):
- This must be clearly stated.

#### 10. Static Verification ≠ Runtime Validation
- Static: code looks correct
- Runtime: actual execution works

These two must be reported separately.

---

## EXP-138 Current Investigation State

### Patch Applied

```
Commit: 9cef960
Title:  EXP-138: Apply TryCallGuestFunction RAX propagation fix
```

### Root Cause Found

**Problem:** Guest callback return value lost

**Before:**
```
Host RAX
 ↓
lost
 ↓
context.Rax = 0
 ↓
Resolver returns NULL
 ↓
IL2CPP fails
 ↓
Unity Job System deadlock
```

**After:**
```
nativeReturn
 ↓
context.Rax
 ↓
Guest receives real value
```

### EXP-138 Changes

#### DirectExecutionBackend.cs

| Change | What | Goal |
|--------|------|------|
| 1 | `CallNativeEntry`: `int` → `ulong` | Preserve 64-bit pointers |
| 2 | `ExecuteGuestThreadEntry`: added `context.Rax = nativeReturn` | Write-back host RAX |
| 3 | `ExecuteGuestContinuationEntry`: added `context.Rax = nativeReturn` | Same write-back for continuation |
| 4 | `num6`: `int` → `ulong` | Prevent pointer truncation |
| 5 | Format: `X8` → `X16` | Display full address |

#### NativeWorker.cs

| Change | What | Goal |
|--------|------|------|
| 6 | `RunGuestEntryStub`: `int` → `ulong` | consistency |

### Validation Status

#### Static Verification

**Status:** ✅ PASS

| Item | Result |
|------|--------|
| CallNativeEntry ulong | PASS |
| Delegate signature | PASS |
| RAX propagation | PASS |
| Thread entry update | PASS |
| Continuation entry update | PASS |
| Pointer width | PASS |
| grep validation | PASS |

#### Runtime Validation

**Status:** ❌ BLOCKED

**Reason:** No dotnet SDK

**Problem:**
```
dotnet: command not found
```

---

## Required Maintainer Test

### Step 1 — Build

```bash
git pull origin main
dotnet build -c Release
```

### Step 2 — Dreaming Sarah Golden Test (mandatory)

```bash
SHARPEMU_HEADLESS=1 \
SHARPEMU_CAPTURE=1 \
./SharpEmu.CLI --game dreaming-sarah --timeout 30
```

**PASS:**
- Frames >= 138
- Colors >= 167
- Crash = 0

### Step 3 — Arise Regression

```bash
./SharpEmu.CLI --game arise --timeout 30
```

**Check:**
- No GPU memory fault
- No new unresolved NID
- Framebuffer valid

### Step 4 — Yatzi (only after previous PASS)

```bash
SHARPEMU_SEMA_FAST_PATH=0 \
./SharpEmu.CLI --game yatzi --timeout 60
```

**Collect:**
```bash
grep "RESOLVER-TRACE" yatzi-exp138.log
grep "RAX=0x0000000000000000" yatzi-exp138.log | wc -l
grep "sema.signal handle=0x81" yatzi-exp138.log
grep "sema.signal handle=0x84" yatzi-exp138.log
```

**Expected:**
- Before: NULL resolver = 232
- After: NULL resolver = 0

---

## Commit Documentation

```
Commit: 36a91fa
Title:  docs: Add Agent Core Rules + Universal Debug SOP + .agent_state
```

**Files:**
- `docs/AGENT_CORE_RULES.md`
- `docs/SOP/SHARPEMU_DEBUG_PROTOCOL.md`
- `.agent_state/current_state.md`
- `.agent_state/known_facts.md`
- `.agent_state/closed_paths.md`
- `.agent_state/experiment_history.json`
- `.agent_state/next_actions.md`

---

## Overall Project Status

### Estimated Progress

| Area | Status |
|------|--------|
| Root Cause Investigation | 90% |
| Diagnostics Infrastructure | 70% |
| Documentation | 100% |
| EXP-138 Patch | 100% |
| Runtime Validation | 0% (Blocked) |
| Yatzi Resolution | Pending |

### Next Real Step

Do not go back to EXP-0 through EXP-135.

**Next step:**
```
EXP-138 Runtime Validation
        ↓
Dreaming Sarah
        ↓
Arise
        ↓
Yatzi
        ↓
EXP-139 if required
```

---

## 6-Rule Quick Reference (always in agent prompt)

1. **Golden Test First** — Dreaming Sarah = CONFIRMED, not "70-80% probable".
2. **GitHub Commit Required** — no work is done until pushed + URL provided.
3. **Runtime Test Over Static Guess** — PASS / FAIL / BLOCKED, never "probably".
4. **Suspicious Issue = Immediate Test** — observe → hypothesize → test → decide.
5. **Existing Diagnostics First** — new debug code is last option.
6. **No Re-investigation of Closed Paths** — read `.agent_state/closed_paths.md` first.
