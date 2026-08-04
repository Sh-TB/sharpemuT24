#!/usr/bin/env python3
"""EXP-079 TASK 2b: Examine the LEA at 0x800A9F2FF that references CLEAR."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_at(img, runtime_addr, max_bytes=400, max_insns=80, label=""):
    vaddr = runtime_addr - PS5_BASE
    if not (img.min_vaddr <= vaddr < img.max_vaddr):
        print(f"  [{label}] 0x{runtime_addr:X} out of range")
        return
    data = img.read_bytes(vaddr, max_bytes)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n[{label}] Disassembly at 0x{runtime_addr:X}:")
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

def main():
    img = ElfImage(EBOOT_PATH)
    # Disassemble around 0x800A9F2FF — the LEA that loads CLEAR's address
    # Start a bit earlier to see context
    print("=== Context around LEA at 0x800A9F2FF ===")
    disasm_at(img, 0x800A9F2A0, max_bytes=400, max_insns=80, label="CTX")
    return 0

if __name__ == "__main__":
    sys.exit(main())
