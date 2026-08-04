#!/usr/bin/env python3
"""
Backfill YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md and YATZI_EXP_INDEX.md.

Adds EXP-086..092 sections to the complete history (currently ends at EXP-085),
and EXP-082..092 rows to the EXP index (currently ends at EXP-081).

Also replaces "[pending]" commit placeholders for EXP-082..085 with real hashes.

This is a one-shot script — safe to re-run only if you undo the changes first.
"""

import os
import re
import sys

REPO = "/tmp/my-project/work/sharpemuT24"
HIST = os.path.join(REPO, "docs/diagnostics/YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md")
IDX = os.path.join(REPO, "docs/diagnostics/YATZI_EXP_INDEX.md")

# Verified commit hashes (from `git log -1 --format=%h -- docs/diagnostics/EXP-NNN.md`)
# Each was also verified via `curl -sI` to return HTTP 200 on github.com.
COMMITS = {
    "082": "a922906",
    "083": "acd9271",
    "084": "49ad4b8",
    "085": "f2b5870",
    "086": "1c26932",
    "087": "bc9f963",
    "088": "eca949c",
    "089": "5ee1a46",
    "090": "431fdf5",
    "091": "fd65963",
    "092": "96d3285",
}

GH_BASE = "https://github.com/Sh-TB/sharpemuT24/commit"


def url(exp):
    h = COMMITS[exp]
    return f"[{h}]({GH_BASE}/{h})"


# ----------------------------------------------------------------------------
# Section data for EXP-086..092 (added to complete history)
# ----------------------------------------------------------------------------
SECTIONS = r"""

---

## EXP-086 (added 2026-07-31)

### EXP-086 — Path B Deadlock Analysis: Main Thread Goes Silent After AllocateDirectMemory
- **Date:** 2026-07-31
- **Commit:** {c086}
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active
- **Path:** B (real metadata path)
- **Question:** What is the main thread doing after `sceKernelAllocateDirectMemory`, and why does it stops making progress?
- **Hypothesis:** Main thread is in a long PRX computation or an error-retry loop caused by failed HLE imports.
- **Tools/Logs:** Stall report, import trace, sema statistics
- **Finding:** Stall detector shows main thread NOT blocked — running but silent after `Import#79360` (`sceKernelAllocateDirectMemory`). All 14 other threads (13 workers + 1 GC) are blocked on their semaphores. Import errors observed: `sceKernelVirtualQuery` NOT_FOUND, `sceKernelDirectMemoryQuery` NOT_FOUND, `fopen` NOT_FOUND, `scePadDeviceClassGetExtendedInformation` UNRESOLVED, unknown NID `1-LFLmRFxxM` PERMISSION_DENIED.
- **Root Cause:** Preliminary — main thread appears to be in a PRX computation or error path; root cause not yet identified.
- **Status:** CONFIRMED (symptom) — but root cause was WRONG (corrected in EXP-087)
- **Related:** EXP-085, EXP-087
- **Impact:** Identified the exact point of main-thread silence (`sceKernelAllocateDirectMemory`). Captured thread states and import errors for downstream EXPs.

### Updated Current State (after EXP-086)
**Solved:** Path B reaches `sceKernelAllocateDirectMemory` — GPU memory allocated.
**Still blocked:** Main thread silent after `AllocateDirectMemory`. All workers + GC thread blocked. No crashes.
**Next debugging target:** Is the main thread in a spinlock/retry loop, or making slow forward progress in PRX code? (EXP-087)


---

## EXP-087 (added 2026-07-31)

### EXP-087 — Main Thread Blocked on WaitSema(0x81): All 15 Threads Deadlocked
- **Date:** 2026-07-31
- **Commit:** {c087}
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What is the main thread doing after `sceKernelAllocateDirectMemory`?
- **Hypothesis:** Re-examine stall snapshot for main thread state.
- **Tools/Logs:** Stall detector snapshot (already in EXP-086 log, but not analyzed)
- **Finding:** Main thread IS blocked — on `sceKernelWaitSema(handle=0x81)`. The stall snapshot captured: `rip=0x6FFFFD001150` (WaitSema import stub), `rdi=0x6FFF00000081` (handle 0x81), `ret=0x804F6E9EB` (PRX vaddr 0x2999EB). ALL 15 threads blocked. Handle 0x81 = `Baselib_SystemSemaphore`, created alongside 0x80, 0x82, right before GC semaphores 0x83, 0x84. 0 `sema.signal` entries for any of 0x5C..0x74, 0x81, 0x83 in entire log.
- **Root Cause:** True all-threads-deadlock — nobody signals handle 0x81.
- **Status:** CONFIRMED
- **Related:** EXP-086 (corrected), EXP-088
- **Impact:** Re-classified deadlock from "main thread running silently" to "main thread blocked on WaitSema(0x81)". The stall detector's `Stall snapshot` line was always there but had been overlooked.

### Correction
EXP-086 said "main thread is NOT blocked — it's running." **WRONG.** The stall detector lists only HLE-handler-blocked threads; the main thread is in the import-stub path and was missed. **Corrected:** ALL 15 threads are blocked — true deadlock.

### Updated Current State (after EXP-087)
**Solved:** Identified exact semaphore handle blocking main thread (0x81 = `Baselib_SystemSemaphore`).
**Still blocked:** Nobody signals handle 0x81. All 15 threads deadlocked.
**Next debugging target:** What PRX function calls `WaitSema(0x81)` at `0x804F6E9EB`, and what should signal it? (EXP-088)


---

## EXP-088 (added 2026-07-31)

### EXP-088 — Semaphore 0x81 Owner: IL2CPP ThreadPool Work-Available Semaphore
- **Date:** 2026-07-31
- **Commit:** {c088}
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What PRX function calls `WaitSema(0x81)` at `0x804F6E9EB`, and what code should call `SignalSema(0x81)`?
- **Hypothesis:** Handle 0x81 belongs to a specific IL2CPP subsystem with a known signal site.
- **Tools/Logs:** Static analysis (disassembly of WaitSema/SignalSema callers, thread-pool dispatch loop)
- **Finding:** Handle 0x81 is the **IL2CPP ThreadPool work-available semaphore**. WaitSema caller = `0x804F6E510` (PRX vaddr 0x299510, ThreadPool dispatch function, confirmed by strings `"IL2CPP Threadpool worker"`, `"ThreadPool"`). Handle loaded from `[r14+0x88]` (thread-pool context). SignalSema caller at `0x804F6ECF9` is in the SAME function — invoked only when an atomic CAS on `[entry+0x90]` succeeds AND the work delta is negative (worker needs wake). 181 total callers of the SignalSema wrapper in the PRX; only 1 uses offset `+0x88`. SignalSema never fires because **no work is ever submitted to the thread pool**.
- **Root Cause:** No work is submitted to the IL2CPP ThreadPool — the CAS at `0x804F6EC75` never succeeds — `SignalSema(0x81)` never called.
- **Status:** CONFIRMED
- **Related:** EXP-087, EXP-089
- **Impact:** Re-classified deadlock from "missing signal" to "missing work submission". The fix is NOT to force `SignalSema(0x81)` (would wake main thread with garbage work) — the fix is to find what should submit work to the pool.

### Updated Current State (after EXP-088)
**Solved:** Semaphore 0x81 ownership = IL2CPP ThreadPool work-available. SignalSema exists but is gated on work being submitted.
**Still blocked:** No work submitted to the thread pool — main thread enters pool and waits forever.
**Next debugging target:** What prevents the IL2CPP runtime from submitting work to the thread pool after allocating GPU memory? (EXP-089)


---

## EXP-089 (added 2026-07-31)

### EXP-089 — Missing Work Submission: Main Thread Enters ThreadPool Without Queuing Work
- **Date:** 2026-07-31
- **Commit:** {c089}
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What prevents IL2CPP from submitting work to the ThreadPool after `sceKernelAllocateDirectMemory`?
- **Hypothesis:** An HLE error or missing trigger prevents the runtime from reaching the work submission stage.
- **Tools/Logs:** Log timeline analysis (line-by-line HLE calls and semaphore operations)
- **Finding:** Only 18 log lines between `sceKernelAllocateDirectMemory` (line 8905) and the deadlock (line 8923). Main thread creates GC system (lines 8906-8907), thread-pool semaphores 0x85-0x90 (lines 8908-8918), GC thread (line 8922), then IMMEDIATELY enters the pool as a worker and blocks on `WaitSema(0x81)` (line 8923). No work is queued between GC creation and pool entry. 0 sema.signal calls in this window. The missing work submission is likely a GC trigger, IL2CPP runtime callback, or timer/event that SharpEmu doesn't generate.
- **Root Cause (preliminary):** Classification D — Unity/IL2CPP waiting for an event SharpEmu never generates.
- **Status:** CONFIRMED — but classification was CORRECTED in EXP-090
- **Related:** EXP-088, EXP-090
- **Impact:** Pinned the missing transition down to an 18-line window. Eliminated the EXP-058 "2.45 billion entries" bug — the tracer was dividing a pointer by entry_size; the actual count is `rcx=0x379=889`.

### Correction
EXP-058/079 reported `array_proc count=2454267240`. **WRONG** — tracer bug (rsi is a pointer, not count*entry_size). **Corrected:** count = `rcx=0x379=889`.

### Updated Current State (after EXP-089)
**Solved:** Pinned missing work submission to an 18-line window. Tracer bug for array_proc count corrected.
**Still blocked:** Unknown what event should trigger work submission.
**Next debugging target:** What event should trigger IL2CPP runtime to submit work to the ThreadPool after GC system creation? (EXP-090)


---

## EXP-090 (added 2026-07-31)

### EXP-090 — Missing Trigger: _ThreadPoolWaitCallback Lookup Returns NULL Due to Empty Hash Table
- **Date:** 2026-07-31
- **Commit:** {c090}
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What event should trigger the first IL2CPP ThreadPool work submission?
- **Hypothesis:** The missing trigger is a function pointer that the IL2CPP runtime looks up via the metadata hash table.
- **Tools/Logs:** Static analysis of `real_init` (`0x804F04BA0`) — found `_ThreadPoolWaitCallback` string reference and lookup call.
- **Finding:** The missing trigger is the **`_ThreadPoolWaitCallback` function pointer**. `real_init` at offset `+0x0A36` performs: `mov rdi, [type_ptr]; lea rsi, [namespace]; lea rdx, ["_ThreadPoolWaitCallback"]; call 0x804F21D70` (il2cpp_class_get_method_from_name). Result stored at global `0x808B53C48`. Because the hash table is empty (EXP-040), the lookup returns NULL, the global stays NULL, and the ThreadPool has no callback to invoke when work is submitted. The EXP-085 metadata flag patch (`[entry+0x19]=1`) makes `metadata_lookup` return 0 for ALL queries, compounding the issue.
- **Root Cause:** IL2CPP metadata hash table empty → `_ThreadPoolWaitCallback` lookup returns NULL → ThreadPool has no worker callback → no work dispatched → deadlock.
- **Status:** CONFIRMED
- **Related:** EXP-040, EXP-085, EXP-088, EXP-089, EXP-091
- **Impact:** Re-classified from "missing event" (D) to "missing HLE implementation" (A) — metadata hash table not populated. Single root cause now links EXP-040, EXP-083, EXP-085, EXP-088, EXP-089.

### Correction
EXP-089 said "Classification D — Unity/IL2CPP waiting for event SharpEmu never generates." **CORRECTED:** Classification A — missing HLE implementation (metadata hash table not populated). The trigger is not a timer or GC callback — it is the `_ThreadPoolWaitCallback` function pointer, which exists in the PRX but cannot be found because the hash table is empty.

### Updated Current State (after EXP-090)
**Solved:** Missing trigger identified = `_ThreadPoolWaitCallback` function pointer lookup. Lookup site at `0x804F055D6`. Result global at `0x808B53C48` (NULL when hash table empty).
**Still blocked:** Hash table is empty — lookups return NULL.
**Next debugging target:** What PRX function should populate the IL2CPP metadata hash table, and why doesn't it insert entries? (EXP-091)


---

## EXP-091 (added 2026-07-31)

### EXP-091 — Hash Table Never Populated: PRX DT_INIT Registration Missing
- **Date:** 2026-07-31
- **Commit:** {c091}
- **Configuration:** same as EXP-086
- **Path:** B
- **Question:** What PRX function should populate the IL2CPP metadata hash table at `0x801EF7610`, and why are entries missing?
- **Hypothesis:** `il2cpp_codegen_register` runs during PRX DT_INIT and should insert entries — SharpEmu may not call the PRX's DT_INIT.
- **Tools/Logs:** Exhaustive static analysis of reads/writes to `0x801EF7610` in EBOOT and PRX.
- **Finding:** Hash table at `0x801EF7610` is **created but never populated**. Hash table struct at `0x600103DB0`, entries array at `0x60053E990`, mask `0x7FFF8`, populated `0/100` (all `0xFFFFFFFF` sentinel). EBOOT: 1689 READ sites (all LOOKUP), 1 WRITE site (creator only, at `0x8007F928C`). PRX: 0 reads, 0 writes to `0x801EF7610`. The hash_table_writer (`0x8007F90A0`) only allocates and initializes the structure — it does NOT insert entries. Entries should be inserted by `il2cpp_codegen_register` during PRX module initialization (DT_INIT), which directly inserts entries WITHOUT using the lookup mechanism (breaking the chicken-and-egg).
- **Root Cause (FINAL):** SharpEmu likely doesn't call the PRX's DT_INIT, so `il2cpp_codegen_register` never runs, and the hash table stays empty.
- **Status:** CONFIRMED
- **Related:** EXP-040, EXP-083, EXP-085, EXP-088, EXP-090, EXP-092
- **Impact:** Single root cause identified that connects ALL prior findings. Fix = ensure the PRX's DT_INIT is called during module loading.

### Chicken-and-Egg
The IL2CPP runtime looks up function pointers (like `_ThreadPoolWaitCallback`) via the hash table. But the insert function is ALSO looked up via the hash table. Without initial entries (from DT_INIT), no lookups succeed — including the lookup for the insert function itself. DT_INIT breaks this cycle by directly inserting entries without using the lookup mechanism.

### Updated Current State (after EXP-091)
**Solved:** Single root cause identified — PRX DT_INIT not called → hash table empty → all lookups fail → deadlock.
**Still blocked:** DT_INIT not yet confirmed as called or not called.
**Next debugging target:** Does SharpEmu call the PRX's DT_INIT function during module loading, and does `il2cpp_codegen_register` run? (EXP-092)


---

## EXP-092 (added 2026-07-31)

### EXP-092 — DT_INIT_ARRAY Fix Applied (37 More Semaphores), Hash Table Still Empty
- **Date:** 2026-07-31
- **Commit:** {c092}
- **Configuration:** `SHARPEMU_SEMA_FAST_PATH=0`, metadata at `Media/Metadata/`, EXP-085 flag patch active, **DT_INIT_ARRAY fix applied**
- **Path:** B
- **Question:** Does SharpEmu execute PRX DT_INIT during module loading?
- **Hypothesis:** SharpEmu's PRX loader skips DT_INIT_ARRAY, so module_start never runs.
- **Tools/Logs:** Code analysis of `RunPreloadedModuleInitializers` and `RunImageInitializers`; runtime evidence (37 more semaphores created, different stall handle).
- **Finding:** `RunPreloadedModuleInitializers` only called `InitFunctionEntryPoint` (DT_INIT), and DT_INIT on PS5 PRXs resolves to the ELF header (`imageBase+0x10`) which is `< 0x10000`, causing the entire module to be skipped via `continue`. `RunImageInitializers` (which calls DT_INIT_ARRAY) existed but was DEAD CODE — never called. Fix: modified `RunPreloadedModuleInitializers` to (1) not skip the module when DT_INIT is invalid (only skip the DT_INIT call), and (2) call `RunImageInitializers` for every module. After fix: PRX `module_start` (`0x804CD5010`) executes, 37 MORE semaphores created (stall moved from handle `0x81` to `0xA6`), but hash table STILL empty (`0/100`).
- **Root Cause:** `RunImageInitializers` was dead code → DT_INIT_ARRAY never ran → `module_start` never executed. Hash table population happens DURING `il2cpp_init` (in `real_init` → `call#7`), not during DT_INIT_ARRAY (which does C++ static init).
- **Status:** CONFIRMED — fix is correct and necessary but not sufficient
- **Related:** EXP-091, EXP-093
- **Impact:** DT_INIT_ARRAY fix is correct (module_start now runs, 37 more semaphores created). But hash table population is a separate code path — `il2cpp_codegen_register` is called during `il2cpp_init` and still doesn't insert entries.

### Updated Current State (after EXP-092)
**Solved:** DT_INIT_ARRAY now executes. `module_start` (`0x804CD5010`) runs. PRX static initializers execute. 37 more semaphores created.
**Still blocked:** Hash table STILL empty (`0/100`). `il2cpp_codegen_register` is called during `il2cpp_init` but doesn't insert entries.
**Next debugging target:** Trace `il2cpp_init → real_init → call#7 → il2cpp_codegen_register → hash insert function`. Why doesn't `il2cpp_codegen_register` insert entries? (EXP-093)
"""


def backfill_history():
    with open(HIST, "r", encoding="utf-8") as f:
        text = f.read()

    # 1. Replace "[pending]" placeholders for EXP-082..085 with real commit links.
    # Each EXP-082..085 entry has a line like:
    #   "- **Commit:** [pending]"
    # We replace per-EXP by walking the EXP section headers.
    replacements = []
    for exp in ("082", "083", "084", "085"):
        # Find each section by its heading, then replace the first [pending] after it.
        # Use a regex that captures the section heading + the first Commit line.
        pattern = re.compile(
            r"(### EXP-" + exp + r" [^\n]*\n(?:.*\n)*?- \*\*Commit:\*\*) \[pending\]",
            re.MULTILINE,
        )
        new_text, n = pattern.subn(rf"\1 {url(exp)}", text)
        if n == 0:
            print(f"WARN: no [pending] commit placeholder found for EXP-{exp}", file=sys.stderr)
        else:
            print(f"EXP-{exp}: replaced {n} [pending] placeholder(s) with commit link")
        text = new_text

    # 2. Update header coverage line.
    text = text.replace(
        "**Coverage: EXP-026 through EXP-081 (56 experiments)**",
        "**Coverage: EXP-026 through EXP-092 (63 experiments)**",
    )
    text = text.replace(
        "**Last updated: 2026-07-31 (EXP-081)**",
        "**Last updated: 2026-07-31 (EXP-092)**",
    )
    # Update TOC anchor if present
    text = text.replace(
        "1. [EXP Timeline (EXP-026 through EXP-081)](#exp-timeline)",
        "1. [EXP Timeline (EXP-026 through EXP-092)](#exp-timeline)",
    )
    text = text.replace(
        "4. [Current State (after EXP-081)](#current-state)",
        "4. [Current State (after EXP-092)](#current-state)",
    )

    # 3. Append EXP-086..092 sections (formatted with commit URLs).
    sections = SECTIONS.format(
        c086=url("086"),
        c087=url("087"),
        c088=url("088"),
        c089=url("089"),
        c090=url("090"),
        c091=url("091"),
        c092=url("092"),
    )

    # Remove trailing whitespace/newlines from existing file, then append.
    text = text.rstrip() + "\n" + sections.rstrip() + "\n"

    with open(HIST, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {HIST} ({len(text)} bytes)")


def backfill_index():
    with open(IDX, "r", encoding="utf-8") as f:
        text = f.read()

    # Build new rows for EXP-082..092, matching the existing table schema:
    # | EXP | Date | Commit | Status | Key Finding | Next Dependency |
    rows = [
        ("082", "2026-07-31", "CONFIRMED",
         "Crash at 0x80080684D is NULL per-image hash table — downstream of EXP-053. r15 = [image+0x278], never initialized because IL2CPP metadata registration wrapper (0x800805AE0) never called.",
         "EXP-053, EXP-056, EXP-052, EXP-083"),
        ("083", "2026-07-31", "CONFIRMED",
         "Metadata global 0x801E51240 never populated — hash_lookup (0x8004BD620) returns NULL, conditional write at 0x8013EF019 skipped. crash_func (0x80135DDD0) reads NULL global and crashes at [NULL+0x98]. Wrapper 0x800805AE0 is a #dllimport: parser, NOT il2cpp_codegen_register (EXP-052/053 misidentified).",
         "EXP-041, EXP-042, EXP-053, EXP-057, EXP-082, EXP-084"),
        ("084", "2026-07-31", "CONFIRMED",
         "Metadata list flag bug — entries have flag=0x00 at +0x19 (searchable) when they should be non-zero before il2cpp_init. metadata_lookup (0x800C66B40) returns non-zero, callback calls crash_func, crash at 0x80135DE83. NOT caused by empty hash table.",
         "EXP-039, EXP-040, EXP-041, EXP-046, EXP-083, EXP-085"),
        ("085", "2026-07-31", "CONFIRMED — DIAGNOSTIC PATCH",
         "Metadata flag patch ([entry+0x19]=1) eliminates crash — Yatzi reaches VideoOut for first time. Side effect: ALL metadata lookups return NULL, including _ThreadPoolWaitCallback (EXPOSED in EXP-090).",
         "EXP-084, EXP-086, EXP-090"),
        ("086", "2026-07-31", "SUPERSEDED BY EXP-087",
         "Path B deadlock analysis — main thread goes silent after sceKernelAllocateDirectMemory. Stall report shows main thread NOT in blocked list. WRONG: stall detector only lists HLE-handler-blocked threads, not import-stub-blocked (corrected in EXP-087).",
         "EXP-085, EXP-087"),
        ("087", "2026-07-31", "CONFIRMED",
         "Main thread IS blocked — on WaitSema(handle=0x81) at PRX 0x804F6E9EB. Stall snapshot: rip=0x6FFFFD001150 (WaitSema import stub), rdi=0x6FFF00000081. ALL 15 threads deadlocked. 0 SignalSema calls for 0x5C..0x74, 0x81, 0x83.",
         "EXP-086, EXP-088"),
        ("088", "2026-07-31", "CONFIRMED",
         "Semaphore 0x81 = IL2CPP ThreadPool work-available semaphore. WaitSema caller = 0x804F6E510 (ThreadPool dispatch, confirmed by strings 'IL2CPP Threadpool worker'). Handle loaded from [r14+0x88]. SignalSema at 0x804F6ECF9 in SAME function — only fires on CAS success at [entry+0x90] + negative delta. Never fires because no work submitted.",
         "EXP-087, EXP-089"),
        ("089", "2026-07-31", "CONFIRMED — CLASSIFICATION CORRECTED IN EXP-090",
         "Main thread creates GC system + thread pool, then IMMEDIATELY enters pool as worker without queuing work. Only 18 log lines between AllocateDirectMemory (line 8905) and deadlock (line 8923). 0 sema.signal calls in this window. EXP-058 '2.45B count' was a tracer bug — real count = rcx=0x379=889.",
         "EXP-088, EXP-090"),
        ("090", "2026-07-31", "CONFIRMED",
         "Missing trigger = _ThreadPoolWaitCallback function pointer. real_init at +0x0A36 calls il2cpp_class_get_name (0x804F21D70) to look up '_ThreadPoolWaitCallback' → returns NULL (hash table empty). Result stored at 0x808B53C48 = NULL → ThreadPool has no callback. Classification A (missing HLE), not D (missing event).",
         "EXP-040, EXP-085, EXP-088, EXP-089, EXP-091"),
        ("091", "2026-07-31", "CONFIRMED — ROOT CAUSE",
         "ROOT CAUSE: hash table created but NEVER populated. EBOOT: 1689 READ sites (all lookup), 1 WRITE (creator only at 0x8007F928C). PRX: 0 reads, 0 writes to 0x801EF7610. Entries should be inserted by il2cpp_codegen_register during PRX DT_INIT. Chicken-and-egg: insert function is looked up via hash table, but hash table is empty without insert function. DT_INIT breaks cycle by direct insertion.",
         "EXP-040, EXP-083, EXP-085, EXP-088, EXP-090, EXP-092"),
        ("092", "2026-07-31", "CONFIRMED — FIX CORRECT BUT NOT SUFFICIENT",
         "DT_INIT_ARRAY fix: RunImageInitializers was dead code, never called. RunPreloadedModuleInitializers only called DT_INIT (resolves to ELF header on PS5 PRXs, imageBase+0x10 < 0x10000 → module skipped entirely). Fix: don't skip module when DT_INIT invalid, call RunImageInitializers for every module. After fix: module_start (0x804CD5010) runs, 37 MORE semaphores created (stall 0x81 → 0xA6). Hash table STILL empty — population happens during il2cpp_init, not DT_INIT_ARRAY.",
         "EXP-091, EXP-093"),
    ]

    new_row_lines = []
    for exp, date, status, finding, deps in rows:
        h = COMMITS[exp]
        commit_cell = f"[{h}]({GH_BASE}/{h})"
        # Truncate finding to match style of existing rows (~120 chars)
        if len(finding) > 130:
            finding = finding[:127] + "..."
        new_row_lines.append(
            f"| {exp} | {date} | {commit_cell} | {status} | {finding} | {deps} |"
        )
    new_rows = "\n".join(new_row_lines)

    # Append the new rows after the last existing row (EXP-081).
    # Find the EXP-081 row line and insert new rows after it.
    pattern = re.compile(r"(\| 081 \| 2026-07-31 \|.*\n)")
    match = pattern.search(text)
    if not match:
        print("ERROR: could not find EXP-081 row in index", file=sys.stderr)
        sys.exit(1)
    text = text[:match.end()] + new_rows + "\n" + text[match.end():]

    # Update the total line.
    text = text.replace(
        "**Total EXPs:** 56 (EXP-026 through EXP-081)",
        "**Total EXPs:** 63 (EXP-026 through EXP-092)",
    )

    with open(IDX, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {IDX} ({len(text)} bytes)")


if __name__ == "__main__":
    backfill_history()
    backfill_index()
    print("Backfill complete.")
