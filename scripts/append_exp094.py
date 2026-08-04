#!/usr/bin/env python3
"""Append EXP-094 to YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md and YATZI_EXP_INDEX.md."""

import os
import sys

REPO = "/home/z/my-project/work/sharpemuT24"
HIST = os.path.join(REPO, "docs/diagnostics/YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md")
IDX = os.path.join(REPO, "docs/diagnostics/YATZI_EXP_INDEX.md")

# We'll use a placeholder commit hash and fix it after commit (same pattern as EXP-093)
HISTORY_SECTION = r"""

---

## EXP-094 (added 2026-07-31)

### EXP-094 — Hash Table at 0x801EF7610 Confirmed RED HERRING — Lookup Uses [0x808923D88]
- **Date:** 2026-07-31
- **Commit:** [see git log for EXP-094.md]
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied
- **Path:** B (real metadata path)
- **Question:** What data structure does `il2cpp_class_get_method_from_name` (`0x804F21D70`) actually search, and is THAT structure populated?
- **Hypothesis (from EXP-093):** The function reads `[0x808923D88]`, not `0x801EF7610`.
- **Tools/Logs:** Static disassembly (capstone) of `0x804F21D70` and `0x804EEE8D0`. Fast byte-pattern scan of PRX and EBOOT executable segments for RIP-relative accesses to `0x808923D88`. Runtime evidence from EXP-092 log (EXP-058 context dump).
- **Finding:** `il2cpp_class_get_method_from_name` (`0x804F21D70`) is a **1-instruction trampoline** (`jmp 0x804EEE8D0`). The actual implementation at `0x804EEE8D0` reads `[0x808923D88]` as its context pointer (**5 reads**) and **NEVER reads `0x801EF7610`** (0 reads). The wrapper at `0x804F21DC0` also reads `0x808923D88` (6 times). This **definitively confirms** EXP-093's hypothesis: the hash table at `0x801EF7610` was a RED HERRING across EXP-040..092. The actual lookup structure at `[0x808923D88]` IS populated at runtime (value = `0x7F113CED77E0`, host-side pointer to a SharpEmu-managed context structure containing stack canary guards `0xC0DEC0DECAFEBA00`). The method table pointer at `[context+0x30]` is non-NULL (`0x55FBF4A4E3A0`), but `_ThreadPoolWaitCallback` lookup still returns NULL — the method table is either incomplete or contains wrong data.
- **Root Cause:** NOT "hash table empty" — the hash table at `0x801EF7610` is irrelevant. The method table at `[context+0x30]` (where context = `[0x808923D88]`) does not contain `_ThreadPoolWaitCallback`.
- **Status:** CONFIRMED — confirms EXP-093 hypothesis, corrects EXP-040..092 direction
- **Related:** EXP-040, EXP-053, EXP-083, EXP-090, EXP-091, EXP-092, EXP-093, EXP-095
- **Impact:** Major pivot — the entire EXP-040..092 hash table investigation was chasing the wrong structure. The actual lookup uses `[0x808923D88]` which IS populated. The new blocker is understanding why the method table at `[context+0x30]` doesn't contain `_ThreadPoolWaitCallback`.

### PRX-wide Writer Scan
- 50 PRX functions READ `0x808923D88` (verified first 10 — all reads, classic "load context pointer at function entry" pattern)
- 0 PRX functions WRITE `0x808923D88` via RIP-relative addressing
- 0 EBOOT accesses to `0x808923D88`
- The write happens via indirect pointer (register-computed address, not RIP-relative) — likely during PRX module_start or DT_INIT_ARRAY

### EXP-040..092 Retrospective
The investigation was NOT wasted:
- EXP-054/055 correctly identified `Il2CppCodeRegistration` and `Il2CppMetadataRegistration`
- EXP-092's DT_INIT_ARRAY fix was correct and necessary (module_start now runs)
- EXP-093 correctly identified `il2cpp_codegen_register` as a stub
- But the core assumption (hash table at `0x801EF7610` is the lookup target) was wrong

**Lesson:** Always verify by disassembly which structure a function ACTUALLY reads before investigating that structure (Golden Rule 8).

### Updated Current State (after EXP-094)
**Solved:** Actual lookup structure identified as `[0x808923D88]` (not `0x801EF7610`). Context structure IS populated. Method table pointer at `[context+0x30]` IS non-NULL.
**Still blocked:** `_ThreadPoolWaitCallback` lookup still returns NULL despite populated context. The method table may be incomplete or contain wrong data.
**Next debugging target:** Runtime trace the `_ThreadPoolWaitCallback` lookup at `0x804F055D6` to dump args, return value, and method table contents. (EXP-095)
"""


INDEX_ROW = (
    "| 094 | 2026-07-31 | [see commit](https://github.com/Sh-TB/sharpemuT24/commit/master) | CONFIRMED — RED HERRING PROVEN | "
    "il2cpp_class_get_method_from_name (0x804F21D70) is a 1-instruction trampoline to 0x804EEE8D0. "
    "Actual impl reads [0x808923D88] (5 reads), NEVER reads 0x801EF7610 (0 reads). "
    "Confirms EXP-093 hypothesis: hash table at 0x801EF7610 was RED HERRING across EXP-040..092. "
    "[0x808923D88] IS populated (host ptr 0x7F113CED77E0, contains stack canaries). "
    "[context+0x30] method table ptr IS non-NULL but _ThreadPoolWaitCallback lookup still returns NULL. "
    "50 PRX readers of 0x808923D88, 0 RIP-relative writers (write via indirect ptr). "
    "New blocker: method table incomplete or wrong data. | "
    "EXP-040, EXP-053, EXP-083, EXP-090, EXP-091, EXP-092, EXP-093, EXP-095 |"
)


def main():
    # 1. Append to complete history
    with open(HIST, "r", encoding="utf-8") as f:
        hist_text = f.read()

    hist_text = hist_text.replace(
        "**Coverage: EXP-026 through EXP-093 (64 experiments)**",
        "**Coverage: EXP-026 through EXP-094 (65 experiments)**",
    )
    hist_text = hist_text.replace(
        "**Last updated: 2026-07-31 (EXP-093)**",
        "**Last updated: 2026-07-31 (EXP-094)**",
    )
    hist_text = hist_text.replace(
        "1. [EXP Timeline (EXP-026 through EXP-093)](#exp-timeline)",
        "1. [EXP Timeline (EXP-026 through EXP-094)](#exp-timeline)",
    )
    hist_text = hist_text.replace(
        "4. [Current State (after EXP-093)](#current-state)",
        "4. [Current State (after EXP-094)](#current-state)",
    )

    hist_text = hist_text.rstrip() + "\n" + HISTORY_SECTION.rstrip() + "\n"

    with open(HIST, "w", encoding="utf-8") as f:
        f.write(hist_text)
    print(f"Wrote {HIST} ({len(hist_text)} bytes)")

    # 2. Append to EXP index
    with open(IDX, "r", encoding="utf-8") as f:
        idx_text = f.read()

    exp093_row_marker = "| 093 | 2026-07-31 |"
    idx = idx_text.find(exp093_row_marker)
    if idx < 0:
        print("ERROR: EXP-093 row not found in index", file=sys.stderr)
        return 1
    end_of_093 = idx_text.find("\n", idx) + 1
    idx_text = idx_text[:end_of_093] + INDEX_ROW + "\n" + idx_text[end_of_093:]

    idx_text = idx_text.replace(
        "**Total EXPs:** 64 (EXP-026 through EXP-093)",
        "**Total EXPs:** 65 (EXP-026 through EXP-094)",
    )

    with open(IDX, "w", encoding="utf-8") as f:
        f.write(idx_text)
    print(f"Wrote {IDX} ({len(idx_text)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
