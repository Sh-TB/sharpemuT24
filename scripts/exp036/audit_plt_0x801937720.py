#!/usr/bin/env python3
"""EXP-036 Task 3: Audit PLT 0x801937720 import mapping."""
import struct
import sys
import subprocess
from pathlib import Path

PLT_ADDR = 0x801937720
GOT_ADDR = 0x801937726 + 0x3e36e2
IMPORT_INDEX = 0x10c

print(f"=== PLT 0x{PLT_ADDR:X} Audit ===")
print(f"  GOT slot address: 0x{GOT_ADDR:X}")
print(f"  Import index: 0x{IMPORT_INDEX:X} ({IMPORT_INDEX})")
print()

# Check what NID tsvEmnenz48 maps to in ps5_names.txt
names_file = Path("/tmp/my-project/work/sharpemuT24/scripts/ps5_names.txt")
print(f"=== NID tsvEmnenz48 lookup in ps5_names.txt ===")
if names_file.exists():
    found = False
    for line in names_file.read_text().splitlines():
        if "tsvEmnenz48" in line:
            print(f"  FOUND: {line}")
            found = True
    if not found:
        print(f"  NOT found in ps5_names.txt")
print()

# Check what NID scePthreadCondTimedwait maps to
print(f"=== scePthreadCondTimedwait / CondWait NID lookup ===")
if names_file.exists():
    for line in names_file.read_text().splitlines():
        low = line.lower()
        if "condtimedwait" in low or "condwait" in low:
            print(f"  {line}")
print()

# Check Aerolib source for tsvEmnenz48
print(f"=== Aerolib / source check for tsvEmnenz48 ===")
result = subprocess.run(
    ["grep", "-rn", "tsvEmnenz48", "/tmp/my-project/work/sharpemuT24/src/"],
    capture_output=True, text=True, timeout=30
)
print(result.stdout[:2000] if result.stdout else "  No matches in src/")
print()

# Check what __cxa_atexit maps to
print(f"=== __cxa_atexit NID lookup ===")
result = subprocess.run(
    ["grep", "-rn", "__cxa_atexit", "/tmp/my-project/work/sharpemuT24/src/"],
    capture_output=True, text=True, timeout=30
)
print(result.stdout[:2000] if result.stdout else "  No matches in src/")
print()

# Check the call site context — what's at [rbx+0x68]?
# From EXP-035 dump: [obj+0x68] = 0x0000000D00000060
# This looks like a packed value, not a pointer.
# Let's check what scePthreadCondTimedwait expects:
#   arg1: ScePthreadCond* (pointer)
#   arg2: ScePthreadMutex* (pointer)
#   arg3: SceKernelUseconds* (pointer to timeout)
# But [rbx+0x68] = 0x0000000D00000060 — not a valid pointer!
# This suggests [rbx+0x68] is NOT a cond/mutex pointer.
print(f"=== Call site argument analysis ===")
print(f"  Call: 0x801937720(rdi=[rbx+0x68], rsi=1, rdx=0)")
print(f"  [rbx+0x68] from EXP-035 dump: 0x0000000D00000060")
print(f"  This is NOT a valid pointer (too small, looks packed)")
print()
print(f"  Possible interpretations:")
print(f"    - [rbx+0x68] is a semaphore ID (not a pointer)")
print(f"    - The function is sceKernelWaitSema(semaid, count, timeout)")
print(f"    - Or the object is not fully initialized and [rbx+0x68] is garbage")
