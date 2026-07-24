---
Task ID: EXP-018
Agent: main (SharpEmu bringup)
Task: Test whether SharpEmu has the Kyty-style scheduler pump problem.

Work Log:
- User asked: "Does SharpEmu, during Thread.Sleep(1), have any Guest Thread Ready that is not running?"
- If YES -> Kyty's KernelDispatchPendingSignalForCurrentThread approach would help.
- If NO -> the issue is elsewhere (IL2CPP, GPU queue, asset loader).

EXP-018 Steps 1-2 (Search for scheduler pump functions):
- Found SharpEmu already has all the Kyty-style scheduler functions:
  * WakeExpiredBlockedGuestThreads() in DirectExecutionBackend.cs:3235
  * DispatchReadyGuestThreads() in DirectExecutionBackend.cs:5827
  * Pump() method in DirectExecutionBackend.cs:3047
  * PumpUntilGuestThreadsIdle() in DirectExecutionBackend.cs:3268
- Pump() is called from:
  * sceKernelWaitEventFlag (KernelEventFlagCompatExports.cs:315)
  * sceKernelUsleep (KernelRuntimeCompatExports.cs:101)
  * sceKernelNanosleep (KernelRuntimeCompatExports.cs:2101)
  * Program.cs:128 (HostMainThread.Pump())
- CRITICAL FINDING: Pump() is NOT called from sceKernelWaitSema!

EXP-018 Step 3-4 (Add diagnostic logging, run Yatzi):
- Added logging in sceKernelWaitSema that prints READY/RUNNING/BLOCKED counts before blocking.
- Ran Yatzi for 60s. Output shows the classic Kyty problem pattern:
    READY=0  RUNNING=1  BLOCKED=0  (initial)
    READY=0  RUNNING=1  BLOCKED=1
    READY=0  RUNNING=1  BLOCKED=2
    READY=0  RUNNING=1  BLOCKED=3
    ...
    READY=0  RUNNING=1  BLOCKED=9
- 52 AssetGarbageCollectorHelper threads were scheduled, all blocking in sceKernelWaitSema
  at entry 0x800BB06A0 (inside eboot.bin).

EXP-018 Step 5 (Try adding scheduler.Pump() call):
- Added scheduler.Pump(ctx, "sceKernelWaitSema") call before RequestCurrentThreadBlock.
- Result: NO behavior change. Still splash frame, still 2 frames produced, still 71K imports.
- The Pump didn't help because READY was always 0 — there are no ready threads waiting to run.

Conclusion (answering user's main question):
- NO — SharpEmu does NOT have ready threads waiting to run during Thread.Sleep(1).
- The blocked threads are NOT waiting for the scheduler to pump; they are waiting for
  sceKernelSignalSema to be called — but no one calls it.
- The signaler logic is inside the game's IL2CPP code, which can't run correctly because
  SharpEmu uses fake IL2CPP stubs (returns NULL for il2cpp_class_from_name, etc.).
- -> Kyty's KernelDispatchPendingSignalForCurrentThread approach would NOT help SharpEmu.
- -> The real blocker is the missing IL2CPP runtime, not the scheduler pump.

Tested global-metadata.dat uploads:
- Yatzi: PPSA17697-app0-(Fix)MediaMetadata.rar (10.6 MB, magic 0xAF1BB1FA - newer IL2CPP format)
- Seeker: Seeker My Shadow 01.002 PPSA12500MediaMetadata.rar (6.0 MB, magic 0xAF1BB1FA)
- Extracted both to /tmp/games/{yatzi,seeker}/Media/Metadata/global-metadata.dat
- Yatzi coverage: 77.8% -> 83.3% (added global-metadata.dat)
- Seeker coverage: 83.3% -> 88.9% (added global-metadata.dat)
- BUT: SharpEmu does NOT actually read global-metadata.dat. It still uses fake IL2CPP stubs.
- Game still produces Unity splash frame (RGB 224,88,64, 99.98% coverage).

Stage Summary:
- EXP-018 confirmed: scheduler pump is NOT the issue. READY was always 0.
- Adding scheduler.Pump() to sceKernelWaitSema made no difference.
- The real blocker is missing IL2CPP runtime: SharpEmu uses fake stubs that return NULL,
  game's IL2CPP code can't initialize, game never calls sceKernelSignalSema.
- All required game files now uploaded for Yatzi (83.3% coverage) and Seeker (88.9%).
- Next: To get past Unity splash, SharpEmu needs to implement real IL2CPP metadata parsing
  (read global-metadata.dat and populate class registry from it).
- Left the diagnostic logging in sceKernelWaitSema for future use (throttled to first 20 calls).
