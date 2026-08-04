#!/usr/bin/env python3
"""Fast byte-level scan for RIP-relative refs to known struct addresses."""
import struct
import sys

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

with open(PRX, "rb") as f:
    data = f.read()

code_start = 0x4000
code_end = 0x4000 + 0x2B9722A

targets = {
    0x8086E9000: "CodeReg",
    0x80885C580: "MetadataReg",
    0x80893E950: "types[]",
    0x808791958: "methodPointers[]",
}

# For 7-byte RIP-relative insn (REX + opcode + modrm + disp32):
#   disp32 at file_off i+3, runtime_of_insn = PRX_BASE + (i - code_start)
#   eff = runtime + 7 + disp32 = target
#   => disp32 = target - PRX_BASE - (i - code_start) - 7

# For 8-byte insn (extra byte): disp32 at i+4, eff = runtime + 8 + disp32

for target, name in targets.items():
    count = 0
    results = []
    # 7-byte insn
    for i in range(code_start, code_end - 7):
        expected_disp = target - PRX_BASE - (i - code_start) - 7
        if expected_disp < -0x80000000 or expected_disp > 0x7FFFFFFF:
            continue
        actual = struct.unpack_from("<i", data, i + 3)[0]
        if actual == expected_disp:
            count += 1
            if len(results) < 20:
                results.append((PRX_BASE + (i - code_start), 7))
    # 8-byte insn
    for i in range(code_start, code_end - 8):
        expected_disp = target - PRX_BASE - (i - code_start) - 8
        if expected_disp < -0x80000000 or expected_disp > 0x7FFFFFFF:
            continue
        actual = struct.unpack_from("<i", data, i + 4)[0]
        if actual == expected_disp:
            count += 1
            if len(results) < 20:
                results.append((PRX_BASE + (i - code_start), 8))
    
    print(f"0x{target:X} ({name}): {count} RIP-relative refs")
    for addr, sz in results[:20]:
        print(f"  0x{addr:X} (insn_size={sz})")
    sys.stdout.flush()
