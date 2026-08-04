#!/usr/bin/env python3
"""EXP-079 TASK 1b: Disassemble helper functions called by CLEAR."""
import sys
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_at(img, runtime_addr, max_bytes=200, max_insns=40, label=""):
    vaddr = runtime_addr - PS5_BASE
    if not (img.min_vaddr <= vaddr < img.max_vaddr):
        print(f"  [{label}] 0x{runtime_addr:X} out of range")
        return
    data = img.read_bytes(vaddr, max_bytes)
    if data is None:
        print(f"  [{label}] no data at 0x{runtime_addr:X}")
        return
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
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                target_addr = ins.address + ins.size + op.mem.disp
                op_str += f"  ; → 0x{target_addr:X}"
        print(f"  0x{ins.address:X}:  {ins.bytes.hex():24s}  {ins.mnemonic:8s} {op_str}{marker}")

def main():
    img = ElfImage(EBOOT_PATH)
    
    # Helpers called by CLEAR
    for label, addr in [
        ("FREE_HELPER_0x8007e2280", 0x8007E2280),   # dealloc helper
        ("VIRTUAL_HELPER_0x801937610", 0x801937610), # called on r12+0x30
        ("SIGNAL_HELPER_A_0x8019377d0", 0x8019377D0), # called with [rbx+0xB0]/[rbx+0xB8] and [rbx+0x68]/[rbx+0x70]
        ("SIGNAL_HELPER_B_0x8019377b0", 0x8019377B0), # called with rdi=[rbx+0x68], esi=1
        ("UNKNOWN_0x800bb0860", 0x800BB0860),          # called per-array-element
        ("UNKNOWN_0x8019369b0", 0x8019369B0),          # error/log
        ("UNKNOWN_0x800461000", 0x800461000),          # final call on r12
    ]:
        disasm_at(img, addr, max_bytes=300, max_insns=50, label=label)
    return 0

if __name__ == "__main__":
    sys.exit(main())
