#!/usr/bin/env python3
"""EXP-079 TASK 6: Disassemble the TASK DISPATCHER function (containing signal site 0x800AC6DF6)."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_func(img, runtime_addr, max_bytes=2000, max_insns=300, label=""):
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

def find_func_start(img, addr, max_back=0x2000):
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
    
    # Find function containing 0x800AC6DF6 (signal [rcx+0x68] site)
    addr = 0x800AC6DF6
    func_start = find_func_start(img, addr, max_back=0x4000)
    print(f"=== Dispatcher function containing 0x{addr:X} ===")
    print(f"  Likely start: {('0x%X' % func_start) if func_start else 'NONE'}")
    if func_start:
        disasm_func(img, func_start, max_bytes=3000, max_insns=400, label="DISPATCHER")
    
    # Also find function containing 0x800AC7269 (another signal site, the one with [rcx+0xf8] write)
    addr2 = 0x800AC7269
    func_start2 = find_func_start(img, addr2, max_back=0x4000)
    print(f"\n=== Function containing 0x{addr2:X} ===")
    print(f"  Likely start: {('0x%X' % func_start2) if func_start2 else 'NONE'}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
