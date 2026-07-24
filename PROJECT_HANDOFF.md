# SharpEmuT24 — Project Handoff Document

**Purpose:** This document enables any new agent or chat session to continue
the SharpEmu debugging work from the exact point we left off, WITHOUT
redoing any of the previously-completed investigations.

**Last updated:** 2026-07-24 (commit 37ea837 + env-restore work)

---

## 1. Project Identity

- **Repo:** https://github.com/Sh-TB/sharpemuT24
- **Upstream parent:** https://github.com/sharpemu/sharpemu
- **Latest investigation commit on `main`:** `37ea837` — "exp: file IO inventory — systematic dump issue, both Yatzi and Seeker affected"
- **Default branch:** `main`
- **Fork branches of interest:**
  - `feat/diagnostics-framework` — has upstream PRs from Jul 21 we have NOT merged
  - `integration/latest-upstream` — has upstream PRs from Jul 19
  - `main` — our work (today's experiments + fallback fix)

---

## 2. FIRST STEPS FOR THE NEW AGENT

### Do NOT:
- ❌ Re-investigate NID return-zero hypothesis (already disproved)
- ❌ Re-investigate `0xC0DEC0DECAFEBA00` magic marker (already identified as SharpEmu TLS canary)
- ❌ Re-investigate the `Internal-ErrorShader` abort (already root-caused)
- ❌ Revert the `SHARPEMU_VIDEOOUT_FALLBACK_IMAGE` fallback fix (it works correctly)
- ❌ Remove the headless Vulkan path (Dreaming Sarah still depends on it)
- ❌ Fake frames or skip GPU initialization
- ❌ Add new IL2CPP stubs without verifying they are actually called

### DO FIRST:
1. **Restore source** from GitHub commit `37ea837`:
   ```bash
   git clone https://github.com/Sh-TB/sharpemuT24.git
   cd sharpemuT24
   git checkout 37ea837
   git log --oneline -50  # verify history
   ```
   ⚠️ The repo has a nested layout: actual source lives at `work/sharpemuT24/`
   inside the repo. Reorganize if needed:
   ```bash
   # Extract real source to a clean location
   mv work/sharpemuT24 /home/z/my-project/work/sharpemuT24-src
   ```

2. **Read all documentation:**
   ```bash
   find . -iname "*checkpoint*" -o -iname "*status*" -o -iname "*project*"
   ```
   Specifically read:
   - `work/sharpemuT24/CHECKPOINT_v0.0.11.md` — definitive investigation log (21 sections)
   - `work/sharpemuT24/PROJECT_STATUS_v0.0.10.md`
   - `work/sharpemuT24/PROJECT_STATUS_v0.0.9.md`
   - `worklog.md` — chronological experiment log

3. **Restore build environment** (if environment was wiped):
   ```bash
   # Install .NET 10 SDK
   curl -sSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
   chmod +x /tmp/dotnet-install.sh
   bash /tmp/dotnet-install.sh --channel 10.0 --install-dir /home/z/.dotnet
   export PATH="/home/z/.dotnet:$PATH"

   # Install Vulkan Lavapipe (without root)
   cd /tmp
   apt-get download mesa-vulkan-drivers
   mkdir -p /home/z/.local/vulkan
   dpkg-deb -x mesa-vulkan-drivers_*.deb /home/z/.local/vulkan

   # Restore libglfw.so.3 from backup if available
   cp /tmp/my-project/work/sharpemu-build/libglfw.so.3 /home/z/my-project/work/sharpemu-build/

   # Restore ps5_names.txt (required by source generator)
   cp /tmp/my-project/work/sharpemuT24/scripts/ps5_names.txt \
      /home/z/my-project/work/sharpemuT24-src/work/sharpemuT24/scripts/

   # Start Xvfb
   mkdir -p /tmp/.X11-unix /tmp/xdg
   chmod 1777 /tmp/.X11-unix /tmp/xdg
   nohup setsid Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset \
       > /tmp/xvfb.log 2>&1 < /dev/null &
   disown; sleep 3

   # Build SharpEmu
   cd /home/z/my-project/work/sharpemuT24-src/work/sharpemuT24
   dotnet publish src/SharpEmu.CLI/SharpEmu.CLI.csproj -c Release -r linux-x64
   cp artifacts/publish/SharpEmu.CLI/Release/net10.0/linux-x64/SharpEmu \
      /home/z/my-project/work/sharpemu-build/SharpEmu
   ```

4. **Verify state before doing anything:**
   ```bash
   git rev-parse HEAD          # must be 37ea837 (or descendant)
   dotnet --version            # 10.0.302
   pgrep Xvfb                  # Xvfb must be running on :99
   ```

5. **Run the existing experiment scripts** to reproduce the current state:
   ```bash
   # Environment variables (must be set before running SharpEmu)
   export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
   export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
   export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
   export SHARPEMU_WRITABLE_APP0=1

   # Run golden test (Dreaming Sarah baseline)
   cd /home/z/my-project/work/sharpemuT24-src/work/sharpemuT24
   bash tests/golden/run-golden-tests.sh
   ```

---

## 3. SOLVED INVESTIGATIONS (do not redo)

These were investigated and either solved or definitively ruled out:

| Topic | Status | Notes |
|-------|--------|-------|
| NID `1D0H2KNjshE` / `hsi9drzHR2k` busy-wait loop | ❌ DISPROVED | Loop is finite (80,311 calls in 2s), exits naturally. Not a polling loop. |
| `0xC0DEC0DECAFEBA00` "Unity error marker" | ❌ DISPROVED | It's SharpEmu's TLS stack canary (`tlsBase + 0x28`). Found in 5 source files. |
| `flip_capture_failed` warning | ✅ FIXED | `SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1` env var creates black placeholder image. |
| `RegisterKnownDisplayBuffer` missing Vulkan image | ✅ UNDERSTOOD | Confirmed AGC `render_target_new` path is the legitimate creator. RegisterBuffers should NOT create images. |
| `Internal-ErrorShader.shader` abort | ✅ ROOT-CAUSED | Unity's shader lookup returns NULL → intentional `xor r12d,r12d; cmp [r12+0x38],0; ud2` abort pattern. |
| Empty `unity_builtin_extra` (0 bytes) | ✅ ROOT-CAUSED | Systematic dump issue — affects both Yatzi AND Seeker. |
| Yatzi encrypted PRX files | ✅ FIXED BY USER | User uploaded new dump (`decrypted.part01-04.rar`) with real decrypted PRX files. |

---

## 4. CURRENT TECHNICAL STATUS

### Environment (as of 2026-07-24 end of session):

| Component | Version / Status |
|-----------|------------------|
| SharpEmu source | commit `37ea837` on `main` |
| .NET SDK | 10.0.302 |
| Vulkan Lavapipe | mesa-vulkan-drivers 25.0.7-2+deb13u1 |
| libvulkan1 | 1.4.309.0-1 |
| LLVM | 19.1.7-3+b1 (⚠️ may be different from previous working env) |
| Xvfb | Running on `:99` |
| SharpEmu binary | Built and deployed to `/home/z/my-project/work/sharpemu-build/SharpEmu` |

### Game dump inventory:

| Game | Location | Status |
|------|----------|--------|
| Dreaming Sarah (PPSA02929) | `/tmp/games/dreaming-sarah/PPSA02929-app0/` | ✅ Complete (after restoring 19 missing `.vert` shader files from backup) |
| Yatzi (PPSA17697) | `/tmp/games/yatzi/` | ✅ **NEW: Real decrypted PRX files** (from `decrypted.part01-04.rar`) — much better than previous encrypted dump |
| Seeker (PPSA12500) | Need to re-extract from `/home/z/my-project/upload/Seeker My Shadow 01.002 PPSA12500file.rar` | Has same empty `unity_builtin_extra` issue as Yatzi |

### Golden test status: ⚠️ FAILING

```
Frame count: 150 (min: 50) — ✅ PASS
Max distinct colors: 23 (min: 50) — ❌ FAIL
```

**Critical symptom:** ALL 150 frames are byte-identical (same MD5 `09bdc09fea2db544132493c2bfbb4b2d`).

- `render_work_enter` events ARE happening (150 unique submission numbers)
- `present_taken` events ARE happening (alternating between two guest image addresses)
- But the swapchain image is NOT being updated between frames

**Important:** This is NOT a code regression — the same problem occurs with the older backup binary (from Jul 23, before today's changes). This is an environmental issue.

**Suspected cause:** LLVM version change (now 19.1.7, was probably 18.1.x in the previously-working environment). Lavapipe may be silently failing to render.

### Yatzi status (with new dump): 🎉 MAJOR PROGRESS

The new Yatzi dump (with real decrypted PRX files) gets MUCH further:

**Before (encrypted PRX dump):** Stuck at `Internal-ErrorShader.shader` lookup abort
**After (real PRX dump):** Reaches IL2CPP class loading, crashes with different error

Crash stack shows Unity class names:
- `FExpressionValuesProxy`
- `Allocator`
- `ProfilerMarker`
- `Unity.Collections`
- `VisualEffectAssetProxy`

This means the IL2CPP path is now much further along. The new crash is a different HLE issue, NOT the shader lookup problem.

---

## 5. KEY FILES TO READ

### Documentation (in repo):
- `work/sharpemuT24/CHECKPOINT_v0.0.11.md` — 21-section definitive investigation log
- `worklog.md` — chronological experiment log (in repo root)
- `work/sharpemuT24/PROJECT_STATUS_v0.0.9.md` and `v0.0.10.md`
- `work/sharpemuT24/GAME_STATE_MATRIX.md`
- `work/sharpemuT24/SHARPEMU_KNOWLEDGE_BASE.md`

### Source code (key files):
- `work/sharpemuT24/src/SharpEmu.Libs/Kernel/PipelineCallCounters.cs` — new file, pipeline call counters
- `work/sharpemuT24/src/SharpEmu.Libs/Kernel/GameCompatExports.cs` — NID stubs with tracing
- `work/sharpemuT24/src/SharpEmu.Libs/VideoOut/VulkanVideoPresenter.cs` — fallback image creation
- `work/sharpemuT24/src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Exceptions.cs` — UNMAPPED logger
- `work/sharpemuT24/src/SharpEmu.Core/Loader/BootDependencyAnalyzer.cs` — boot dep analyzer

### Reusable tools (in `work/sharpemuT24/scripts/`):
- `disasm_around_rip.py` — disassembles bytes around a guest RIP (uses pyelftools + capstone)
- `exp-nid-caller-map.sh` — captures caller module+offset for NID calls
- `exp-nid-nonzero-test.sh` — tests if non-zero return breaks the NID loop
- `exp-pipeline-counters.sh` — side-by-side pipeline function call comparison
- `exp-gimg-lifecycle.sh` — traces _guestImages creation lifecycle
- `exp-fallback-flip.sh` — tests the fallback image fix
- `exp-pre-fault-calls.sh` — traces HLE calls between VideoOut ready and fault

### Also restored to `/home/z/my-project/scripts/`:
All the above scripts are also copied to `/home/z/my-project/scripts/` for convenience.

---

## 6. ENVIRONMENT VARIABLES (SharpEmu)

These are the key env vars (set before running SharpEmu):

```bash
# Required for Vulkan
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build

# Required for display
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg

# Game setup
export SHARPEMU_APP0_DIR=<path-to-game-app0>
export SHARPEMU_WRITABLE_APP0=1

# Frame capture (for golden test)
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=<dump-dir>
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1

# Optional: enable our fallback image fix (for Yatzi)
export SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1

# Optional: pipeline call counters
export SHARPEMU_PIPELINE_COUNTERS=1

# Optional: NID tracing
export SHARPEMU_NID_CALLER_MAP=1
export SHARPEMU_NID_RETURN_NONZERO=1

# Optional: file IO tracing
export SHARPEMU_LOG_OPEN=1
export SHARPEMU_LOG_IO=1

# IMPORTANT: unset these (they break things)
unset SHARPEMU_HEADLESS          # Must be unset for real Vulkan frames
unset SHARPEMU_SEMA_FAST_PATH    # Breaks Unity
```

---

## 7. CRITICAL CONTEXT

### The intentional NULL dereference pattern

When you see an UNMAPPED fault like:
```
[UNMAPPED] #1 READ rip=0x800B28A0D fault=0x38 instr='cmp qword ptr [r12+38h],0'
R12=0x0000000000000000 ...
```

And the disassembly shows:
```asm
xor eax, eax
xor r12d, r12d          ; R12 = 0 INTENTIONALLY
cmp [r12+0x38], 0       ; FAULT — deliberate NULL deref
jne <somewhere>
jmp <error_path>
call <abort_handler>
ud2                     ; UNDEFINED INSTRUCTION — abort()
```

This is Unity's **assertion abort pattern**. The code deliberately NULLs R12 then dereferences it to trigger SIGSEGV. The actual failure is BEFORE this code — in a function call that returned NULL.

Use `scripts/disasm_around_rip.py` to find the caller:
```bash
python3 /home/z/my-project/scripts/disasm_around_rip.py /tmp/games/<game>/eboot.bin 0x<RIP> 80 50
```

### The 0xC0DEC0DECAFEBA00 marker

This is SharpEmu's TLS stack canary (`__stack_chk_guard`), written to `tlsBase + 0x28`. It is NOT a Unity error marker. If you see it in RCX at a fault, it just means the function was doing stack canary validation — it does not indicate an error state.

Source locations:
- `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.cs:4550`
- `src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs:36`
- `src/SharpEmu.Core/Cpu/CpuDispatcher.cs:378`
- `src/SharpEmu.HLE/HleDataSymbols.cs:18`
- `src/SharpEmu.Libs/Kernel/KernelRuntimeCompatExports.cs:55`

### The fallback image fix

`SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1` enables lazy fallback image creation in `ExecuteOrderedGuestFlip`. When the game flips a registered display buffer before any rendering populated `_guestImages`, a black placeholder image is created on-the-fly. This matches real PS5 hardware behavior.

This is an **INTERMEDIATE step, not a complete fix**. It eliminates the `flip_capture_failed` warning and produces a black frame, but does not address the underlying Unity error state (in Yatzi's case, the missing `unity_builtin_extra`).

### The BootDependencyAnalyzer should be updated

`BootDependencyAnalyzer.cs` currently marks `unity_builtin_extra` and `unity default resources` as `FilePriority.Low`. This is incorrect — they are CRITICAL for Unity IL2CPP games. A future PR should:
1. Bump these to `FilePriority.Critical` for Unity IL2CPP games
2. Add a size check: if file exists but is 0 bytes, treat as missing

This would have caught the empty-file issue much earlier.

---

## 8. CURRENT FAILURE POINTS TO INVESTIGATE

### Failure 1: Golden test fails — all 150 frames byte-identical

**Symptom:**
- 150 frames produced (sufficient count)
- All 150 frames have the same MD5 (`09bdc09fea2db544132493c2bfbb4b2d`)
- Max distinct colors = 23 (need 50)
- `render_work_enter` events ARE happening (150 unique submissions)
- `present_taken` events ARE happening (alternating 2 guest image addresses)
- But the swapchain image never changes

**Tested:**
- Same problem with OLD backup binary (Jul 23, before today's changes) — NOT a code regression
- Same problem with cleared Vulkan pipeline cache
- Same problem with `VK_LOADER_DEBUG=warn`

**Suspected cause:** Environmental. LLVM version is now 19.1.7 (was probably 18.1.x before). Lavapipe may be silently failing to actually render.

**Next step:** Try installing LLVM 18 alongside LLVM 19 and see if that helps. Or try a different Lavapipe version.

### Failure 2: Yatzi crashes at IL2CPP class loading

**Symptom (with new real-PRX dump):**
- Yatzi boots much further than before
- Reaches IL2CPP class loading
- Crashes with "Need to implement HLE for this NID"
- Crash stack shows Unity class names: `FExpressionValuesProxy`, `Allocator`, `ProfilerMarker`, `Unity.Collections`, `VisualEffectAssetProxy`

**Status:** This is a NEW failure point (different from the previous `Internal-ErrorShader` abort). The new dump gets much further.

**Next step:** Capture the crash log, identify the missing NID, and implement the HLE for it.

---

## 9. BACKUP LOCATIONS

If `/home/z/my-project/work/` is missing, restore from:

| Resource | Backup Location |
|----------|-----------------|
| Source code | `git clone https://github.com/Sh-TB/sharpemuT24.git` (commit `37ea837`) |
| Older binary (Jul 23) | `/tmp/my-project/work/sharpemu-build/SharpEmu` |
| libglfw.so.3 | `/tmp/my-project/work/sharpemu-build/libglfw.so.3` |
| Dreaming Sarah dump | `/tmp/my-project/upload/PPSA02929/PPSA02929-app0/` |
| Yatzi dump (encrypted PRX, OLD) | `/tmp/my-project/upload/PPSA17697.rar` (eboot.bin only) |
| Yatzi dump (real PRX, NEW) | `/home/z/my-project/upload/decrypted.part01-04.rar` |
| Yatzi metadata | `/home/z/my-project/upload/PPSA17697-app0-(Fix)MediaMetadata.rar` (global-metadata.dat) |
| Seeker dump | `/home/z/my-project/upload/Seeker My Shadow 01.002 PPSA12500file.rar` |
| Seeker level10 | `/home/z/my-project/upload/eker My Shadow 01.002 PPSA12500 level10.rar` |
| Yatzi level0 | `/home/z/my-project/upload/level0` (1404 bytes — suspiciously tiny) |
| Yatzi sharedassets0.assets | `/home/z/my-project/upload/sharedassets0.assets` (1548 bytes — suspiciously tiny) |
| ps5_names.txt | `/tmp/my-project/work/sharpemuT24/scripts/ps5_names.txt` |
| Experiment scripts | `/tmp/my-project/scripts/exp-*.sh` and `disasm_around_rip.py` |

---

## 10. KEY COMMITS (read with `git show <sha>`)

```
37ea837  exp: file IO inventory — systematic dump issue, both Yatzi and Seeker affected
10ad31f  exp: ROOT CAUSE FOUND — Yatzi ships empty unity_builtin_extra
144e621  exp: lifecycle trace confirms AGC should create image; fallback fix is INTERMEDIATE
4710a77  exp: pipeline counters — ROOT CAUSE = RegisterKnownDisplayBuffer missing image
8a22795  exp: non-zero return DOES NOT break NID loop — busy-wait hypothesis refuted
7012c3e  feat: NID trace working — 1D0H2KNjshE/hsi9drzHR2k are busy-wait loop
881591a  feat: IL2CPP instrumentation — CRITICAL FINDING: SignalSema != 0
7ef6065  docs: CHECKPOINT_v0.0.11 — corrected conclusion + IL2CPP investigation plan
0455370  fix: remove Harvest Days stubs + fix xk0AcarP3V4 conflict
f83b6ea  final: comprehensive release report with all test results and mistakes documented
17a0d05  fix: restore PR #457 — GLFW X11 explicit platform hint for Xvfb-only Linux
74d272e  feat: Golden Baseline Rule v1.0 + automated golden test
```

---

## 11. GOLDEN BASELINE RULE (NON-NEGOTIABLE)

```
Tag: golden-render-baseline (v0.0.9, commit f83b6ea)
Game: Dreaming Sarah (PPSA02929)
Engine: Native C++
Expected: ≥50 frames, ≥50 distinct colors, real game content
Test: tests/golden/run-golden-tests.sh
```

**Rule:** Every change must pass Dreaming Sarah Golden Test before merge.

Currently the golden test is FAILING due to the environmental issue described in section 8. This must be fixed FIRST before any new code changes.

---

## 12. WHAT TO DO NEXT (priority order)

1. **Fix the environmental rendering issue** (golden test failing — all frames identical)
   - Suspect: LLVM 19 vs 18 incompatibility with Lavapipe
   - Try: install LLVM 18, or try a different Lavapipe version
   - Verify: golden test must produce 50+ distinct colors before proceeding

2. **Investigate Yatzi's new crash** (IL2CPP class loading)
   - Capture full crash log with `SHARPEMU_LOG_IO=1 SHARPEMU_LOG_OPEN=1`
   - Identify the missing NID from the crash output
   - Check if it's a known NID or a new one
   - Implement HLE for it (only after verifying it's actually called)

3. **Consider merging upstream PRs** from `feat/diagnostics-framework`:
   - `fix(gpu): support Gen5 flat memory and 3D images (#587)`
   - `feat: implement cosf, time, ctype tables, tracked heap access, IL2CPP lookup ABI paths (#540)`
   - `fix: VulkanHostBufferPool deadlock, audio overflow crash, and log grouping (#564)`
   - These may help with Yatzi's IL2CPP issues

4. **Update BootDependencyAnalyzer** to mark `unity_builtin_extra` as Critical + add 0-byte size check

---

## 13. ACKNOWLEDGMENTS

This document was created after a long debugging session that:
- Identified the real root cause of Yatzi's abort (empty `unity_builtin_extra`)
- Implemented a working fallback image fix
- Built reusable diagnostic tools (disasm, pipeline counters, lifecycle tracers)
- Discovered that the "magic marker" was SharpEmu's own TLS canary (not Unity's)
- Got Yatzi to a much deeper boot point with the new real-PRX dump

The user (Persian-speaking) provided invaluable guidance throughout, repeatedly
steering the investigation away from false hypotheses and toward cheap tests
before committing to expensive implementations.
