# Last Known Good State (Permanent — Never Delete)

## DO NOT GO BELOW THIS POINT

Commit: f54a404
Date: 2026-07-22T20:40:00Z
Build: SharpEmu 53MB single-file linux-x64

## Game Status at This Commit

| Game | Status | First Frame | Notes |
|------|--------|-------------|-------|
| Dreaming Sarah | ✅ PASS | ✅ 3840x2160 (guest frame) | Golden test — must not break |
| Arise | ✅ PASS | ✅ 3840x2160 (splash) | GPU pipeline working |
| Harvest Days | 🟡 RUNNING | ❌ | Import ~948, NULL rec 15, IL2CPP block |
| New Game | 🟡 RUNNING | ❌ | NULL rec 1005, IL2CPP block |

## How to Reproduce

```bash
# Environment
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_SEMA_FAST_PATH=1

# Dreaming Sarah
export SHARPEMU_APP0_DIR=/home/z/my-project/upload/PPSA02929/PPSA02929-app0
./work/sharpemu-build/SharpEmu --log-level=info upload/PPSA02929/PPSA02929-app0/eboot.bin
# Expected: "Vulkan VideoOut presented first frame: 3840x2160"
# Expected: "Vulkan VideoOut presented guest frame: image=0x... 3840x2160"

# Arise
export SHARPEMU_APP0_DIR=/tmp/arise-app0
# (ensure save data + dummy game data files exist)
./work/sharpemu-build/SharpEmu --log-level=info /tmp/arise-app0/eboot.bin
# Expected: "Vulkan VideoOut presented first frame: 3840x2160"
```

## Key Files at This State

- Source: `work/sharpemuT24/src/` (all C# projects)
- Build: `work/sharpemu-build/SharpEmu` (53MB single-file)
- Archive: `download/SharpEmuT24-bringup-current-2026-07-22-2040.tar.gz`
- Tags: `milestone/2-games-first-frame`, `milestone/pr542-applied`

## Key Changes Applied

1. IL2CPP fake heap (64KB + vtable + fake objects + per-function stubs)
2. NULL execute fault recovery (redirect to return-zero stub)
3. Unmapped memory read/write recovery (Iced decode + skip)
4. AGC auto-init for sceAgcDriverRegisterOwner
5. Sema fast path (SHARPEMU_SEMA_FAST_PATH=1)
6. C11SyncExports.cs (_Mtx_init, _Cnd_init, srand)
7. PR #542: MessengerCompatExports (time, cosf, puts, _Getptolower, _Getptoupper)
8. PR #542: _Execute_once (DiGVep5yB5w) for Unity static init
9. PR #542: IL2CPP dispatch fix (return resolvedAddress instead of 0)
10. 3 Arise NID stubs (McaImWKXong, bRujIheWlB0, Cj+Fw5q1tUo)

## Next Priority

1. Harvest Days → VideoOut (IL2CPP runtime)
2. New Game → VideoOut (same IL2CPP fix)
3. Arise → Gameplay (asset loading pipeline)
4. Keep Dreaming Sarah regression
