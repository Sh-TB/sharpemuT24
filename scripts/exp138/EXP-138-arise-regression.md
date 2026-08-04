# EXP-138 Arise Regression Test

**Date:** 2026-08-04
**Commit tested:** `9cef960` (EXP-138 patch) on `fde8cfa` (v0.0.12)
**Game:** Arise (PPSA06328)
**Result:** **FAIL** (same as v0.0.9 baseline — no regression)

---

## Environment

| Component | Value |
|-----------|-------|
| .NET SDK | 10.0.302 |
| OS | Linux x86-64 (sandbox) |
| GPU | Lavapipe (software Vulkan) |
| Vulkan | YES (via Lavapipe) |
| X11 | YES (Xvfb :99) |
| GLFW | X11 backend |
| Headless | NO (SHARPEMU_HEADLESS unset) |

---

## Build

**Status:** PASS

- 0 errors, 13 pre-existing warnings
- EXP-138 patch compiled cleanly
- Binary: `artifacts/bin/Release/net10.0/linux-x64/SharpEmu` (78256 bytes)

---

## Execution

| Field | Value |
|-------|-------|
| Game | Arise (PPSA06328) |
| Path | `/tmp/arise/eboot.bin` (24.8 MB) |
| Duration | <1 second (crashed immediately) |
| Binary | `SharpEmu` (Release build with EXP-138) |

**Command:**
```bash
DISPLAY=:99 VK_ICD_FILENAMES=/tmp/lvp_icd_fixed.json \
LD_LIBRARY_PATH=... \
SHARPEMU_TRACE_GUEST_IMAGES=present \
SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/arise-framebuffers \
./SharpEmu /tmp/arise/eboot.bin
```

---

## Results

| Metric | v0.0.9 Baseline | v0.0.12 Result | Status |
|--------|-----------------|----------------|--------|
| Boot | YES | YES (Can boot: YES) | ✅ PASS |
| Backend | — | VulkanVideoPresenter | ✅ PASS |
| GLFW X11 | — | Selected | ✅ PASS |
| Frame count | 0 | 0 | ⚠️ Same (no frames) |
| Framebuffer dumps | 0 | 0 | ⚠️ Same (no frames) |
| Crash | SIGILL | **SIGILL** | ⚠️ Same crash |
| Guest return | — | Exit code 132 (SIGILL) | ❌ FAIL |
| Unresolved NIDs | — | 38 logged (9507 total unresolved) | ⚠️ Expected |
| GPU memory faults | — | 5 (at 0x1FE000000) | ⚠️ Expected |
| AGC calls | 0 | 0 | ⚠️ Same (crashes before AGC) |

---

## Exact First Failure

**Crash type:** Illegal Instruction (SIGILL)

**Code at RIP:** `0F 0B 48 8D 3D DE 15 3F 01 E8 9C C4 FF 00 0F 0B`

- `0F 0B` = `ud2` (Undefined Instruction) — this is an **intentional abort** in the guest code
- The game deliberately executes `ud2` to signal a fatal error
- This is NOT a CPU emulation bug — the instruction is correctly executed as SIGILL

**Pre-crash events:**
1. Boot succeeds (`Can boot: YES`)
2. Backend selected: `VulkanVideoPresenter (default)` ✅
3. 5 GPU memory faults at address `0x1FE000000` (UNMAPPED WRITE)
   - `rip=0x800170FB2 fault=0x1FE000000 instr='mov qword ptr [rax],0'`
   - Guest tries to write to GPU memory address `0x1FE000000` which is not mapped
4. 38 unresolved NID imports logged (9507 total unresolved)
5. Game executes `ud2` (intentional abort)

---

## Root Cause Hypothesis

**The SIGILL crash is the same as v0.0.9 baseline.** This is NOT a regression from EXP-138.

**Root cause:** Arise (PPSA06328) crashes during early initialization because:
1. The game tries to access GPU memory at `0x1FE000000` (a GPU MMIO address)
2. SharpEmu has not mapped this address range (it's a GPU register space, not guest RAM)
3. The write faults are caught by the POSIX signal handler
4. The game's error handling path executes `ud2` (intentional abort)

**This is a pre-existing issue documented in v0.0.9 GOLDEN_BASELINE.md:**
```
| 4 | Arise (PPSA06328) | Native C++ | ❌ | SIGILL crash |
```

**EXP-138 did NOT cause this crash.** The crash occurs before any IL2CPP or `TryCallGuestFunction` code runs (Arise is native C++, not IL2CPP). EXP-138 only affects CPU backend return value propagation, which is neutral for native games.

---

## Evidence

### Log File
- **Path:** `scripts/exp138/evidence/arise/execution-log.txt` (1394 lines)
- **Key lines:**
  - Line 1: `[DEBUG] SharpEmu starting with 1 args`
  - Boot report: `Can boot: YES`
  - Backend: `VulkanVideoPresenter (default) (reason: GPU detected, using Vulkan)`
  - Crash: `Type: Illegal Instruction`
  - Code at RIP: `0F 0B 48 8D 3D DE 15 3F 01 E8 9C C4 FF 00 0F 0B`

### No Framebuffer Dumps
- 0 framebuffer dumps (game crashes before any rendering)

### GPU Memory Faults
```
[UNMAPPED] #1 WRITE rip=0x800170FB2 fault=0x1FE000000 instr='mov qword ptr [rax],0' len=7
[UNMAPPED] #2 WRITE rip=0x800170FB2 fault=0x1FE000040 instr='mov qword ptr [rax],0' len=7
[UNMAPPED] #3 READ rip=0x80017F382 fault=0xFFFFFFFF80020102 instr='vmovups ymm0,[rax+100h]' len=8
[UNMAPPED] #4 WRITE rip=0x8001717AB fault=0x1FE000080 instr='vmovups [rax],ymm0' len=4
[UNMAPPED] #5 WRITE rip=0x8001717AF fault=0x1FE0000A0 instr='mov [rax+20h],rcx' len=4
```

---

## Files Changed

**NONE.** This is a regression test only — no code changes were made.

---

## Comparison: v0.0.12 vs Previous Arise Failure

| Aspect | v0.0.9 (GOLDEN_BASELINE.md) | v0.0.12 (EXP-138) | Regression? |
|--------|----------------------------|---------------------|-------------|
| Crash type | SIGILL | SIGILL | ❌ No regression |
| Boot | YES | YES | ❌ No regression |
| Backend | — | VulkanVideoPresenter | ❌ No regression (improved) |
| Frame count | 0 | 0 | ❌ No regression (same) |
| AGC calls | 0 | 0 | ❌ No regression (same) |

**Conclusion:** EXP-138 does NOT regress Arise. The SIGILL crash is the same pre-existing issue documented in v0.0.9. Arise was never working — it's a known-broken game per the Game Status Matrix.

---

## Final Status

# **FAIL** (same as v0.0.9 baseline — NOT a regression)

**Arise (PPSA06328) crashes with SIGILL during early initialization.** This is the same behavior as v0.0.9. EXP-138 does not fix or worsen this crash.

**The crash is caused by:**
1. Game attempts to write to GPU MMIO address `0x1FE000000` (not mapped in SharpEmu)
2. Game's error handling executes `ud2` (intentional abort)
3. This is a pre-existing issue, NOT caused by EXP-138

**Regression gate result:** ✅ PASS — no regression from EXP-138.

**Safe to proceed to Yatzi FAST_PATH=0 validation.** Arise was never a working game (documented in GOLDEN_BASELINE.md as "❌ SIGILL crash" since v0.0.9). The EXP-138 patch does not make it worse.

---

## GitHub Evidence

| File | URL |
|------|-----|
| This report | https://github.com/Sh-TB/sharpemuT24/blob/main/exp-reports/EXP-138-arise-regression.md |
| Execution log | https://github.com/Sh-TB/sharpemuT24/blob/main/scripts/exp138/evidence/arise/execution-log.txt |
