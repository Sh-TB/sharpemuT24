#!/usr/bin/env python3
"""EXP-079 TASK 5e: Disassemble SET_DEP function at 0x800A9FAED (and similar)."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_func(img, runtime_addr, max_bytes=400, max_insns=80, label=""):
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

def find_func_start(img, addr, max_back=0x800):
    vaddr = addr - PS5_BASE
    start_vaddr = max(img.min_vaddr, vaddr - max_back)
    data = img.read_bytes(start_vaddr, vaddr - start_vaddr + 1)
    if data is None: return None
    last_cc_end = None
    i = 0
    while i < len(data) - 1:
        if data[i] == 0xCC and data[i+1] == 0xCC:
            j = i
            while j < len(data) and data[j] == 0xCC:
                j += 1
            if j - i >= 4:
                last_cc_end = j
            i = j
        else:
            i += 1
    if last_cc_end is not None:
        return start_vaddr + last_cc_end + PS5_BASE
    return None

def main():
    img = ElfImage(EBOOT_PATH)
    
    # The SET_DEP at 0x800A9FAED
    addr = 0x800A9FAED
    func_start = find_func_start(img, addr)
    print(f"=== SET_DEP site 0x{addr:X}, func start: {('0x%X' % func_start) if func_start else 'NONE'} ===")
    if func_start:
        disasm_func(img, func_start, max_bytes=300, max_insns=80, label=f"SET_DEP_{addr:X}")
    
    # Also check 0x800AC0371 (the other site that signals [r13+0x68])
    # Need to find what function that's in
    print(f"\n=== Signal site 0x800AC0371 - find function start ===")
    addr2 = 0x800AC0371
    func_start2 = find_func_start(img, addr2)
    print(f"  func start: {('0x%X' % func_start2) if func_start2 else 'NONE'}")
    if func_start2:
        disasm_func(img, func_start2, max_bytes=900, max_insns=130, label=f"SIG_SITE_{addr2:X}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
