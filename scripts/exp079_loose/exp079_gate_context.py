#!/usr/bin/env python3
"""EXP-079 TASK 4: Disassemble around the gate at 0x800AA0207 and analyze worker context."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_at(img, runtime_addr, max_bytes=800, max_insns=120, label=""):
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

def find_func_start(img, addr, max_back=0x1000):
    """Walk backwards to find function start (after INT3 padding)."""
    vaddr = addr - PS5_BASE
    start_vaddr = max(img.min_vaddr, vaddr - max_back)
    data = img.read_bytes(start_vaddr, vaddr - start_vaddr + 1)
    if data is None:
        return None
    # Find last CC pad before target
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
    
    # Find the function that contains the gate at 0x800AA0207
    gate_addr = 0x800AA0207
    func_start = find_func_start(img, gate_addr)
    print(f"=== Function containing gate at 0x{gate_addr:X} ===")
    print(f"Likely function start: 0x{func_start:X}" if func_start else "Could not find function start")
    
    if func_start:
        # Disassemble from function start, show enough to cover the gate
        disasm_at(img, func_start, max_bytes=1500, max_insns=250, label="WORKER_FUNC")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
