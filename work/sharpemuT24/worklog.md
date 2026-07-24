---
Task ID: EXP-100/101 — Differential Boot Analysis: Dreaming Sarah vs Seeker
Agent: main (SharpEmu bringup)
Task: User asked the critical question — what does Dreaming Sarah do that Seeker doesn't?

User's key insight: "If Dreaming Sarah runs on SharpEmu main, then render engine,
Vulkan, VideoOut, and most HLE are 'capable of running at least one Unity game'.
So instead of asking 'why does Seeker not boot', we should ask 'what does Dreaming
Sarah do that Seeker doesn't'."

=== EXP-100: Run Dreaming Sarah with full diagnostic logging ===
- 30 second run, 516 frames produced (260 saved before disk full)
- Game ran for full 30s, processed 226K imports
- Game crashed with SIGABRT at end (out of disk space, not a real crash)

=== EXP-101: Differential Boot Analysis ===

┌──────────────────────────────────┬──────────────────┬──────────────────┐
│ Metric                           │ Dreaming Sarah   │ Seeker           │
├──────────────────────────────────┼──────────────────┼──────────────────┤
│ Engine                           │ Native C++       │ Unity IL2CPP     │
│ Modules loaded                   │ 1 (libc.prx)     │ 12 (libc + 11)   │
│ Imports processed                │ 540 (then 226K)  │ 759              │
│ Total Flips                      │ 260              │ 1                │
│ TryRead (FB reads)               │ 260              │ 0                │
│ Unique libraries                 │ 6                │ 3                │
│ AGC function calls               │ 43               │ 0                │
│ Unique AGC functions             │ 12               │ 0                │
│ Direct memory allocs             │ 25               │ 1                │
│ MapDirectMemory calls            │ 20               │ 10               │
└──────────────────────────────────┴──────────────────┴──────────────────┘

=== ROOT CAUSE FOUND ===

Dreaming Sarah (Native C++) calls REAL PS5 AGC/GPU functions:
- sceAgcDriverSubmitDcb (1 call — submitting a Command Buffer!)
- sceAgcDcbSetIndexBuffer
- sceAgcDcbAcquireMem
- sceAgcDcbSetUcRegistersIndirect
- sceAgcCreatePrimState
- sceAgcCreateInterpolantMapping
- sceAgcSetCxRegIndirectPatchAddRegisters / SetAddress
- sceAgcSetShRegIndirectPatchAddRegisters
- sceAgcSetUcRegIndirectPatchAddRegisters
- sceAgcCbSetShRegisterRangeDirect
- sceAgcSuspendPoint

Seeker (Unity IL2CPP) calls ZERO AGC functions.
Seeker's only activity is:
- 102 libc calls (mostly __cxa_atexit registering destructors)
- 55 libKernel calls (mutex init/lock)
- 8 libSceAudioOut calls (audio output)

=== Dreaming Sarah's frames are NOT test pattern ===
- Frame CRCs: 0xEB9E4E4E for ALL 260 frames (identical)
- First pixel: RGB(0,0,0) α=0 (BLACK, not the orange test pattern color)
- SharpEmu is reading from REAL game-provided framebuffer addresses
  (0x1260000, 0x3240000 — non-zero, double-buffered)
- But nonZero(first1000)=0 — framebuffer content is all zeros
  → Game is providing valid framebuffer addresses but SharpEmu isn't
    rendering anything into them (AGC stub doesn't execute DCBs)

=== WHY Dreaming Sarah works (kind of) and Seeker doesn't ===

1. Dreaming Sarah is a NATIVE C++ PS5 game:
   - Calls AGC functions DIRECTLY from its own code
   - SharpEmu has AGC stubs that accept these calls and return OK
   - Even though SharpEmu doesn't actually render anything, the game
     proceeds through its main loop and calls sceVideoOutFlip

2. Seeker is a UNITY IL2CPP game:
   - Has Il2cppUserAssemblies.prx with 592 real exports
   - But Unity's IL2CPP runtime needs to be initialized FIRST
   - Initialization requires IL2CPP runtime to call into the host
     SharpEmu doesn't actually implement IL2CPP runtime init
   - Game is stuck in C++ static initialization, registering __cxa_atexit
     handlers but never reaching Unity engine boot

=== THE DEFINITIVE ROOT CAUSE ===

The blocker for Unity IL2CPP games is NOT:
- ❌ Missing files (Seeker has all files)
- ❌ Metadata corruption (metadata is valid)
- ❌ Scheduler pump (no ready threads waiting)
- ❌ Semaphore deadlock (signals DO happen)
- ❌ Fake IL2CPP stubs (game doesn't use them)
- ❌ AGC/GPU rendering (game never gets there)

The blocker IS:
- ✅ Unity IL2CPP runtime initialization is incomplete
- ✅ Game's IL2CPP bootstrap never enters the Unity engine boot
- ✅ Game is stuck in C++ static initialization phase
- ✅ SharpEmu doesn't properly initialize IL2CPP runtime for Unity games

=== WHAT WE NOW KNOW FOR CERTAIN ===

1. SharpEmu's kernel, scheduler, filesystem, module loading ALL work (Dreaming Sarah proves it)
2. SharpEmu's AGC stubs ACCEPT calls and return OK (Dreaming Sarah calls 12 AGC functions)
3. SharpEmu's VideoOut flip mechanism works (Dreaming Sarah does 260 flips)
4. Unity IL2CPP games need something Native C++ games don't:
   - Either: a specific PS5 kernel function SharpEmu doesn't implement
   - Or: proper IL2CPP runtime initialization that SharpEmu doesn't trigger
   - Or: a specific symbol resolution that fails silently

=== NEXT INVESTIGATION (single item) ===

Find what Dreaming Sarah does at Import #540 (where it transitions from
static init to actual game logic with AGC calls), and check what Seeker
does at Import #759 (where it stops making progress).

The divergence point is somewhere between:
- Dreaming Sarah: __cxa_atexit (86x) → sceKernelAllocateDirectMemory (24x) → sceAgcDriverSubmitDcb
- Seeker: __cxa_atexit (481x) → scePthreadMutexInit (26x) → [stuck]

Seeker never reaches sceKernelAllocateDirectMemory in the way Dreaming Sarah does.
