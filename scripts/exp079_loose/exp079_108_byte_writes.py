#!/usr/bin/env python3
"""EXP-079 TASK 5d: Find BYTE writes to [reg+0x108] specifically."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

def main():
    img = ElfImage(EBOOT_PATH)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    
    # Look for these specific byte-write patterns to [reg+0x108]:
    # 1. mov byte ptr [rax+0x108], imm8 : C6 80 08 01 00 00 imm8 (7 bytes)
    # 2. mov byte ptr [rcx+0x108], imm8 : C6 81 08 01 00 00 imm8
    # 3. mov byte ptr [rdx+0x108], imm8 : C6 82 08 01 00 00 imm8
    # 4. mov byte ptr [rbx+0x108], imm8 : C6 83 08 01 00 00 imm8
    # 5. mov byte ptr [rsi+0x108], imm8 : C6 86 08 01 00 00 imm8
    # 6. mov byte ptr [rdi+0x108], imm8 : C6 87 08 01 00 00 imm8
    # 7. With REX.B (r8-r15):
    #    mov byte ptr [r8+0x108], imm8  : 41 C6 80 08 01 00 00 imm8
    #    mov byte ptr [r9+0x108], imm8  : 41 C6 81 ...
    #    mov byte ptr [r10+0x108], imm8 : 41 C6 82 ...
    #    mov byte ptr [r11+0x108], imm8 : 41 C6 83 ...
    #    mov byte ptr [r14+0x108], imm8 : 41 C6 86 ...
    #    mov byte ptr [r15+0x108], imm8 : 41 C6 87 ...
    # (r12 and r13 need SIB byte, so encoding is different)
    # 8. mov byte ptr [r12+0x108], imm8 : 41 C6 84 24 08 01 00 00 imm8 (8 bytes, with SIB)
    # 9. mov byte ptr [r13+0x108], imm8 : 41 C6 85 08 01 00 00 imm8 (8 bytes, mod=10 rm=101=r13 with disp32)
    #    Actually for r13, mod=10 rm=101 — that's [r13+disp32] not [r13+SIB]
    
    patterns = [
        (b'\xc6\x80\x08\x01\x00\x00', 'rax'),
        (b'\xc6\x81\x08\x01\x00\x00', 'rcx'),
        (b'\xc6\x82\x08\x01\x00\x00', 'rdx'),
        (b'\xc6\x83\x08\x01\x00\x00', 'rbx'),
        (b'\xc6\x86\x08\x01\x00\x00', 'rsi'),
        (b'\xc6\x87\x08\x01\x00\x00', 'rdi'),
        (b'\x41\xc6\x80\x08\x01\x00\x00', 'r8'),
        (b'\x41\xc6\x81\x08\x01\x00\x00', 'r9'),
        (b'\x41\xc6\x82\x08\x01\x00\x00', 'r10'),
        (b'\x41\xc6\x83\x08\x01\x00\x00', 'r11'),
        (b'\x41\xc6\x85\x08\x01\x00\x00', 'r13'),
        (b'\x41\xc6\x86\x08\x01\x00\x00', 'r14'),
        (b'\x41\xc6\x87\x08\x01\x00\x00', 'r15'),
        # r12 needs SIB byte
        (b'\x41\xc6\x84\x24\x08\x01\x00\x00', 'r12'),
    ]
    
    # Also look for `mov byte ptr [reg+0x108], reg8` (e.g., from a register)
    # Encoding: 88 /r with mod=10
    # 88 80 .. = [rax], 88 81 = [rcx], 88 83 = [rbx], ...
    # And: 44 88 80 .. = [r8] from r8b etc (REX.R)
    # We'll search the disassembly instead
    
    print("=== BYTE writes to [reg+0x108] ===\n")
    print("--- mov byte ptr [reg+0x108], imm8 ---")
    
    all_hits = []
    for seg in img.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1):
            continue
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        seg_vaddr_runtime = PS5_BASE + seg['p_vaddr']
        
        for pat, reg in patterns:
            i = 0
            while True:
                j = seg_data.find(pat, i)
                if j < 0: break
                imm8 = seg_data[j + len(pat)] if j + len(pat) < len(seg_data) else None
                runtime_addr = seg_vaddr_runtime + j
                all_hits.append((runtime_addr, reg, imm8, 'imm8'))
                i = j + 1
    
    for addr, reg, imm, kind in sorted(all_hits):
        if imm is not None:
            print(f"  0x{addr:X}: mov byte ptr [{reg}+0x108], 0x{imm:02X}")
    
    # Also disassemble the whole executable segment and find ALL byte mov writes
    # This catches `mov byte [reg+0x108], r8b` etc.
    print(f"\n--- All 'mov byte ptr [reg+0x108], ...' (including from register) ---")
    
    extra_hits = []
    for seg in img.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1):
            continue
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        seg_vaddr_runtime = PS5_BASE + seg['p_vaddr']
        # Disassemble and filter
        for ins in md.disasm(seg_data, seg_vaddr_runtime):
            if ins.mnemonic == 'mov' and ins.op_str.startswith('byte ptr [') and '0x108]' in ins.op_str:
                # Verify it's a register or immediate source
                parts = ins.op_str.split(',', 1)
                if len(parts) == 2:
                    src = parts[1].strip()
                    if src in ('al','cl','dl','bl','sil','dil','r8b','r9b','r10b','r11b','r12b','r13b','r14b','r15b') or src.startswith('0x'):
                        extra_hits.append((ins.address, ins.op_str, ins.bytes.hex()))
    
    print(f"Found {len(extra_hits)} byte-mov instructions to [reg+0x108]")
    for addr, ops, hex_b in extra_hits[:30]:
        print(f"  0x{addr:X}: {hex_b:30s}  mov {ops}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
