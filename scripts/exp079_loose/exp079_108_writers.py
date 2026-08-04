#!/usr/bin/env python3
"""EXP-079 TASK 5d: Find ALL writes to [reg+0x108] (the dependency flag)."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def main():
    img = ElfImage(EBOOT_PATH)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    
    # We're looking for instructions that write to [reg+0x108]:
    # - mov byte ptr [reg+0x108], imm8     ; e.g., mov byte [rbx+0x108], 0
    # - mov byte ptr [reg+0x108], reg8     ; e.g., mov byte [rbx+0x108], al
    # - mov qword ptr [reg+0x108], imm32   ; e.g., mov qword [rbx+0x108], 0
    # - mov qword ptr [reg+0x108], reg64
    # The displacement 0x108 is encoded as 4 bytes (since 0x108 doesn't fit in 1-byte disp)
    
    # Pattern: any instruction with displacement 0x108 (00 01 00 00 in little-endian)
    # Specifically look for: .. [reg + 0x108] ..
    # The encoding has 0x08010000 in the displacement field
    
    # Let's scan the executable segment for the byte pattern 08 01 00 00 (disp32 = 0x108)
    # Then disassemble around each hit to verify it's a memory operand
    
    # Actually, a better approach: disassemble the whole executable segment and look for
    # instructions that reference [reg+0x108]
    
    print("=== Scanning EBOOT executable segment for [reg+0x108] references ===")
    
    # First, scan for the disp32 = 0x108 byte pattern (08 01 00 00) in code
    # Then verify by disassembling
    hits = []
    for seg in img.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1):
            continue
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        seg_vaddr_runtime = PS5_BASE + seg['p_vaddr']
        
        # The 4-byte displacement 0x00000108 = 08 01 00 00 in little-endian
        # Look for this pattern, but check context to filter
        i = 0
        while i < len(seg_data) - 4:
            if seg_data[i:i+4] == b'\x08\x01\x00\x00':
                # Check if this looks like a ModR/M + SIB + disp32 encoding
                # The byte before should be ModR/M with mod=10 (0x80-0xBF) and r/m in {0,1,2,3,5,6,7}
                # Or for byte accesses, the prefix might be 80/83/88/etc.
                # Disassemble 16 bytes before and 8 after
                start = max(0, i - 16)
                end = min(len(seg_data), i + 12)
                chunk = seg_data[start:end]
                # Try to disassemble
                insns = list(md.disasm(chunk, seg_vaddr_runtime + start))
                for ins in insns:
                    if ins.address <= seg_vaddr_runtime + i < ins.address + ins.size:
                        # This instruction contains the disp32 0x108
                        # Check if it accesses +0x108
                        if '0x108]' in ins.op_str or '+ 0x108]' in ins.op_str:
                            hits.append((ins.address, ins.mnemonic, ins.op_str, ins.bytes.hex()))
                        break
            i += 1
    
    print(f"\nFound {len(hits)} instructions referencing [reg+0x108]:")
    
    # Categorize: writes vs reads
    writes = []
    reads = []
    for addr, mn, ops, hex_bytes in hits:
        # A write is when [reg+0x108] is the destination (first operand)
        # In Intel syntax, the dest is the first operand
        first_op = ops.split(',')[0].strip()
        if '0x108' in first_op:
            writes.append((addr, mn, ops, hex_bytes))
        else:
            reads.append((addr, mn, ops, hex_bytes))
    
    print(f"\n--- WRITES ({len(writes)}) ---")
    for addr, mn, ops, hex_bytes in writes[:50]:
        print(f"  0x{addr:X}: {hex_bytes:30s}  {mn} {ops}")
    
    print(f"\n--- READS ({len(reads)}) ---")
    for addr, mn, ops, hex_bytes in reads[:50]:
        print(f"  0x{addr:X}: {hex_bytes:30s}  {mn} {ops}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
