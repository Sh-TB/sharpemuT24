#!/usr/bin/env python3
"""EXP-079 TASK 2: Find ALL references to 0x800A9F750 in eboot and PRX."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM, X86_OP_IMM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PRX_PATH = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PS5_BASE = 0x800000000

TARGET = 0x800A9F750

def scan_image(img_path, img_label, base_offset=0):
    """Scan executable segments for references to TARGET."""
    img = ElfImage(img_path)
    print(f"\n=== Scanning {img_label} ({img_path}) ===")
    
    # Build byte patterns
    target_bytes_le = struct.pack('<Q', TARGET)  # full 8-byte little-endian
    target_bytes_le_4 = struct.pack('<I', TARGET & 0xFFFFFFFF)  # 4-byte little-endian
    
    # The address as a 32-bit displacement (used in CALL/JMP rel32)
    # CALL rel32 = E8 xx xx xx xx
    # JMP rel32  = E9 xx xx xx xx
    # The rel32 is computed as: target - (instruction_address + 5)
    
    direct_calls = []
    indirect_refs = []  # function pointer stores
    reloc_refs = []  # in relocation tables
    
    # Iterate all PT_LOAD X (executable) segments
    for seg in img.segments:
        if seg['p_type'] != 1: continue
        if not (seg['p_flags'] & 1): continue  # X flag
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        seg_vaddr = seg['p_vaddr']  # base-relative
        # The runtime address of seg_vaddr is base_offset + seg_vaddr
        # But for eboot, base_offset = PS5_BASE = 0x800000000
        # For PRX, base_offset varies — but the PRX has its own vaddr range starting at 0
        
        # Scan for direct CALL/JMP to TARGET
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
        # Disassemble the whole segment — but that's slow, so use a different approach:
        # Look for E8/E9 bytes and check if the rel32 lands on TARGET
        
        # For eboot: target_vaddr_in_image = TARGET - PS5_BASE = 0xA9F750
        # For PRX: we don't know the load base, but Yatzi's PRX is loaded at some runtime address
        # that's different from 0x800000000.
        
        # Direct CALL/JMP scan: pattern E8 + rel32
        for i in range(len(seg_data) - 5):
            if seg_data[i] in (0xE8, 0xE9):
                rel32 = struct.unpack_from('<i', seg_data, i + 1)[0]
                # Instruction is at runtime addr: base_offset + seg_vaddr + i
                # Next instruction is at: base_offset + seg_vaddr + i + 5
                # Target = next + rel32
                instr_runtime = base_offset + seg_vaddr + i
                target_runtime = instr_runtime + 5 + rel32
                if target_runtime == TARGET:
                    direct_calls.append((instr_runtime, seg_data[i], target_runtime))
        
        # Also scan for 8-byte literal address (function pointer store)
        # Pattern: any 8-byte sequence equal to TARGET
        # This is searched even in non-X segments below, but check X first for RIP-relative LEAs
        # LEA rax, [rip + disp32] = 48 8D 05 xx xx xx xx
        for i in range(len(seg_data) - 7):
            if seg_data[i:i+3] == b'\x48\x8d\x05':  # LEA rax, [rip+disp32]
                disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                instr_runtime = base_offset + seg_vaddr + i
                target_runtime = instr_runtime + 7 + disp32
                if target_runtime == TARGET:
                    indirect_refs.append(('LEA rax,[rip]', instr_runtime, target_runtime))
            elif seg_data[i:i+3] == b'\x48\x8d\x0d':  # LEA rcx, [rip+disp32]
                disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                instr_runtime = base_offset + seg_vaddr + i
                target_runtime = instr_runtime + 7 + disp32
                if target_runtime == TARGET:
                    indirect_refs.append(('LEA rcx,[rip]', instr_runtime, target_runtime))
            elif seg_data[i:i+3] == b'\x48\x8d\x15':  # LEA rdx, [rip+disp32]
                disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                instr_runtime = base_offset + seg_vaddr + i
                target_runtime = instr_runtime + 7 + disp32
                if target_runtime == TARGET:
                    indirect_refs.append(('LEA rdx,[rip]', instr_runtime, target_runtime))
            elif seg_data[i:i+3] == b'\x48\x8d\x35':  # LEA rsi, [rip+disp32]
                disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                instr_runtime = base_offset + seg_vaddr + i
                target_runtime = instr_runtime + 7 + disp32
                if target_runtime == TARGET:
                    indirect_refs.append(('LEA rsi,[rip]', instr_runtime, target_runtime))
            elif seg_data[i:i+3] == b'\x48\x8d\x3d':  # LEA rdi, [rip+disp32]
                disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                instr_runtime = base_offset + seg_vaddr + i
                target_runtime = instr_runtime + 7 + disp32
                if target_runtime == TARGET:
                    indirect_refs.append(('LEA rdi,[rip]', instr_runtime, target_runtime))
    
    # Search ALL segments (including data) for the 8-byte address as a stored function pointer
    for seg in img.segments:
        if seg['p_type'] != 1: continue
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        seg_vaddr_runtime = base_offset + seg['p_vaddr']
        for i in range(len(seg_data) - 8):
            if seg_data[i:i+8] == target_bytes_le:
                addr_runtime = seg_vaddr_runtime + i
                reloc_refs.append(('PTR_QWORD', addr_runtime))
            # Also check 4-byte truncated form (some packed structures)
            # Actually this is risky — skip
    
    # Search relocation tables (RELA) for addends = TARGET
    # (function pointer in initialization relocations)
    rela_off = None
    rela_size = None
    # For eboot: DT_RELA=0x7, DT_RELASZ=0x8 (from previous analysis)
    # For PRX: similar pattern
    
    return direct_calls, indirect_refs, reloc_refs

def main():
    # Scan eboot (PS5_BASE = 0x800000000)
    dc, ir, rr = scan_image(EBOOT_PATH, "EBOOT", PS5_BASE)
    print(f"\n--- EBOOT results ---")
    print(f"  Direct CALL/JMP to 0x{TARGET:X}: {len(dc)}")
    for addr, opcode, tgt in dc[:20]:
        op_name = "CALL" if opcode == 0xE8 else "JMP"
        print(f"    0x{addr:X}: {op_name} 0x{tgt:X}")
    print(f"  LEA references (RIP-relative): {len(ir)}")
    for kind, addr, tgt in ir[:20]:
        print(f"    0x{addr:X}: {kind} → 0x{tgt:X}")
    print(f"  Pointer-sized references in data: {len(rr)}")
    for kind, addr in rr[:20]:
        print(f"    0x{addr:X}: {kind} = 0x{TARGET:X}")
    
    # Scan PRX (PRX is loaded at a different base — need to check SharpEmu code)
    # SharpEmu loads PRX at a separate base. Let me try a few candidate bases.
    # Often PRX is loaded right after eboot or at a fixed offset.
    
    # For now, scan PRX with base=0 to find relative references (CALL/JMP rel32 from within PRX
    # to TARGET is unlikely since PRX is loaded far from eboot)
    # The relevant search is for stored function pointers in PRX data, but those would have to
    # be runtime-resolved (via relocation) — so check the PRX .rela tables
    
    print(f"\n=== PRX load base ===")
    # Check SharpEmu source for PRX load base
    return 0

if __name__ == "__main__":
    sys.exit(main())
