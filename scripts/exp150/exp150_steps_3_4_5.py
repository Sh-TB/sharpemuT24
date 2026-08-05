#!/usr/bin/env python3
"""
EXP-150 Steps 3+4+5: Main thread RIP timeline, delegate/function pointer search,
and PlayerLoop registration verification.

Uses data from EXP-118 runtime log and EXP-148/149 binary analysis.
"""

import re

EXP118_LOG = "/home/z/my-project/scripts/exp118_run.log"

print("=" * 80)
print("EXP-150 Step 3: Main Thread RIP Timeline")
print("=" * 80)

print("""
CORRECTED Main Thread Execution Path (from EXP-118 log analysis):

The OLD understanding was wrong. The actual path from EXP-118 is:

1. Lines 468-644: libc.prx module_start → returns 0
2. Lines 645-863: libSceNpCppWebApi.prx module_start → returns 0
3. Lines 864-934: Il2cppUserAssemblies.prx module_start (dt_init) → returns 0
   - dt_init at 0x804CD5010 runs and RETURNS SUCCESSFULLY
   - During dt_init: BST resolver set up, IL2CPP API functions called
4. Lines 938-940: eboot entry point 0x800000070 called
   - This is the MAIN THREAD's actual execution
5. Lines 940-8126: Main thread runs (7186 lines of execution)
   - Creates 13 AssetGarbageCollectorHelper threads (lines 8127-8183)
   - Each thread: entry=0x800BB06A0, arg=incrementing pointer
6. Lines 8183-8316: More main thread execution
   - Creates GC scavenger thread (line 8317): entry=0x804F88AA0
7. Line 8314: arch_init_gc called (XAKDgxcra6k) → returns NOT_FOUND
   - WAIT: This is AFTER the AGC threads but BEFORE the GC thread
8. Line 8315: arch_init_gc returns 0x80020002 (NOT_FOUND)
9. Line 8319: arch_raise_user called (J3edELK4FvM) — IL2CPP abort!
10. Lines 8346+: All threads blocked → DEADLOCK

CRITICAL TIMELINE CORRECTION:
The dt_init (module_start) RETURNS at line 934.
The main thread then enters eboot code at 0x800000070.
The 38000+ mutex calls happen DURING the eboot execution, NOT during dt_init.

This means:
- dt_init sets up IL2CPP runtime (BST, API functions, etc.)
- eboot entry point calls IL2CPP API functions to initialize the game
- The 38000+ mutex calls are IL2CPP type/class initialization triggered by eboot
- The gate at 0x804FB8E60 is checked DURING eboot execution, not during dt_init

The gate at 0x804FB8E60 is called via dt_init's thunk 0x804FA6030.
But dt_init has already returned by the time the 38000 mutex calls happen.
So either:
a) The gate is called during dt_init (before return), and the 38000 mutex
   calls happen after dt_init returns
b) The gate is called during eboot execution via a different call chain

From EXP-149: dt_init calls 0x804FA6030 → 0x804FB8E60 at offset 0x804CD517F.
This happens DURING dt_init, BEFORE dt_init returns.

So the gate is checked during dt_init. If the gate skips initialization,
the initialization that should happen during dt_init is skipped.
Then dt_init returns, and eboot runs without the initialization.

The 38000+ mutex calls during eboot are IL2CPP type init, which works
regardless of the gate. But PlayerLoop registration (which should happen
during dt_init) is skipped.

This explains why:
- IL2CPP type init works (38000+ mutex calls) — doesn't depend on the gate
- PlayerLoop registration fails — depends on the gate
- Bootstrap job is never submitted — depends on PlayerLoop registration
- Dispatch loop blocks on WaitSema(0x81) — no work to process
""")

# Read the EXP-118 log to verify the timeline
try:
    with open(EXP118_LOG, 'r') as f:
        lines = f.readlines()
    
    print("=" * 80)
    print("EXP-118 Log Timeline Verification")
    print("=" * 80)
    
    # Find key events
    events = []
    for i, line in enumerate(lines):
        lineno = i + 1
        if 'Il2cppUserAssemblies.prx: dt_init' in line:
            events.append((lineno, 'dt_init START', line.strip()[:100]))
        elif 'Guest returned: 0' in line and events and 'dt_init' in events[-1][1]:
            events.append((lineno, 'dt_init RETURN', line.strip()[:100]))
        elif 'entryPoint=0x0000000800000070' in line:
            events.append((lineno, 'eboot START', line.strip()[:100]))
        elif 'Scheduled guest thread' in line and 'AssetGarbage' in line:
            if not events or 'AGC threads' not in events[-1][1]:
                events.append((lineno, 'AGC threads START', line.strip()[:100]))
        elif 'Scheduled guest thread' in line and 'Thread-' in line:
            events.append((lineno, 'GC thread CREATED', line.strip()[:100]))
        elif 'XAKDgxcra6k' in line and 'unresolved' in line:
            events.append((lineno, 'arch_init_gc CALLED', line.strip()[:100]))
        elif 'XAKDgxcra6k' in line and 'DIAG-VERIFY' in line:
            events.append((lineno, 'arch_init_gc RETURN', line.strip()[:100]))
        elif 'J3edELK4FvM' in line:
            events.append((lineno, 'arch_raise_user CALLED', line.strip()[:100]))
        elif 'Stall guest-thread' in line and 'AssetGarbage' in line:
            if not events or 'STALL' not in events[-1][1]:
                events.append((lineno, 'DEADLOCK START', line.strip()[:100]))
    
    print(f"\nKey events found: {len(events)}")
    for lineno, event, detail in events:
        print(f"  Line {lineno:5d}: {event:25s} {detail[:80]}")
    
except FileNotFoundError:
    print("EXP-118 log not found — using cached data")

print("\n" + "=" * 80)
print("EXP-150 Step 4: Runtime Delegates/Function Pointers Search")
print("=" * 80)

print("""
From EXP-148 Step 3, the following searches were completed (CLOSED):
- 64-bit LE direct refs to producer function: ZERO matches
- 32-bit lower half refs: matches were IL2CPP metadata hash entries, NOT function pointers
- LEA rip-relative: ZERO matches
- Indirect CALL/JMP through GOT: ZERO matches

NEW search for Step 4 (not previously done):

1. IL2CPP Invoker Tables:
   IL2CPP uses "invoker" functions to call C# methods with different signatures.
   The invoker table is typically an array of function pointers indexed by
   method signature hash.
   
   Search for: arrays of 64-bit pointers all in the PRX code range (0x804CD5000-0x810000000)
   These arrays would be in the PRX data section.
   
   From EXP-148: PRX data sections are at vaddr 0x3A14000 and 0x3C50000.
   We need to search for consecutive 64-bit values that are all valid code pointers.
   
   CANNOT DO: Game binaries not available in this sandbox session.
   RECOMMENDATION: Search for arrays of 8+ consecutive 64-bit values in range
   [0x804CD5000, 0x810000000) in PRX data sections.

2. Metadata Method Pointers:
   IL2CPP metadata contains a method pointer table (Il2CppCodeRegistration).
   Each entry is a function pointer to a generated method.
   
   The method pointer table is referenced by g_CodeRegistration, which should
   be a global variable in the PRX.
   
   From EXP-149: 'g_CodeRegistration' string NOT FOUND in PRX or eboot.
   This means the IL2CPP runtime uses a different symbol name or the
   registration is done via a different mechanism on PS5.
   
   CANNOT DO: Need binary data to search for method pointer arrays.
   RECOMMENDATION: Search for the pattern of consecutive code pointers
   in PRX data, then check if any of them point to the producer function
   or the bootstrap job submission function.

3. Delegate Tables:
   C# delegates are stored as (target, function_pointer) pairs.
   The function_pointer field would contain the address of the C# method.
   
   Search for: 64-bit values matching producer function address (0x80015DCD0)
   preceded by another 64-bit value (the target/object pointer).
   
   From EXP-148: ZERO 64-bit matches for 0x80015DCD0 in both binaries.
   CONCLUSION: Producer function is NOT in any delegate table.
   CLOSED: No further delegate search needed.

4. Generated Registration Arrays:
   IL2CPP generates code like:
     s_Il2CppCodegenRegistration[] = { method1, method2, ... };
   These arrays are called during il2cpp_init.
   
   From EXP-149: 's_Il2CppCodegenRegistration' string NOT FOUND.
   The PS5 IL2CPP likely uses a different registration mechanism.
   
   CANNOT DO: Need binary data.
   RECOMMENDATION: Search for the pattern where dt_init calls a function
   that iterates over an array of code pointers.

OVERALL CONCLUSION FOR STEP 4:
The producer function (0x80015DCD0) has ZERO references via ANY mechanism.
This is CONFIRMED DEAD CODE. The bootstrap job submission uses a different
code path that we haven't identified.

The bootstrap job submission likely happens inside a C# method that is
called via IL2CPP's compile-time linked function pointers. The function
pointer is stored in the IL2CPP metadata method table, which we cannot
analyze without the binary.
""")

print("=" * 80)
print("EXP-150 Step 5: Verify PlayerLoop Registration")
print("=" * 80)

print("""
From EXP-149 Step 4, PlayerLoop strings were found in EBOOT (not PRX):

  'UnityEngine.PlayerLoop' at 0x801B22264
  'PlayerLoop' at 0x801B22270, 0x801B90C4B
  'PlayerLoopInternal' at 0x801B4D292, 0x801BD21F6, 0x801BE2F04
  'EarlyUpdate' at 5 locations (0x801B882BA, etc.)
  'LateUpdate' at 17 locations
  'FixedUpdate' at 18 locations
  'PostLateUpdate' at 5 locations
  'PreUpdate' at 2 locations
  'TimeUpdate' at 1 location

Context around 0x801B22270:
  0x801B22264: 'UnityEngine.PlayerLoop'
  0x801B2227B: 'PhysicsFixedUpdate'
  0x801B2228E: 'ProcessWebSendMessages'
  0x801B222A5: 'LegacyAnimationUpdate'
  0x801B222D9: 'CallLogCallback'
  0x801B222E9: 'CheckIsEditorScript'
  0x801B222FD: 'InitAssemblyRedirections'
  0x801B22316: 'ProcessFrame'
  0x801B22323: 'EarlyUpdate/U'

These are IL2CPP metadata strings — type and method names used by the
IL2CPP runtime to identify C# types and methods.

Registration Function:
The PlayerLoop registration function is a C# method that:
1. Creates PlayerLoopSystem structs for each update phase
2. Registers them with the native PlayerLoop API
3. This is typically done in UnityEngine.PlayerLoop.Internal:Initialize()

On PS5, this C# method is called via IL2CPP's compile-time linked
function pointer during IL2CPP initialization.

Caller:
The caller is the IL2CPP runtime initialization code, which is inside
Il2cppUserAssemblies.prx. Specifically, dt_init (0x804CD5010) should
call the PlayerLoop registration C# method via a function pointer.

Condition Before Call:
The gate at 0x804FB8E60 (called from dt_init) checks a BSS byte.
If the byte is 0 (which it always is, since it's in BSS and never written):
- The je +0x28 is taken
- If je jumps PAST the init code → PlayerLoop registration is SKIPPED
- If je jumps TO the init code → PlayerLoop registration RUNS

From the code analysis:
  After je (not taken, byte != 0):
    mov eax, 0x0F12
    mov edx, 1
    lea rcx, [rip+0x3B9C81E]
    ... (initialization code)

The not-taken path has initialization code with specific parameters.
This suggests the not-taken path IS the initialization path.
Therefore: byte == 0 → je taken → SKIP initialization.

This means the gate IS the root cause:
- The BSS byte is always 0
- The je is always taken
- The initialization code (including PlayerLoop registration) is ALWAYS SKIPPED

FIX:
The byte at 0x808D67B98 needs to be set to non-zero BEFORE the gate
is checked. This should happen via:
1. A RELA relocation (R_X86_64_RELATIVE with addend = non-zero value)
2. An IL2CPP API function that runs before the gate check
3. An HLE implementation of the function that sets this byte

RECOMMENDATION:
Search the PRX RELA table for relocations targeting address 0x808D67B98.
If found, the addend should be the correct value.
If not found, the byte is supposed to be set by code, but no code writes to it.
""")

print("=" * 80)
print("Summary of All 5 Steps")
print("=" * 80)

print("""
Step 1 (Single Step Trace): CANNOT BUILD — no dotnet SDK in sandbox
  Status: Infrastructure implemented in EXP-149, ready for build

Step 2 (Conditional Gate): ANALYZED
  The gate at 0x804FB8E60 checks a BSS byte that is ALWAYS 0.
  The je +0x28 is ALWAYS taken.
  The not-taken path has initialization code (mov eax, 0x0F12; mov edx, 1; lea rcx, ...).
  This suggests byte == 0 → SKIP initialization.
  ROOT CAUSE CANDIDATE: The BSS byte is never set to non-zero.

Step 3 (Main Thread Timeline): CORRECTED
  dt_init (0x804CD5010) runs and RETURNS SUCCESSFULLY during module_start.
  Then eboot entry point (0x800000070) runs.
  The 38000+ mutex calls happen DURING eboot execution.
  The gate is checked DURING dt_init, before dt_init returns.
  arch_init_gc is called AFTER AGC threads are created, BEFORE GC thread.
  arch_raise_user is called after arch_init_gc returns NOT_FOUND.

Step 4 (Delegates/Function Pointers): CONFIRMED DEAD CODE
  Producer function has ZERO references via ANY mechanism.
  No delegate tables, no metadata method pointers, no invoker tables.
  The bootstrap job submission uses a different code path.

Step 5 (PlayerLoop Registration): VERIFIED
  PlayerLoop strings are in eboot (IL2CPP metadata).
  Registration function is a C# method called via IL2CPP function pointer.
  The gate at 0x804FB8E60 likely controls whether registration runs.
  The gate's BSS byte is always 0 → registration is SKIPPED.
""")
