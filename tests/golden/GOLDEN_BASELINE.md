# SharpEmuT24 Golden Baseline Rule v1.0

## Golden Baseline

```
Tag:        golden-render-baseline
Commit:     f83b6ea
Release:    v0.0.9
Date:       2026-07-24
```

## Golden Test Game

```
Game:       Dreaming Sarah (PPSA02929)
Engine:     Native C++
Required:   100+ framebuffer dumps with 50+ distinct colors
```

## Rule

> Every change to SharpEmuT24 must pass the Dreaming Sarah golden test
> before it can be merged to main.

### What "pass" means

1. Dreaming Sarah boots (no crash within 30s)
2. VulkanVideoPresenter activates (not HeadlessVideoPresenter)
3. GLFW X11 backend selected
4. 100+ framebuffer dumps produced
5. At least one frame has 50+ distinct colors (real game content)

### What "fail" means

- Any of the above conditions not met
- The change is rejected and must be reverted or fixed

## Test Command

```bash
./tests/golden/run-golden-tests.sh
```

## Game Status Matrix (as of v0.0.9)

| # | Game | Engine | Status | Blocker |
|---|------|--------|--------|---------|
| 1 | Dreaming Sarah | Native C++ | ✅ GOLDEN | None |
| 2 | Yatzi (PPSA17697) | Unity IL2CPP | ❌ | VkqLPArfFdc NID unresolved |
| 3 | Seeker My Shadow (PPSA12500) | Unity IL2CPP | ❌ | VkqLPArfFdc NID unresolved |
| 4 | Arise (PPSA06328) | Native C++ | ❌ | SIGILL crash |
| 5 | Harvest Days (PPSA14677) | Unity IL2CPP | ❌ | Encrypted PRX files |

## Development Phases

### Phase 1 — Freeze Renderer (CURRENT)
- ❌ No changes to Vulkan/VideoOut/AGC
- Dreaming Sarah must stay green

### Phase 2 — Unity IL2CPP (NEXT)
- Resolve VkqLPArfFdc NID
- Target: Yatzi + Seeker reach render loop

### Phase 3 — Native Crash
- Investigate Arise SIGILL

### Phase 4 — Encrypted Games
- Harvest Days needs decrypted PRX files

## Mistakes Documented (Do Not Repeat)

1. **HSV test pattern confused with game output**
   - GenerateFramePattern() produced RGB(229,95,68) = HSV(10°,0.7,0.9)
   - This was SharpEmu's test pattern, NOT game rendering
   - Fix: Always check distinct color count, not just "frame exists"

2. **Six false hypotheses that wasted days**
   - ❌ Scheduler pump issue (READY was always 0)
   - ❌ Semaphore deadlock (4831 signals happened)
   - ❌ Metadata corruption (entropy 5.54, valid)
   - ❌ Missing game files (Seeker had all files)
   - ❌ Fake IL2CPP stubs returning NULL (game didn't use them)
   - ❌ Regression between versions (v0.0.3 was also all-black)

3. **The real fix was one function**
   - PreferX11OnLinuxWayland() needed to request X11 when DISPLAY is set
   - Not just when WAYLAND_DISPLAY is set
   - This was PR #457 which wasn't merged to main

4. **Multiple systems changed simultaneously**
   - Never change HLE + GPU + VideoOut + Memory at the same time
   - One subsystem per change, then test

## NID Coverage Comparison (old working source vs current)

Old working source (e3bbe69, 2026-07-19):
- Total unique NIDs: 1029
- AgcExports NIDs: 93

Current source (f83b6ea):
- Total unique NIDs: 911
- AgcExports NIDs: 90

Missing: 133 NIDs (old has, current doesn't)
Added: 15 NIDs (current has, old doesn't — our custom stubs)

Key finding: VkqLPArfFdc is NOT in either source.
It's genuinely unimplemented — Unity IL2CPP games call it during bootstrap.
Dreaming Sarah (native C++) never calls it, which is why it works.

## Next Steps for Unity IL2CPP (Phase 2)

1. Port 133 missing NIDs from old source to current
2. Identify VkqLPArfFdc — likely an IL2CPP runtime function
3. Implement VkqLPArfFdc stub that returns allocated memory (not NULL)
4. Run golden test after each change to verify Dreaming Sarah still works
5. Test Yatzi/Seeker after NID work — do they reach AGC?
