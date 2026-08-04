#!/usr/bin/env python3
"""EXP-079 TASK 5c: Disassemble context around each SignalSema[reg+0x68] call site."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

SITES = [0x800AC037A, 0x800AC3393, 0x800AC5E85, 0x800AC6DF6, 0x800AC7269, 0x800AC7346, 0x800AC7476]

def disasm_around(img, runtime_addr, before=64, after=20, label=""):
    vaddr = runtime_addr - PS5_BASE
    start_vaddr = vaddr - before
    if start_vaddr < img.min_vaddr: return
    data = img.read_bytes(start_vaddr, before + after + 16)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n[{label}] Context around 0x{runtime_addr:X}:")
    for ins in list(md.disasm(data, runtime_addr - before)):
        if ins.address > runtime_addr + after: break
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
        arrow = "  <<<" if ins.address == runtime_addr else ""
        print(f"  0x{ins.address:X}:  {ins.bytes.hex():24s}  {ins.mnemonic:8s} {op_str}{marker}{arrow}")

def find_func_start(img, addr, max_back=0x1000):
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
    for site in SITES:
        func_start = find_func_start(img, site)
        print(f"\n=== Site 0x{site:X} — likely function start: {('0x%X' % func_start) if func_start else 'NONE'} ===")
        disasm_around(img, site, before=100, after=10, label=f"SITE_{site:X}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
