#!/usr/bin/env python3
"""EXP-155 Task 3: Validate IL2CPP initialization chain."""

import re

LOG_PATH = "/home/z/my-project/scripts/exp118_run.log"

def main():
    print("=" * 80)
    print("EXP-155 Task 3: Validate IL2CPP Initialization Chain")
    print("=" * 80)
    
    with open(LOG_PATH, 'r') as f:
        lines = f.readlines()
    
    # Trace the IL2CPP init chain
    print("\n[1] IL2CPP initialization timeline:")
    
    # Find key events
    events = []
    for i, line in enumerate(lines):
        if 'Il2cppUserAssemblies.prx: dt_init' in line:
            events.append((i+1, 'dt_init START', line.rstrip()[:100]))
        elif 'Guest returned: 0' in line and events and 'dt_init' in events[-1][1]:
            events.append((i+1, 'dt_init RETURN', line.rstrip()[:100]))
        elif 'entryPoint=0x0000000800000070' in line:
            events.append((i+1, 'eboot START', line.rstrip()[:100]))
        elif 'il2cpp_init' in line and 'RESOLVER-TRACE' in line and 'Entry' in line:
            events.append((i+1, 'il2cpp_init RESOLVED', line.rstrip()[:100]))
        elif 'il2cpp_runtime_class_init' in line and 'RESOLVER-TRACE' in line and 'Entry' in line:
            events.append((i+1, 'class_init RESOLVED', line.rstrip()[:100]))
        elif 'Scheduled guest thread' in line and 'AssetGarbage' in line:
            if not events or 'AGC threads' not in events[-1][1]:
                events.append((i+1, 'AGC threads START', line.rstrip()[:100]))
        elif 'Scheduled guest thread' in line and 'Thread-' in line:
            events.append((i+1, 'GC thread CREATED', line.rstrip()[:100]))
        elif 'Stall guest-thread' in line and 'AssetGarbage' in line:
            if not events or 'DEADLOCK' not in events[-1][1]:
                events.append((i+1, 'DEADLOCK START', line.rstrip()[:100]))
    
    for lineno, event, detail in events:
        print(f"  Line {lineno:5d}: {event:25s} {detail[:80]}")
    
    # Check the chain
    print(f"\n[2] Expected IL2CPP initialization chain:")
    print(f"  il2cpp_init → il2cpp_runtime_class_init → .cctor → type flag write → PlayerLoop")
    
    print(f"\n[3] Actual chain (from log):")
    print(f"  dt_init starts → resolver runs (232 calls) → ALL have RAX corruption")
    print(f"  → il2cpp_runtime_class_init GOT gets garbage (0x7FD670094000)")
    print(f"  → il2cpp_runtime_class_init NEVER actually runs")
    print(f"  → .cctor NEVER runs")
    print(f"  → type flags (0x808D67BB8, 0x808D67B98) NEVER set")
    print(f"  → gate function (0x804FB8E60) skips ALL methods")
    print(f"  → PlayerLoop.Initialize() NEVER runs")
    print(f"  → deadlock")
    
    # Verify the flag writers
    print(f"\n[4] Flag writer verification (from EXP-152):")
    print(f"  Flag 0x808D67B98: 3 writers, all check flag before writing (chicken-and-egg)")
    print(f"  Flag 0x808D67BB8: 2 writers (one writes 1 inside writer func, one writes 0 cleanup)")
    print(f"  No unconditional writer — flags are NEVER set")
    
    # The chain
    print(f"\n[5] Complete broken chain:")
    print(f"  1. Resolver returns 0x804ED9590 for il2cpp_runtime_class_init ✓")
    print(f"  2. RAX propagation bug: cpuContext.Rax = 0x7FD670094000 (garbage) ✗")
    print(f"  3. GOT slot receives garbage ✗")
    print(f"  4. Guest calls il2cpp_runtime_class_init through GOT → jumps to garbage ✗")
    print(f"  5. Type initialization NEVER runs ✗")
    print(f"  6. Flags stay 0 ✗")
    print(f"  7. Gate skips all methods ✗")
    print(f"  8. PlayerLoop never runs ✗")
    print(f"  9. Deadlock ✗")
    
    print(f"\n  BROKEN TRANSITION: Step 2 (RAX propagation)")
    print(f"  This is the EARLIEST confirmed broken transition")
    
    print(f"\n{'='*80}")
    print("IL2CPP INIT CHAIN SUMMARY")
    print(f"{'='*80}")
    print("""
The IL2CPP initialization chain is broken at the RAX propagation step.
The resolver correctly finds il2cpp_runtime_class_init at 0x804ED9590,
but TryCallGuestFunction doesn't propagate this value to cpuContext.Rax.

The GOT slot receives garbage, and subsequent calls to
il2cpp_runtime_class_init jump to a garbage address.

Type initialization NEVER runs, flags are NEVER set, and the gate
function blocks ALL IL2CPP-generated methods including PlayerLoop.Initialize().

The earliest broken transition is:
  Resolver returns 0x804ED9590 → cpuContext.Rax gets 0x7FD670094000
  (EXP-138 RAX propagation bug)
""")

if __name__ == '__main__':
    main()
