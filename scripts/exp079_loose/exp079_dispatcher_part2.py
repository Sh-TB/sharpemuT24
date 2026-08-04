#!/usr/bin/env python3
"""EXP-079: Disassemble the part of the dispatcher around 0x800AC6DF6 and 0x800AC7260."""
import sys
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_range(img, start, end, label=""):
    vaddr = start - PS5_BASE
    data = img.read_bytes(vaddr, end - start + 32)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n[{label}] Range 0x{start:X}..0x{end:X}:")
    for ins in list(md.disasm(data, start)):
        if ins.address > end: break
        marker = ""
        if ins.mnemonic.startswith("call"): marker = " ← CALL"
        elif ins.mnemonic.startswith("j") and ins.mnemonic != "jmp": marker = " ← COND-JMP"
        elif ins.mnemonic == "jmp": marker = " ← JMP"
        elif ins.mnemonic == "ret": marker = " ← RET"
        op_str = ins.op_str
        for op in ins.operands:
            if op.type == 2 and op.mem.base == 41:
                target_addr = ins.address + ins.size + op.mem.disp
                op_str += f"  ; → 0x{target_addr:X}"
        print(f"  0x{ins.address:X}:  {ins.bytes.hex():24s}  {ins.mnemonic:8s} {op_str}{marker}")

def main():
    img = ElfImage(EBOOT_PATH)
    disasm_range(img, 0x800AC6DE0, 0x800AC6F00, label="PART1_AROUND_6DF6")
    disasm_range(img, 0x800AC71C0, 0x800AC74B0, label="PART2_AROUND_7260")
    
    # Also find the function start of the parent function containing 0x800AC7260 (signal site)
    # That signal site is in a different function (or sub-block) - find its start
    # Check from 0x800AC6F00 to 0x800AC71C0 for function boundaries
    print("\n=== Looking for function boundaries between 0x800AC6F00 and 0x800AC71C0 ===")
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    vaddr = 0x800AC6F00 - PS5_BASE
    data = img.read_bytes(vaddr, 0x800AC71C0 - 0x800AC6F00 + 16)
    # Look for INT3 padding
    last_int3_end = None
    for i in range(len(data) - 1):
        if data[i] == 0xCC and data[i+1] == 0xCC:
            j = i
            while j < len(data) and data[j] == 0xCC:
                j += 1
            if j - i >= 4:
                last_int3_end = j
    if last_int3_end is not None:
        print(f"  Last INT3 pad end: 0x{0x800AC6F00 + last_int1_end:X}" if last_int3_end else "")
        print(f"  Last INT3 pad end: 0x{0x800AC6F00 + last_int3_end:X}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
