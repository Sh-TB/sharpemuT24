#!/usr/bin/env python3
"""Check MetadataReg refs - fast version, only insn sizes 7 and 8."""
import struct
import sys

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

with open(PRX, "rb") as f:
    data = f.read()

code_start = 0x4000
code_end = 0x4000 + 0x2B9722A

targets = [0x80885C580, 0x80885C5C0, 0x80885C600]

for target in targets:
    total = 0
    results = []
    # Only check insn_size 7 and 8
    for insn_size in [7, 8]:
        prefix_len = insn_size - 4
        for i in range(code_start, code_end - insn_size):
            expected_disp = target - PRX_BASE - (i - code_start) - insn_size
            if expected_disp < -0x80000000 or expected_disp > 0x7FFFFFFF:
                continue
            actual = struct.unpack_from("<i", data, i + prefix_len)[0]
            if actual == expected_disp:
                total += 1
                if len(results) < 5:
                    results.append((PRX_BASE + (i - code_start), insn_size))
    print(f"0x{target:X}: {total} refs")
    for addr, sz in results:
        print(f"  0x{addr:X} (size={sz})")
    sys.stdout.flush()
