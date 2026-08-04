#!/usr/bin/env python3
"""EXP-079 TASK 1: Disassemble CLEAR function at 0x800A9F750."""
import sys, os, struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_REG, CS_OP_MEM, CS_OP_IMM
from capstone.x86 import X86_REG_RIP, X86_OP_MEM, X86_OP_REG, X86_OP_IMM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000  # SharpEmu PS5 main image base

# Reuse ElfImage from previous script
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage

def disasm_at(img, runtime_addr, max_bytes=512, max_insns=120, label=""):
    """Disassemble at runtime address (PS5_BASE + vaddr)."""
    vaddr = runtime_addr - PS5_BASE
    if not (img.min_vaddr <= vaddr < img.max_vaddr):
        print(f"  [{label}] 0x{runtime_addr:X} out of range")
        return []
    data = img.read_bytes(vaddr, max_bytes)
    if data is None:
        print(f"  [{label}] no data at 0x{runtime_addr:X}")
        return []
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    print(f"\n[{label}] Disassembly at 0x{runtime_addr:X} (file vaddr 0x{vaddr:X}):")
    insns = list(md.disasm(data, runtime_addr))[:max_insns]
    for ins in insns:
        # Highlight calls/jumps
        marker = ""
        if ins.mnemonic.startswith("call"):
            marker = " ← CALL"
        elif ins.mnemonic.startswith("j") and ins.mnemonic != "jmp":
            marker = " ← COND-JMP"
        elif ins.mnemonic == "jmp":
            marker = " ← JMP"
        elif ins.mnemonic == "ret":
            marker = " ← RET"
        elif ins.mnemonic == "int3":
            marker = " ← INT3"
        # Annotate memory operands relative to RIP
        op_str = ins.op_str
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                disp = op.mem.disp
                target_addr = ins.address + ins.size + disp
                op_str += f"  ; → 0x{target_addr:X}"
        print(f"  0x{ins.address:X}:  {ins.bytes.hex():24s}  {ins.mnemonic:8s} {op_str}{marker}")
    return insns

def find_func_end(img, start_addr, max_insns=300):
    """Find function end by looking for ret followed by alignment/nop."""
    vaddr = start_addr - PS5_BASE
    data = img.read_bytes(vaddr, 4096)
    if data is None:
        return None
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    last_ret_addr = None
    for i, ins in enumerate(md.disasm(data, start_addr)):
        if i >= max_insns:
            break
        if ins.mnemonic == "ret":
            last_ret_addr = ins.address
            # Check if next bytes are alignment (NOP/INT3) suggesting function boundary
            next_off = ins.address + ins.size - start_addr
            for j in range(next_off, min(next_off + 16, len(data))):
                if data[j] not in (0x90, 0xCC, 0x00):
                    break
            else:
                return last_ret_addr + ins.size
    return last_ret_addr + 1 if last_ret_addr else None

def main():
    img = ElfImage(EBOOT_PATH)
    print(f"EBOOT vaddr range: 0x{img.min_vaddr:X} .. 0x{img.max_vaddr:X}")
    print(f"PS5 base: 0x{PS5_BASE:X}")
    print(f"Effective runtime range: 0x{PS5_BASE+img.min_vaddr:X} .. 0x{PS5_BASE+img.max_vaddr:X}")
    
    # TASK 1: Disassemble CLEAR at 0x800A9F750
    print("\n=== TASK 1: Disassemble CLEAR function at 0x800A9F750 ===")
    insns = disasm_at(img, 0x800A9F750, max_bytes=1024, max_insns=200, label="CLEAR")
    
    # Find function end
    end = find_func_end(img, 0x800A9F750, max_insns=300)
    print(f"\nEstimated function end: {('0x%X' % end) if end else 'UNKNOWN'}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
