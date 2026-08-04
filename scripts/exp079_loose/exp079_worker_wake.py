#!/usr/bin/env python3
"""EXP-079 TASK 5: Disassemble 0x800BB0860 (worker wake function) and find who signals [rbx+0x68]."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_func(img, runtime_addr, max_bytes=1200, max_insns=200, label=""):
    vaddr = runtime_addr - PS5_BASE
    data = img.read_bytes(vaddr, max_bytes)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n[{label}] Function at 0x{runtime_addr:X}:")
    for ins in list(md.disasm(data, runtime_addr))[:max_insns]:
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
        if ins.mnemonic == "ret" or ins.mnemonic == "ud2":
            # Show a few more after ret
            for ins2 in list(md.disasm(data[ins.address + ins.size - runtime_addr + vaddr:], ins.address + ins.size))[:3]:
                if ins2.mnemonic == "int3": break
                print(f"  0x{ins2.address:X}:  {ins2.bytes.hex():24s}  {ins2.mnemonic:8s} {ins2.op_str}")
            break

def main():
    img = ElfImage(EBOOT_PATH)
    disasm_func(img, 0x800BB0860, max_bytes=1500, max_insns=200, label="WORKER_WAKE_0x800BB0860")
    return 0

if __name__ == "__main__":
    sys.exit(main())
