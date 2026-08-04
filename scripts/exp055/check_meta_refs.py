#!/usr/bin/env python3
"""Check all insn sizes 5-11 for refs to MetadataReg."""
import struct

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

with open(PRX, "rb") as f:
    data = f.read()

code_start = 0x4000
code_end = 0x4000 + 0x2B9722A

targets = [0x80885C580, 0x80885C5C0, 0x80885C600, 0x80885C578, 0x80885C560]

for target in targets:
    total = 0
    for insn_size in range(5, 12):
        prefix_len = insn_size - 4
        for i in range(code_start, code_end - insn_size):
            expected_disp = target - PRX_BASE - (i - code_start) - insn_size
            if expected_disp < -0x80000000 or expected_disp > 0x7FFFFFFF:
                continue
            actual = struct.unpack_from("<i", data, i + prefix_len)[0]
            if actual == expected_disp:
                total += 1
    print(f"0x{target:X}: {total} refs (insn sizes 5-11)")
