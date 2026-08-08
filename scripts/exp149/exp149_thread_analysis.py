#!/usr/bin/env python3
"""EXP-149 Step 3: Thread execution analysis — who should run PlayerLoop?"""

print("=" * 80)
print("EXP-149 Step 3: Thread Execution Analysis")
print("=" * 80)

print("""
Total threads: 15
  Main thread: 1
  AssetGarbageCollectorHelper: 13
  GC scavenger: 1

Thread Creation Order (from yatzi-devlog-fix.log):
  Lines 2805-2910: 13 AssetGarbageCollectorHelper threads created
    - All have entry=0x800BB06A0 (eboot address)
    - All have priority=700, affinity=0x7F
    - Created during IL2CPP type initialization (before mutex #38000)

  Line 2985: GC scavenger thread created
    - Entry=0x804F88AA0 (PRX address — Il2cppUserAssemblies.prx)
    - Priority=700, affinity=0x3C
    - Created AFTER all semaphores (0x7C-0x90) are set up
    - This is the LAST thread created before the deadlock

  Main thread: never explicitly "scheduled" — it's the original eboot thread
    - Entry=0x800000070 (eboot entry point)
    - Runs IL2CPP init, creates all semaphores, enters dispatch loop, blocks

Thread State at Deadlock:
  Main:         WaitSema(0x81) — rip=0x00006FFFFD001150 (import stub)
  AGC #1-13:    WaitSema(0x5C-0x74) — each on their own semaphore
  GC scavenger: WaitSema(0x83) = SuspendSemaphore

Key Question: Which thread should execute PlayerLoop registration?

ANALYSIS:

1. Main thread (eboot entry 0x800000070):
   - Executes the entire IL2CPP initialization sequence
   - Creates all worker semaphores (0x7C-0x90)
   - Creates the GC scavenger thread
   - Enters the dispatch loop at 0x804F6E510
   - Blocks on WaitSema(0x81)

   The main thread is the ONLY thread that can run PlayerLoop registration
   because:
   - It's the thread that runs IL2CPP init
   - PlayerLoop registration happens during IL2CPP init (before dispatch loop)
   - Worker threads (AGC) are created AFTER PlayerLoop should be registered
   - GC thread is created even later

2. AssetGarbageCollectorHelper threads (entry 0x800BB06A0):
   - These are WORKER threads that wait for jobs
   - They block on semaphores 0x5C-0x74 (their individual job semaphores)
   - They do NOT run initialization code
   - They are created by the main thread during IL2CPP type init
   - 13 threads = likely the Unity Job System worker pool

3. GC scavenger thread (entry 0x804F88AA0):
   - This is the IL2CPP garbage collector thread
   - Entry is in Il2cppUserAssemblies.prx (not eboot)
   - It blocks on SuspendSemaphore (0x83) — waiting to be resumed
   - The GC thread is the LAST thread created before deadlock
   - It does NOT run PlayerLoop registration

CONCLUSION:

The MAIN THREAD is the only thread that can execute PlayerLoop registration.
The main thread's execution path is:

  eboot entry (0x800000070)
    → IL2CPP init (dt_init at 0x804CD5010)
      → Type initialization (38000+ mutex calls)
      → Worker queue setup (semaphore creation)
      → GC thread creation
      → [MISSING: PlayerLoop registration]
      → [MISSING: Bootstrap job submission]
      → Dispatch loop entry (0x804F6E510)
        → WaitSema(0x81) → DEADLOCK

The PlayerLoop registration must happen on the main thread, AFTER the GC thread
is created and BEFORE the dispatch loop is entered.

The window is: GC thread creation (log line 2985) → dispatch loop entry (log line 2986+)

This is a VERY NARROW window — possibly just a few hundred instructions.
The single-step trace (Step 2) is designed to capture exactly this window.

Thread Start Addresses:
  Main:         0x800000070 (eboot) — PS5 process entry point
  AGC x13:      0x800BB06A0 (eboot) — Unity Baselib worker thread entry
  GC scavenger: 0x804F88AA0 (PRX)   — IL2CPP GC scavenger function

Thread Termination:
  NO threads have terminated at the time of deadlock.
  ALL 15 threads are blocked on WaitSema.
  No thread is in a "running" or "ready" state.

Root Cause Question: Who should signal semaphore 0x81?

Semaphore 0x81 (Baselib_SystemSemaphore) is the MAIN THREAD's work semaphore.
It should be signaled by the BOOTSTRAP JOB SUBMISSION code.

The bootstrap job submission should:
1. Increment the work counter [r14+0x90] (or [rbx+0x10])
2. Signal semaphore 0x81 to wake the main thread
3. The main thread then processes the bootstrap job

The bootstrap job submission code is the PRODUCER FUNCTION at 0x80015DCD0.
But this function has ZERO callers (confirmed in EXP-148 Step 3).

The bootstrap job submission should be called by PlayerLoop registration.
PlayerLoop registration should be called by the IL2CPP init sequence.
But PlayerLoop registration is SKIPPED.

WHO should call PlayerLoop registration?
→ The IL2CPP init sequence (dt_init at 0x804CD5010) should call it.

WHY is it skipped?
→ This is the root cause we need to find with the single-step trace.

The single-step trace will show the EXACT instruction where the IL2CPP init
sequence decides to skip PlayerLoop registration and go directly to the
dispatch loop.
""")
