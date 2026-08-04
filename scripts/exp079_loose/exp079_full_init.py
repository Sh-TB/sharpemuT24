#!/usr/bin/env python3
"""EXP-079 TASK 2c: Examine the init function around LEA at 0x800A9F2FF and find its caller."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def disasm_at(img, runtime_addr, max_bytes=1500, max_insns=300, label=""):
    vaddr = runtime_addr - PS5_BASE
    if not (img.min_vaddr <= vaddr < img.max_vaddr):
        print(f"  [{label}] 0x{runtime_addr:X} out of range")
        return []
    data = img.read_bytes(vaddr, max_bytes)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n[{label}] Disassembly at 0x{runtime_addr:X}:")
    insns = list(md.disasm(data, runtime_addr))[:max_insns]
    for ins in insns:
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
        if ins.mnemonic == "ret":
            break
    return insns

def find_function_start(img, addr, max_back=0x400):
    """Walk backwards to find function prologue (push rbp / push rbx etc.)."""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    # Look for common prologue: 55 48 89 e5 (push rbp; mov rbp, rsp) or 41 57 (push r15) etc.
    # Search backward for INT3 alignment or known prologues
    vaddr = addr - PS5_BASE
    start_vaddr = max(img.min_vaddr, vaddr - max_back)
    data = img.read_bytes(start_vaddr, vaddr - start_vaddr + 16)
    if data is None:
        return None
    # Look for 0xCC 0xCC 0xCC 0xCC alignment followed by prologue
    last_cc_block = None
    for i in range(len(data) - 1):
        if data[i] == 0xCC and data[i+1] == 0xCC:
            # Find end of CC run
            j = i
            while j < len(data) and data[j] == 0xCC:
                j += 1
            last_cc_block = i  # start of last CC run
    if last_cc_block is not None:
        # Function starts right after CC run
        return start_vaddr + last_cc_block + (data[last_cc_block:].index(b'\x00', 0) if False else 0)
    return None

def main():
    img = ElfImage(EBOOT_PATH)
    
    # The LEA at 0x800A9F2FF is inside a function. Let me find that function's start.
    # Walk backwards looking for INT3 padding + prologue
    target = 0x800A9F2FF
    start_vaddr = (target - PS5_BASE) - 0x800
    data = img.read_bytes(start_vaddr, 0x800 + 16)
    if data is None:
        print("Cannot read backwards")
        return 1
    
    # Find last CC pad before target
    last_cc_end = None
    for i in range(len(data) - 1):
        if data[i] == 0xCC and (i == 0 or data[i-1] != 0xCC):
            # Start of CC run
            j = i
            while j < len(data) and data[j] == 0xCC:
                j += 1
            if j - i >= 4:  # at least 4 CC bytes (alignment)
                last_cc_end = j
    
    if last_cc_end is not None:
        func_start = (start_vaddr + last_cc_end) + PS5_BASE
        print(f"=== Likely function start: 0x{func_start:X} (LEA at 0x{target:X} is +0x{target - func_start:X} bytes in) ===")
        # Disassemble from there
        disasm_at(img, func_start, max_bytes=1500, max_insns=250, label="INIT_FUNC")
    
    # Also check 0x800A9F730 (the function loaded by the OTHER LEA at 0x800A9F2BC)
    print(f"\n=== Function at 0x800A9F730 (loaded by other LEA at 0x800A9F2BC) ===")
    disasm_at(img, 0x800A9F730, max_bytes=300, max_insns=40, label="F730")
    
    # And the function at 0x800A9F8E0 (the function we saw after CLEAR's end - looks like an inline function)
    print(f"\n=== Function at 0x800A9F8E0 (called by 0x800A9F8F0) ===")
    disasm_at(img, 0x800A9F8E0, max_bytes=200, max_insns=30, label="F8E0")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
