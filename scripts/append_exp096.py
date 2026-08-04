#!/usr/bin/env python3
"""Append EXP-096 to YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md and YATZI_EXP_INDEX.md."""

import os
import sys

REPO = "/home/z/my-project/work/sharpemuT24"
HIST = os.path.join(REPO, "docs/diagnostics/YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md")
IDX = os.path.join(REPO, "docs/diagnostics/YATZI_EXP_INDEX.md")

HISTORY_SECTION = r"""

---

## EXP-096 (added 2026-08-01)

### EXP-096 — Work Submission Function NEVER Reached — Entire Call Chain Is Dead Code
- **Date:** 2026-08-01
- **Commit:** [see git log for EXP-096.md]
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied, EXP-095 + EXP-096 tracers active
- **Path:** B (real metadata path)
- **Question:** What code path should submit work to the ThreadPool after the `_ThreadPoolWaitCallback` lookup, and why doesn't it execute?
- **Hypothesis:** The work-submission function (`0x804F6EC20`) should be called during IL2CPP init to queue work. Deadlock occurs because it's never called (Case A), or called but skips (Case B), or submits but SignalSema fails (Case C).
- **Tools/Logs:** Static disassembly (capstone) of `0x804F6EC20` and its callers. PRX/EBOOT-wide `E8 rel32` scan for all callers. New INT3 tracer (`_Exp096WorkSubmissionTracer.cs`) at all 3 call sites. Runtime run with 120s timeout.
- **Finding:** **Case A confirmed.** The work-submission function (`0x804F6EC20`) is NEVER reached at runtime. All 3 call sites (`0x804F4571A`, `0x804F9FAAA`, `0x804FA14C8`) had ZERO INT3 hits. Static analysis proves the entire call chain is dead code: the containing functions (`0x804F456E0`, `0x804F9FA80`, `0x804FA1440`) have zero direct callers, and the one caller (`0x804FA2089` in `0x804FA1FE0`) also has zero direct callers. The work-submission path is only reachable via indirect function pointers (vtables, delegates, runtime callbacks) that are never set up.
- **Root Cause:** The work-submission call chain is dead code because the indirect function pointers that should reach it are never registered. SharpEmu likely doesn't implement the HLE function that performs this registration.
- **Status:** CONFIRMED — Case A (work submission never reached)
- **Related:** EXP-088, EXP-089, EXP-090, EXP-092, EXP-095, EXP-097
- **Impact:** Root cause of the ThreadPool deadlock identified at the call-chain level. The callback EXISTS (EXP-095) but the code that should INVOKE it is dead code. The fix must identify what indirect registration mechanism should set up the call chain and implement the missing HLE function.

### Work-Submission Call Chain (All Dead Code)

```
0x804F6EC20 (SignalSema(0xA6) caller — work submission)
  ← 0x804F4571A in 0x804F456E0  (0 direct callers — DEAD)
  ← 0x804F9FAAA in 0x804F9FA80  (1 caller: 0x804FA2089 in 0x804FA1FE0)
  ← 0x804FA14C8 in 0x804FA1440  (0 direct callers — DEAD)

0x804FA1FE0 (caller of 0x804F9FA80)
  ← 0 direct callers — DEAD
```

### Updated Current State (after EXP-096)
**Solved:** Work-submission function located (`0x804F6EC20`). 3 call sites identified. Runtime proof: NONE reached (Case A). Static proof: entire call chain is dead code (0 direct callers). Root cause: indirect function pointers never set up.
**Still blocked:** The indirect registration mechanism that should set up the call chain is not identified. SharpEmu likely doesn't implement the HLE function that performs this registration.
**Next debugging target:** Search PRX data segment for function pointers to the dead-code functions. Check IL2CPP registration data. Find what should populate the function pointer. (EXP-097)
"""


INDEX_ROW = (
    "| 096 | 2026-08-01 | [see commit](https://github.com/Sh-TB/sharpemuT24/commit/master) | CONFIRMED — CASE A (ROOT CAUSE) | "
    "Work-submission function (0x804F6EC20, calls SignalSema(0xA6)) NEVER reached. "
    "INT3 at all 3 call sites (0x804F4571A, 0x804F9FAAA, 0x804FA14C8) — ZERO hits. "
    "Static proof: containing functions (0x804F456E0, 0x804F9FA80, 0x804FA1440) have 0 direct callers. "
    "Caller's caller (0x804FA1FE0) also 0 callers. ENTIRE call chain is dead code — "
    "only reachable via indirect function pointers (vtables/delegates/callbacks) never set up. "
    "Callback EXISTS (EXP-095) but code that should INVOKE it is dead. "
    "Root cause: missing HLE function for indirect registration. | "
    "EXP-088, EXP-089, EXP-090, EXP-092, EXP-095, EXP-097 |"
)


def main():
    # 1. Append to complete history
    with open(HIST, "r", encoding="utf-8") as f:
        hist_text = f.read()

    hist_text = hist_text.replace(
        "**Coverage: EXP-026 through EXP-095 (66 experiments)**",
        "**Coverage: EXP-026 through EXP-096 (67 experiments)**",
    )
    hist_text = hist_text.replace(
        "**Last updated: 2026-08-01 (EXP-095)**",
        "**Last updated: 2026-08-01 (EXP-096)**",
    )
    hist_text = hist_text.replace(
        "1. [EXP Timeline (EXP-026 through EXP-095)](#exp-timeline)",
        "1. [EXP Timeline (EXP-026 through EXP-096)](#exp-timeline)",
    )
    hist_text = hist_text.replace(
        "4. [Current State (after EXP-095)](#current-state)",
        "4. [Current State (after EXP-096)](#current-state)",
    )

    hist_text = hist_text.rstrip() + "\n" + HISTORY_SECTION.rstrip() + "\n"

    with open(HIST, "w", encoding="utf-8") as f:
        f.write(hist_text)
    print(f"Wrote {HIST} ({len(hist_text)} bytes)")

    # 2. Append to EXP index
    with open(IDX, "r", encoding="utf-8") as f:
        idx_text = f.read()

    exp095_row_marker = "| 095 | 2026-08-01 |"
    idx = idx_text.find(exp095_row_marker)
    if idx < 0:
        print("ERROR: EXP-095 row not found in index", file=sys.stderr)
        return 1
    end_of_095 = idx_text.find("\n", idx) + 1
    idx_text = idx_text[:end_of_095] + INDEX_ROW + "\n" + idx_text[end_of_095:]

    idx_text = idx_text.replace(
        "**Total EXPs:** 66 (EXP-026 through EXP-095)",
        "**Total EXPs:** 67 (EXP-026 through EXP-096)",
    )

    with open(IDX, "w", encoding="utf-8") as f:
        f.write(idx_text)
    print(f"Wrote {IDX} ({len(idx_text)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
