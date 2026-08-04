#!/usr/bin/env python3
"""Append EXP-095 to YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md and YATZI_EXP_INDEX.md."""

import os
import sys

REPO = "/home/z/my-project/work/sharpemuT24"
HIST = os.path.join(REPO, "docs/diagnostics/YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md")
IDX = os.path.join(REPO, "docs/diagnostics/YATZI_EXP_INDEX.md")

HISTORY_SECTION = r"""

---

## EXP-095 (added 2026-08-01)

### EXP-095 — _ThreadPoolWaitCallback Lookup SUCCEEDS (rax=0x6007E64D0) — Deadlock Persists on WaitSema(0xA6)
- **Date:** 2026-08-01
- **Commit:** [see git log for EXP-095.md]
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied, EXP-095 tracer active
- **Path:** B (real metadata path)
- **Question:** What are the exact args and return value of the `_ThreadPoolWaitCallback` lookup at runtime, and what does the method table at `[context+0x30]` contain?
- **Hypothesis (from EXP-094):** The method table is incomplete or doesn't contain `_ThreadPoolWaitCallback`, causing the lookup to return NULL.
- **Tools/Logs:** New two-stage INT3 tracer (`_Exp095ThreadPoolLookupTracer.cs`): Stage 1 at call site `0x804F055D6` (captures args), Stage 2 at return site `0x804F055DB` (captures rax). Built SharpEmu with `dotnet publish`, ran with 120s timeout.
- **Finding:** The lookup **SUCCEEDED**. `rax = 0x6007E64D0` (non-NULL guest heap pointer to a valid `MethodInfo` structure). The method table at `[context+0x30]` IS populated and DOES contain `_ThreadPoolWaitCallback`. The MethodInfo at `0x6007E64D0` contains: `+0x00 = 0x60070B3A0` (Il2CppClass* matching rdi arg), `+0x10/+0x18/+0x20` = guest heap pointers (method name, signature, invoker). However, the deadlock **still occurs** — main thread blocks on `WaitSema(0xA6)` at `0x804F6E9EB` (ThreadPool dispatch), identical to EXP-092. The callback EXISTS but is never INVOKED because no work is submitted to the ThreadPool.
- **Root Cause:** NOT a missing callback — the lookup succeeds. The deadlock is caused by no work being submitted to the ThreadPool (re-confirms EXP-088/089).
- **Status:** CONFIRMED — corrects EXP-090 and EXP-094
- **Related:** EXP-040, EXP-085, EXP-088, EXP-089, EXP-090, EXP-091, EXP-092, EXP-093, EXP-094, EXP-096
- **Impact:** Major correction — the entire EXP-090..094 chain was based on the wrong assumption that `_ThreadPoolWaitCallback` lookup returns NULL. It does NOT. The lookup succeeds. The real blocker is that no work is submitted to the ThreadPool after the lookup. EXP-088/089's original classification was correct all along.

### Corrections
- **EXP-090 CORRECTED:** Claimed "_ThreadPoolWaitCallback lookup returns NULL → deadlock". Wrong: the lookup returns `0x6007E64D0` (non-NULL). The assumption was based on the hash table at `0x801EF7610` being empty, but EXP-094 proved the lookup doesn't use `0x801EF7610`, and EXP-095 proves the lookup succeeds.
- **EXP-094 CORRECTED:** Claimed "method table doesn't contain _ThreadPoolWaitCallback". Wrong: the method table DOES contain it, and the lookup succeeds.

### Tracer Bug (Minor)
`Exp095ReadCString` fails on guest heap addresses (`0x60...` range) — not identity-mapped to host addresses. The `method_name` string was read as `"??p"` instead of `"_ThreadPoolWaitCallback"`. The `namespace` string read correctly because it's in the PRX data segment (identity-mapped). This bug does NOT affect the key finding (rax was read from the register, not memory).

### Updated Current State (after EXP-095)
**Solved:** `_ThreadPoolWaitCallback` lookup traced at runtime. Lookup SUCCEEDS (rax=0x6007E64D0). Method info structure is valid and populated. Method table at `[context+0x30]` IS searchable. Deadlock is NOT caused by a missing callback.
**Still blocked:** Main thread blocks on `WaitSema(0xA6)` at `0x804F6E9EB` (ThreadPool dispatch). No work submitted to the ThreadPool after the lookup succeeds. The callback exists but is never invoked.
**Next debugging target:** Trace what the main thread does between `0x804F055DB` (lookup result stored) and `0x804F6E9EB` (WaitSema block). Look for a `QueueUserWorkItem` or similar work-submission call that should happen but doesn't. (EXP-096)
"""


INDEX_ROW = (
    "| 095 | 2026-08-01 | [see commit](https://github.com/Sh-TB/sharpemuT24/commit/master) | CONFIRMED — MAJOR CORRECTION | "
    "_ThreadPoolWaitCallback lookup SUCCEEDS at runtime! Two-stage INT3 tracer at 0x804F055D6 (call site) + 0x804F055DB (return site). "
    "rax=0x6007E64D0 (non-NULL MethodInfo*). Method table at [context+0x30] IS populated. "
    "Method info valid: +0x00=Il2CppClass*, +0x10/+0x18/+0x20=guest heap ptrs (name/sig/invoker). "
    "BUT deadlock persists: main thread blocks on WaitSema(0xA6) at 0x804F6E9EB (same as EXP-092). "
    "Callback EXISTS but never INVOKED — no work submitted to ThreadPool. "
    "Corrects EXP-090 (lookup does NOT return NULL) and EXP-094 (method table DOES contain the method). "
    "Re-confirms EXP-088/089: blocker is no work submitted, not missing callback. | "
    "EXP-040, EXP-085, EXP-088, EXP-089, EXP-090, EXP-091, EXP-092, EXP-093, EXP-094, EXP-096 |"
)


def main():
    # 1. Append to complete history
    with open(HIST, "r", encoding="utf-8") as f:
        hist_text = f.read()

    hist_text = hist_text.replace(
        "**Coverage: EXP-026 through EXP-094 (65 experiments)**",
        "**Coverage: EXP-026 through EXP-095 (66 experiments)**",
    )
    hist_text = hist_text.replace(
        "**Last updated: 2026-07-31 (EXP-094)**",
        "**Last updated: 2026-08-01 (EXP-095)**",
    )
    hist_text = hist_text.replace(
        "1. [EXP Timeline (EXP-026 through EXP-094)](#exp-timeline)",
        "1. [EXP Timeline (EXP-026 through EXP-095)](#exp-timeline)",
    )
    hist_text = hist_text.replace(
        "4. [Current State (after EXP-094)](#current-state)",
        "4. [Current State (after EXP-095)](#current-state)",
    )

    hist_text = hist_text.rstrip() + "\n" + HISTORY_SECTION.rstrip() + "\n"

    with open(HIST, "w", encoding="utf-8") as f:
        f.write(hist_text)
    print(f"Wrote {HIST} ({len(hist_text)} bytes)")

    # 2. Append to EXP index
    with open(IDX, "r", encoding="utf-8") as f:
        idx_text = f.read()

    exp094_row_marker = "| 094 | 2026-07-31 |"
    idx = idx_text.find(exp094_row_marker)
    if idx < 0:
        print("ERROR: EXP-094 row not found in index", file=sys.stderr)
        return 1
    end_of_094 = idx_text.find("\n", idx) + 1
    idx_text = idx_text[:end_of_094] + INDEX_ROW + "\n" + idx_text[end_of_094:]

    idx_text = idx_text.replace(
        "**Total EXPs:** 65 (EXP-026 through EXP-094)",
        "**Total EXPs:** 66 (EXP-026 through EXP-095)",
    )

    with open(IDX, "w", encoding="utf-8") as f:
        f.write(idx_text)
    print(f"Wrote {IDX} ({len(idx_text)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
