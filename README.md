<!--
Copyright (C) 2026 SharpEmu Emulator Project
SPDX-License-Identifier: GPL-2.0-or-later
-->

# SharpEmu — Fork with Linux Headless Rendering & Game Compatibility Shims

<p align="center">
  <img src="./assets/images/logo.png" width=30% height=30% />
</p>

<p align="center">
  An experimental PlayStation 5 emulator for Windows, Linux and macOS.<br/>
  <strong>This fork adds headless Linux rendering, C11/IL2CPP/Unity NID shims, and game-specific compatibility patches.</strong>
</p>

---

> [!NOTE]
> This is a **fork** of [sharpemu/sharpemu](https://github.com/sharpemu/sharpemu) tracking `upstream/main` closely. All fork-specific changes are isolated to specific files and commits so they can be upstreamed or reverted without touching the rest of the codebase.

> [!WARNING]
> SharpEmu is an experimental PS5 emulator developed from scratch in C#. The current focus is on accuracy and infrastructure setup rather than game-specific compatibility.

## What This Fork Adds (verified fork-only features)

Every claim below is **proven by source diff against `upstream/main`** and **by runtime evidence** (logs, PNG framebuffers, metrics JSON). If a feature exists in upstream, it is **not** listed here.

### 1. Headless Linux X11 / Xvfb Rendering Fix

**File:** `src/SharpEmu.Libs/VideoOut/VulkanVideoPresenter.cs` (function `PreferX11OnLinuxWayland`)
**Commit:** `4a059f2`

**Problem in upstream:** `PreferX11OnLinuxWayland()` only sets the `GLFW_PLATFORM_X11` init hint when `WAYLAND_DISPLAY` is set. On a plain X11/Xvfb session (no Wayland), the hint is never applied and GLFW 3.4's auto platform detection fails silently with `GLFW_PLATFORM_UNAVAILABLE (65550)`. The presenter thread then exits, and all subsequent `VulkanOffscreenGuestDraw` work items pile up in the queue with no thread draining them — so the guest's `dcb_set_flip` counter increments (guest-side) but `vk.flip_capture` stays at zero (host-side).

**Fix in fork:** Drop the `WAYLAND_DISPLAY` gate. Always set `GLFW_PLATFORM_X11` on Linux when `DISPLAY` is set.

**Runtime evidence (Dreaming Sarah, PPSA02929, 90s run on Xvfb + Lavapipe):**

| Metric | Upstream (broken on Xvfb) | Fork (fixed) |
|---|---|---|
| `vkQueueSubmit` count | 0 | **170** |
| `vkCmdDrawIndexed` count | 0 | **1,485** |
| `vkQueuePresentKHR` count | 0 | **170** |
| Framebuffer dumps | 0 | **170** |
| First frame nonblack % | 0% | **100%** |
| First real game image | Never | **Yes** |

### 2. C11 / C++ stdlib Synchronization Exports

**File:** `src/SharpEmu.Libs/Kernel/C11SyncExports.cs` (new file, 147 lines)
**Commit:** `05b5137`

**Problem in upstream:** 7 NIDs are missing:
- `_Mtx_init`, `_Mtx_lock`, `_Mtx_unlock` (C11 mutex)
- `_Cnd_init` (C11 condition variable)
- `sincosf` (libm)
- `srand` (libc)
- `_ZSt14_Throw_C_errori` (libstdc++)

**Games affected:** Arise (PPSA06328) crashes with SIGSEGV at `0x1FE000000` because its job scheduler calls `_Mtx_unlock` (unresolved), assumes success, and writes to GPU memory without holding the lock.

**Fix in fork:** New `C11SyncExports` class maps these NIDs onto the existing `KernelPthreadCompatExports.PthreadMutexInitCore` / `PthreadCondInitCore` infrastructure. No new threading code — pure delegation.

### 3. Game-Specific Private NID Shims

**File:** `src/SharpEmu.Libs/Kernel/GameCompatExports.cs` (new file, 122 lines)
**Commit:** `1429bbb`

**Problem in upstream:** Harvest Days (PPSA14677, Unity/IL2CPP) calls private NIDs that are not in the public Aerolib catalog. The most damaging is `zlqfTyrQSPk`, called 54,343 times in a tight loop — the guest's job scheduler waits on a private synchronization primitive that never returns, blocking all forward progress before any AGC submission.

**Fix in fork:** New `GameCompatExports` class provides stubs for 6 private NIDs:
- `zlqfTyrQSPk` → `sceKernelWaitOnAddressInternal` (sleep 1ms, return 0 — breaks the busy-wait loop)
- `dZGYu5wObJs` → `il2cpp_metadata_register_pool` (return 0)
- `35NoyMOtYpE` → `SetDataFolder` (return 0)
- `M4YYbSFfJ8g` → `setenv` (real implementation with `ConcurrentDictionary` storage)
- `-pnj3-7a6QA` → `unity_mono_set_user_malloc_mutex` (return 0)
- `cJ2Y4E-t258` → `il2cpp_api_register_symbols` (return 0)

**Runtime evidence:** Harvest Days previously infinite-looped at import #3690. After the fix, it breaks out of the loop, completes IL2CPP metadata registration, and reaches a new crash point (`ayuoL6Vjz2k` — investigation in progress).

### What This Fork Does NOT Add

To avoid claiming credit for upstream work, the following features are **in upstream** and are **not** fork-specific:

- AGC pipeline (`sceAgcDriverSubmitDcb` → `ParseSubmittedDcbCore` → `ApplySubmittedRegisters`)
- GPU backend (`VulkanGuestGpuBackend` → `ExecuteOffscreenDraw` → `vkCmdDrawIndexed`)
- Vulkan presenter (`VulkanVideoPresenter` with swapchain, render pass, framebuffer)
- Shader recompiler (AGC Shader → SPIR-V)
- Memory manager, kernel semaphores, pthread mutex/cond
- PlayGo, AppContent, NpTrophy, etc.

The fork only adds the **headless rendering fix**, the **C11 sync exports**, and the **game-specific NID shims**. Everything else is upstream's work.

---

## Games Tested (with this fork)

| Game | TitleId | Status | Notes |
|---|---|---|---|
| Dreaming Sarah | PPSA02929 | ✅ First real image | 1,330 draws, 159 flips, 170 framebuffer dumps, splash → in-game transition visible |
| Arise | PPSA06328 | ⚠️ Partial boot | 7 missing NIDs added; crashes at `sem_init` MEMORY_FAULT (host pointer passed as guest address) |
| Harvest Days | PPSA14677 | ⚠️ Partial boot | 6 private NIDs stubbed; breaks out of init loop; crashes at `ayuoL6Vjz2k` (another private NID) |

---

## How to Run on Headless Linux (Xvfb + Lavapipe)

This is the configuration the fork was tested with. It does **not** require a physical GPU or a desktop environment.

```bash
# 1. Install dependencies (Debian/Ubuntu)
sudo apt-get install -y xvfb mesa-vulkan-drivers libglfw3 libffi8 \
    libegl1 libglx0 libopengl0 libdecor-0-0 \
    libwayland-client0 libwayland-cursor0 libwayland-egl1 \
    libxkbcommon0 libxrandr2 libxinerama1 libxi6 libxcursor1 libxrender1

# 2. Start Xvfb (no -terminate so it stays alive)
Xvfb :1 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset &

# 3. Set environment
export DISPLAY=:1
export XDG_RUNTIME_DIR=/tmp/xdg
mkdir -p /tmp/xdg
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json

# 4. Optional: capture framebuffers for verification
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR=/tmp/framebuffers
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1

# 5. Run
./SharpEmu /path/to/game/eboot.bin
```

Expected output (Dreaming Sarah, within ~5 seconds):
```
[LOADER][INFO] Linux X11 session detected; requested GLFW X11 backend explicitly.
[LOADER][INFO] GLFW windowing platform in use: X11
[LOADER][INFO] Vulkan device: llvmpipe (LLVM 19.1.7, 256 bits) (Cpu)
[LOADER][INFO] Vulkan VideoOut ready: 1920x1080, format=B8G8R8A8Srgb
[LOADER][INFO] Vulkan VideoOut presented first frame: 3840x2160
[LOADER][INFO] Vulkan VideoOut presented guest frame: image=0x0000000001260000 3840x2160
```

---

## Roadmap

### Short term (next 1–2 weeks)

1. **Arise `sem_init` MEMORY_FAULT** — investigate whether the guest is passing a host pointer or the HLE layer is mis-translating the argument. If it's a guest-side bug, patch the guest's memory layout; if it's an HLE bug, fix `PosixSemInit` to translate host pointers.
2. **Harvest Days `ayuoL6Vjz2k` crash** — identify the NID (likely another private Unity/IL2CPP primitive), add a stub, re-test.
3. **Cherry-pick upstream PR #433** (`sceKernelMapDirectMemory2`) — may resolve the `0x1FE000000` GPU memory mapping issue that Arise hits.

### Medium term (1–2 months)

4. **Compatibility Database** — auto-record per-game boot status, draw count, flip count, crash point, missing NIDs.
5. **Game-specific Debug Reports** — one-command bundle of logs, framebuffers, and metrics for a given game.
6. **Automated Regression Benchmarks** — after each commit, run 3 games and compare metrics to the previous commit.

### Long term (3+ months)

7. **More games reaching first frame** — target 10+ playable games.
8. **Shader recompiler correctness** — fix any SPIR-V translation bugs that produce visual artifacts.
9. **Audio** — currently silent; wire up ALSA/PulseAudio backend.

---

## Build

1. Install .NET SDK 10.0 (see `global.json`).
2. `git clone https://github.com/Sh-TB/sharpemuT24.git`
3. `cd sharpemuT24`
4. `dotnet build SharpEmu.slnx -c Release`
5. For a self-contained publish: `dotnet publish src/SharpEmu.CLI/SharpEmu.CLI.csproj -c Release -r linux-x64 --self-contained true -o ./build`

---

## Branches

- `main` — stable, mirrors upstream + fork-specific commits
- `integration/latest-upstream` — active development, tracks `upstream/main` + fork patches
- `backup-main-before-sync` — tag pointing to the pre-fork baseline

---

## Fork-Specific Commits (chronological)

| Date | Commit | Title |
|---|---|---|
| 2026-07-19 | `4a059f2` | fix(linux): always request X11 platform on Linux when DISPLAY is set |
| 2026-07-19 | `05b5137` | feat(libs): add C11 _Mtx_*/_Cnd_*/sincosf/srand/_ZSt14_Throw_C_errori exports |
| 2026-07-19 | `1429bbb` | feat(libs): add GameCompatExports for private NIDs (Harvest Days boot) |

---

## Disclaimer

SharpEmu is an experimental emulator intended for research and educational purposes.

This project does not contain any copyrighted system firmware, game data, or proprietary PlayStation assets.

All games used during development and testing are dumped from consoles that we personally own. Users are expected to use legally obtained copies of their games.

## License

[**GPL-2.0 license**](./LICENSE)

## Special Thanks

- **[ShadPS4](https://github.com/shadps4-emu/shadPS4)** — PS4 architecture reference
- **[Kyty](https://github.com/InoriRus/Kyty)** — PS5 emulator reference
- **Ryujinx** — C# filesystem patterns
- **upstream SharpEmu contributors** — without them this fork would have nothing to build on
