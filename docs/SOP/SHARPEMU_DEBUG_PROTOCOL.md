# SharpEmuT24 Universal Debug SOP v2.0

**Purpose:** Full Standard Operating Procedure. Read periodically (every few sessions) or when agent starts drifting.
**Companion document:** `docs/AGENT_CORE_RULES.md` (6 core rules, read every session).

---

## Rule 1 — Verify Input First

Before debug, verify:
```
Files
Size
Count
Hash
Version
Commit
Environment
```

For critical files (`eboot.bin`, `*.prx`, `global-metadata.dat`, `Il2cppUserAssemblies.prx`), record:
```
File:
Path:
Size:
SHA256:
```

If a critical file is missing → `STATUS: BLOCKED`. Do NOT analyze crashes.

---

## Rule 2 — Always Build A Timeline

For every game:
```
Boot
↓
Loader
↓
PRX
↓
TLS
↓
Imports
↓
Guest Code
↓
Engine Init
↓
IL2CPP
↓
Assets
↓
Graphics Init
↓
Draw
↓
Submit
↓
Framebuffer
↓
Present
```

Identify: `Reached State X`, `Failed State X+1`.

---

## Rule 3 — Layer Debug Order

Always debug bottom-up:
```
Layer 0: Input / Files
↓
Layer 1: Loader
↓
Layer 2: Memory
↓
Layer 3: Imports
↓
Layer 4: Runtime
↓
Layer 5: Engine
↓
Layer 6: Graphics
↓
Layer 7: Present
```

A lower layer must be confirmed before debugging a higher layer.

---

## Rule 4 — NULL Pointer Investigation

No NULL is investigated in isolation. For every NULL:
```
Address
Owner Structure
All Writers
Expected Writer
Initialization Order
Dependent Fields
Caller
Thread
```

Goal: find the **missing initialization mechanism**, NOT silence the crash.

---

## Rule 5 — Runtime Is The Ground Truth

Static analysis only generates hypotheses.

If static says "function exists" but runtime says "0 callers", the function is NOT active. Runtime wins.

---

## Rule 6 — Experiment Format

Every EXP:
```
EXP ID:
Hypothesis:
Test:
Expected:
Actual:
Conclusion:
Confidence:
```

---

## Rule 7 — Closed Paths

Every rejected path is recorded. Example:
```
EXP-076
Theory: GPU blocker
Evidence: GPU initialized correctly
Status: CLOSED
```

Do NOT repeat without new evidence.

---

## Rule 8 — Dependency Architecture

```
Contracts
↓
Core
↓
Libraries / HLE / GPU
↓
Diagnostics
↓
CLI
```

Forbidden: `Core → Diagnostics → Core` (circular).

---

## Rule 9 — Contract First

Every new API:
```
Interface
↓
Contract Test
↓
Implementation
↓
Integration
```

---

## Rule 10 — Fork Safety

No big changes directly on Core. Use:
- Adapter
- Compatibility Layer
- Interface

Goal: upstream updates must not blow up the project.

---

## Rule 11 — Regression

Every fix requires:
```
Golden Test
+
Regression Test
+
Runtime Test
```

---

## Rule 12 — Real Success Criteria

Real success is NOT:
- Build OK
- Boot OK

Real success IS:
```
Game
↓
Engine Init
↓
Render Commands
↓
Framebuffer
↓
Real Frame
```

---

## Rule 13 — No Game-Specific Hacks

Forbidden:
```csharp
if (GameId == "XXXX") { ... }
```

Fixes must be:
- Generic
- System-level
- Reusable

---

## Rule 14 — Investigation Memory

At session start, read:
```
.agent_state/current_state.md
.agent_state/known_facts.md
.agent_state/closed_paths.md
.agent_state/experiment_history.json
.agent_state/next_actions.md
```

Never start from zero.

---

## Rule 15 — Final Report

Every investigation produces:
```
facts.md
timeline.md
callgraph.md
memory.md
imports.md
resolver.md
rootcause.md
next_steps.md
```

---

## Investigation Pipeline (per EXP)

```
1. Build EXP-NNN
        ↓
2. Dreaming Sarah Golden Test (mandatory regression gate)
        ↓
3. Arise Regression (secondary regression gate)
        ↓
4. Target game (e.g., Yatzi) FAST_PATH=0
        ↓
5. Collect evidence:
   - RAX trace
   - NULL count
   - resolver table
   - semaphore lifecycle
   - AGC counters
        ↓
6. EXP-NNN-results.md
```

If Golden Test or Arise regresses → STOP. Do not continue.

---

## Final Success Condition

Not just "no crash". The real success condition:

```
Boot
+
Unity Init
+
Render Command
+
Framebuffer Data
+
Real Frame Present
```
