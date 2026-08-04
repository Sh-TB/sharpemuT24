#!/usr/bin/env python3
"""Append EXP-097 to YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md and YATZI_EXP_INDEX.md."""

import os
import sys

REPO = "/home/z/my-project/work/sharpemuT24"
HIST = os.path.join(REPO, "docs/diagnostics/YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md")
IDX = os.path.join(REPO, "docs/diagnostics/YATZI_EXP_INDEX.md")

HISTORY_SECTION = r"""

---

## EXP-097 (added 2026-08-01)

### EXP-097 — Dead-Code Functions Not Registered Anywhere — Self-Registering Function 0x804FA1FE0 Never Called
- **Date:** 2026-08-01
- **Commit:** [see git log for EXP-097.md]
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, DT_INIT_ARRAY fix (EXP-092) applied, EXP-095 + EXP-096 + EXP-097 tracers active
- **Path:** B (real metadata path)
- **Question:** What indirect call mechanism should reach the work-submission function `0x804F6EC20`, and why is the function pointer never set?
- **Hypothesis (from user):** The dead-code functions are reachable via indirect function pointers (vtable slots, delegate targets, callback tables) that are either static relocations or runtime-written values. Find the stored function pointer and determine if SharpEmu populates it.
- **Tools/Logs:** Exhived static search of PRX + EBOOT for stored qwords (byte-level scan). LEA instruction scan. movabs scan. New runtime tracer (`_Exp097FuncPtrGlobalTracer.cs`) that dumps 7 function pointer globals + 3 IL2CPP globals + once-init guard from the EXP-095 return-site handler.
- **Finding:** The 5 dead-code function addresses are **NOT registered as function pointers anywhere** — 0 stored qwords in data segments, 0 LEA instructions (except self-referential `0x804FA1FE0`), 0 movabs immediates. The 3 IL2CPP registration globals ARE populated at runtime but don't contain the dead-code addresses. The 7 runtime-set function pointer globals (called via `call [rip+disp]`) ARE populated but point to different functions (`0x804F09550`, `0x804FBF820`, etc.). The once-init guard `[0x808B418D8]` = `0xFFFFFFFFFFFFFFFF` (sentinel — never cleared). The self-registering function `0x804FA1FE0` (loads its own address via `lea rsi, [self]` and tail-jumps to `0x804F889D0`) is itself dead code with 0 callers.
- **Root Cause:** The registration mechanism that should set up the work-submission call chain is itself dead code. The self-registering function `0x804FA1FE0` was supposed to register the function pointers by calling `0x804F889D0`, but `0x804FA1FE0` has 0 callers and is never executed.
- **Status:** CONFIRMED — dead-code functions not registered anywhere
- **Related:** EXP-088, EXP-089, EXP-095, EXP-096, EXP-098
- **Impact:** The investigation traced the exact address (as the user instructed) rather than pattern-guessing. The root cause is now precisely identified: the self-registering function `0x804FA1FE0` is the missing link — it should register the work-submission path but is never called. Next step is to find what should call `0x804FA1FE0`.

### Self-Registering Function Pattern
```asm
0x804FA210F  lea  rsi, [rip+...]  ; -> 0x804FA1FE0 (its own address!)
0x804FA2127  jmp  0x804F889D0     ; tail jump to registration function
```

### Updated Current State (after EXP-097)
**Solved:** 5 dead-code functions NOT registered anywhere (0 stored qwords, 0 LEA except self-ref, 0 movabs). 7 runtime-set function pointer globals all populated but point elsewhere. 3 IL2CPP globals populated but don't contain dead-code addresses. Once-init guard never cleared. Self-registering function `0x804FA1FE0` identified as the registration entry point but is itself dead code.
**Still blocked:** What should call `0x804FA1FE0`? Is it in the init_array? Is it an IL2CPP icall? Is it called from EBOOT?
**Next debugging target:** Check the PRX's init_array at runtime for `0x804FA1FE0`. Trace the 25 call sites in real_init. (EXP-098)
"""


INDEX_ROW = (
    "| 097 | 2026-08-01 | [see commit](https://github.com/Sh-TB/sharpemuT24/commit/master) | CONFIRMED | "
    "5 dead-code functions NOT registered anywhere: 0 stored qwords in data segments, "
    "0 LEA (except self-ref 0x804FA1FE0), 0 movabs. 3 IL2CPP globals populated but no match. "
    "7 runtime-set func ptr globals populated but point elsewhere (0x804F09550, 0x804FBF820, etc.). "
    "Once-init guard [0x808B418D8]=0xFFFF... (never cleared). "
    "Self-registering func 0x804FA1FE0 (lea rsi,[self]; jmp 0x804F889D0) is itself dead code (0 callers). "
    "Root cause: registration mechanism is dead code. | "
    "EXP-088, EXP-089, EXP-095, EXP-096, EXP-098 |"
)


def main():
    # 1. Append to complete history
    with open(HIST, "r", encoding="utf-8") as f:
        hist_text = f.read()

    hist_text = hist_text.replace(
        "**Coverage: EXP-026 through EXP-096 (67 experiments)**",
        "**Coverage: EXP-026 through EXP-097 (68 experiments)**",
    )
    hist_text = hist_text.replace(
        "**Last updated: 2026-08-01 (EXP-096)**",
        "**Last updated: 2026-08-01 (EXP-097)**",
    )
    hist_text = hist_text.replace(
        "1. [EXP Timeline (EXP-026 through EXP-096)](#exp-timeline)",
        "1. [EXP Timeline (EXP-026 through EXP-097)](#exp-timeline)",
    )
    hist_text = hist_text.replace(
        "4. [Current State (after EXP-096)](#current-state)",
        "4. [Current State (after EXP-097)](#current-state)",
    )

    hist_text = hist_text.rstrip() + "\n" + HISTORY_SECTION.rstrip() + "\n"

    with open(HIST, "w", encoding="utf-8") as f:
        f.write(hist_text)
    print(f"Wrote {HIST} ({len(hist_text)} bytes)")

    # 2. Append to EXP index
    with open(IDX, "r", encoding="utf-8") as f:
        idx_text = f.read()

    exp096_row_marker = "| 096 | 2026-08-01 |"
    idx = idx_text.find(exp096_row_marker)
    if idx < 0:
        print("ERROR: EXP-096 row not found in index", file=sys.stderr)
        return 1
    end_of_096 = idx_text.find("\n", idx) + 1
    idx_text = idx_text[:end_of_096] + INDEX_ROW + "\n" + idx_text[end_of_096:]

    idx_text = idx_text.replace(
        "**Total EXPs:** 67 (EXP-026 through EXP-096)",
        "**Total EXPs:** 68 (EXP-026 through EXP-097)",
    )

    with open(IDX, "w", encoding="utf-8") as f:
        f.write(idx_text)
    print(f"Wrote {IDX} ({len(idx_text)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
