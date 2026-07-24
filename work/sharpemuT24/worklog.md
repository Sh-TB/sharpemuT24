---
Task ID: EXP-041 to EXP-058 (Vulkan/GNM/AGC audit + Framebuffer CRC)
Agent: main (SharpEmu bringup)
Task: User asked for definitive answer on whether game produces any draw calls.

User asked the critical question:
> "Before building AGC Parser, prove the game produces at least one DRAW command.
> If DRAW_INDEX = 0, building AGC parser is wasted time."
> If DRAW_INDEX > 0 but vkCmdDraw = 0, then AGC→Vulkan translation is the work.

=== EXP-041: Vulkan Pipeline Audit ===
ALL Vulkan calls = ZERO:
- vkCreateInstance: 0
- vkCreateDevice: 0
- vkCreateSwapchain: 0
- vkCreateRenderPass: 0
- vkCreateFramebuffer: 0
- vkCreateGraphicsPipeline: 0
- vkCmdBindPipeline: 0
- vkCmdDraw: 0
- vkCmdDrawIndexed: 0
- vkQueueSubmit: 0
- vkQueuePresentKHR: 0

=== EXP-042/058: AGC/GNM Command Coverage ===
ALL GNM/AGC calls from game = ZERO:
- sceGnmSubmitCommandBuffers: 0
- sceGnmxSubmit: 0
- sceAgcSubmitDcb: 0
- sceAgcSubmitDcb1/2: 0
- sceAgcDcbDrawIndex: 0
- sceVideoOutSubmitFlip: 0
- sceVideoOutRegisterBuffers: 0

Only sceVideoOutOpen was called (1 time) — to register a display handle.

=== EXP-051: Framebuffer CRC ===
Only ONE frame produced (frame000001.ppm).
- CRC32: 0x6516E746
- First pixel: RGB(229,95,68) α=255

VERIFICATION: This color (229,95,68) is NOT from the game!
It's from SharpEmu's HeadlessVideoPresenter.GenerateFramePattern():
  hue = (frame * 10) % 360  // = 10 for frame 1
  HSV(h=10°, s=0.7, v=0.9) → RGB(229,95,68)  ← EXACT MATCH

The "Unity splash frame" we've been celebrating for the past 6+ experiments
is SharpEmu's SYNTHETIC TEST PATTERN, not game output!

=== EXP-050: DCB Replay Audit ===
- DCB received: 0 (game never submitted any DCB)
- DCB parsed: 0
- DCB executed: 0
- Framebuffer changed: only by SharpEmu's GenerateFramePattern()

=== EXP-049: GPU Memory Audit ===
- Game never called sceKernelMapDirectMemory for GPU memory
- Game never allocated any GPU resources
- Only CPU memory was allocated

=== EXP-044: Pipeline State ===
- No pipeline state exists — no graphics pipeline was ever created

=== Game activity breakdown (top imports) ===
The game's actual activity in 30s of execution (200K imports total):
- 481 calls: libc:__cxa_atexit (C++ static destructors registration)
- 33 calls: libKernel:scePthreadMutexLock
- 26 calls: libKernel:scePthreadMutexInit
- 25 calls: libKernel:scePthreadMutexattrInit/Destroy/Settype
- 14 calls: libKernel:scePthreadMutexattrSetprotocol
- 9 calls: libKernel:sceKernelCreateSema
- 5 calls: libKernel:sceKernelGetProcParam

The game is stuck in C++ static initialization phase. It's registering
atexit handlers and creating mutexes — that's it. It has NOT yet:
- Opened the display (1 call only to sceVideoOutOpen)
- Allocated GPU memory
- Created any render targets
- Submitted any command buffers
- Drawn anything

=== ROOT CAUSE (DEFINITIVE) ===

The game is stuck in the EARLY C++ initialization phase, not in the render loop.

The "Unity splash frames" we've been generating are NOT game output — they're
SharpEmu's HeadlessVideoPresenter.GenerateFramePattern() test pattern. The color
RGB(229,95,68) is HSV(h=10°, s=0.7, v=0.9) computed from frame number 1.

Evidence:
1. Game calls ZERO sceVideoOut/sceAgc/sceGnm functions
2. Game's only activity is __cxa_atexit + mutex initialization
3. Only ONE flip happened, at t=0.04s (SharpEmu's initialization, not game's)
4. The frame color matches SharpEmu's test pattern formula exactly
5. No GPU memory was ever allocated by the game

=== WHAT THIS MEANS ===

1. Building AGC parser is PREMATURE — game never submits any DCB
2. The real blocker is earlier than GPU: game's IL2CPP runtime initialization
   is stuck somewhere in C++ static init, before the Unity engine boots
3. The "5 games with first frame" milestone was a false positive — those
   frames were all SharpEmu's test pattern, not game output

=== NEXT STEP (single item) ===

The real blocker is: why is the game stuck in C++ static init / early IL2CPP setup?
- The game registers 481 atexit handlers (way too many — typical is 50-100)
- It creates 9 semaphores and many mutexes
- It calls sceKernelGetProcParam 5 times
- But it NEVER calls into the real Unity/IL2CPP runtime entry point

Hypothesis: The game's IL2CPP runtime needs something SharpEmu doesn't provide.
Possible candidates:
- il2cpp_init() returns failure (game can't see this in our logs)
- The game's bootstrap expects a function that returns NULL
- A specific PS5 kernel function is missing

The next investigation should be:
- Trace what the game does AFTER all those __cxa_atexit calls
- Find the first import call that doesn't return success
- Look for il2cpp_init() or similar in Il2cppUserAssemblies.prx
