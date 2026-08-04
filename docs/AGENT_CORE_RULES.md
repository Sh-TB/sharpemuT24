# SharpEmuT24 Agent Core Rules v1.0

**Purpose:** Permanent agent rules — read at the start of every session.
**Companion document:** `docs/SOP/SHARPEMU_DEBUG_PROTOCOL.md` (full SOP, read periodically).

---

## Golden Rule 1 — Evidence First

No decision based on guess. Before any fix:

```
Observation
↓
Evidence
↓
Hypothesis
↓
Experiment
↓
Root Cause
↓
Fix
↓
Verification
```

**Forbidden:**
```
Crash
↓
Guess
↓
Patch
```

---

## Golden Rule 2 — Golden Test Always Mandatory

Before AND after every change, run:

```
Golden Test:
  Game: Dreaming Sarah
  Title ID: PPSA02929
  Baseline commit: f83b6ea
  Baseline tag: golden-render-baseline (v0.0.9)
```

Required metrics:
```
Boot:               YES/NO
VulkanVideoPresenter: YES/NO
Framebuffer:        YES/NO
Real Frame:         YES/NO
Frame count:        N
Distinct colors:    N
```

If Golden Test regresses → **change is rejected, revert or fix immediately**. Even if another game improved.

---

## Golden Rule 3 — Every Improvement Must Be Backed By A Metric

Never say "better" / "improved" / "closer" without a number.

Required format:
```
Before:
  Instructions: 3481
  Crash: RIP 0x123

After:
  Instructions: 12800
  Crash: RIP 0x456
```

Or:
```
Flip calls:      2 → 57
Framebuffer:     0 bytes → first non-zero frame
```

---

## Golden Rule 4 — Investigate Suspicious Issues Immediately

If something suspicious appears during debug, do NOT defer it.

Example: NULL pointer found → immediately investigate:
- Who writes it?
- Who initializes it?
- When should it exist?
- Why is it NULL?

Do NOT just patch the crash.

---

## Golden Rule 5 — No New Features Mid Bug Investigation

When a game fails to run, FORBIDDEN:
- New features
- New refactors
- New optimizations

Required order:
```
Last Successful Execution Point
↓
Failure Point
↓
Root Cause
↓
Fix
```

Then features.

---

## Golden Rule 6 — Every Session Ends With Commit + GitHub Upload + Handoff Report

Every session MUST:
1. Commit
2. Push to GitHub
3. Generate a handoff report

Format (`CHANGELOG.md`):
```
Version:
Date:

Fixed:
Added:
Tests:
Golden Test:
Known Issues:
Next Step:
```

**GitHub upload is non-negotiable.** Local-only knowledge is unacceptable.

---

## 6-Rule Summary (always in agent prompt)

1. **Evidence First** — no guesses without tests.
2. **Golden Test before AND after every change** — Dreaming Sarah must not regress.
3. **Every improvement needs a metric** — number, log, frame, instruction count.
4. **Investigate suspicious items immediately** — NULL, wait, missing resource, import.
5. **Bug fix before feature** — no new features during crash investigation.
6. **Every session: commit + GitHub upload + handoff report.**
