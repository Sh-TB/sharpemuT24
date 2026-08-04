#!/usr/bin/env python3
"""EXP-079 TASK 6: Disassemble worker entry point 0x800BB06A0."""
import sys
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_func(img, runtime_addr, max_bytes=600, max_insns=120, label=""):
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
            break

def main():
    img = ElfImage(EBOOT_PATH)
    disasm_func(img, 0x800BB06A0, max_bytes=600, max_insns=120, label="WORKER_ENTRY")
    
    # Also check the SET_DEP function continuation (after 0x800A9FAED)
    print("\n=== SET_DEP function continuation (0x800A9FAEF onwards) ===")
    disasm_func(img, 0x800A9FAEF, max_bytes=400, max_insns=80, label="SET_DEP_CONT")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
