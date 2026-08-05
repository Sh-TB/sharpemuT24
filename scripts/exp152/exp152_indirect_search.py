#!/usr/bin/env python3
"""
EXP-152 Step 5: Search for INDIRECT writes to the flag.
The flag might be set via a register-based write (e.g., mov [rax+offset], 1)
where rax points to a structure containing the flag.

Also search for the flag address being loaded into a register (LEA or MOV).
"""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000
TARGET_BYTE_ADDR = 0x808D67B98

def parse_elf64(path):
    data = open(path, 'rb').read()
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_flags = struct.unpack_from('<I', data, off + 4)[0]
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        p_memsz = struct.unpack_from('<Q', data, off + 40)[0]
        segments.append({'type': p_type, 'flags': p_flags, 'offset': p_offset,
                         'vaddr': p_vaddr, 'filesz': p_filesz, 'memsz': p_memsz})
    return data, segments

def runtime_to_file(segments, runtime, load_base):
    vaddr = runtime - load_base
    for seg in segments:
        if seg['vaddr'] <= vaddr < seg['vaddr'] + seg['filesz']:
            return seg['offset'] + (vaddr - seg['vaddr'])
    return None

def main():
    print("=" * 80)
    print("EXP-152 Step 5: Indirect Write Search + Flag Address Loading")
    print("=" * 80)
    
    data, segments = parse_elf64(PRX_PATH)
    
    # ===== Search for the flag address being loaded into a register =====
    # This would be: LEA reg, [rip+disp32] where computed == TARGET_BYTE_ADDR
    # or: MOV reg, imm64 where imm64 == TARGET_BYTE_ADDR
    
    print(f"\n[1] Searching for LEA/MOV that loads flag address 0x{TARGET_BYTE_ADDR:X} into a register...")
    
    lea_hits = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        
        for i in range(len(seg_data) - 7):
            b0 = seg_data[i]
            b1 = seg_data[i + 1] if i + 1 < len(seg_data) else 0
            
            # LEA reg, [rip+disp32]: 48 8D xx or 4C 8D xx
            if b0 in (0x48, 0x4C) and b1 == 0x8D:
                modrm = seg_data[i + 2]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod == 0 and rm == 5:
                    disp = struct.unpack_from('<i', seg_data, i + 3)[0]
                    instr_addr = PRX_BASE + seg['vaddr'] + i
                    computed = instr_addr + 7 + disp
                    if computed == TARGET_BYTE_ADDR:
                        reg = (modrm >> 3) & 7
                        rex_r = (b0 >> 2) & 1
                        regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']
                        reg_name = regs[reg + (rex_r * 8)] if reg + (rex_r * 8) < 16 else f'r{reg + (rex_r * 8)}'
                        lea_hits.append((instr_addr, f'lea {reg_name}', computed))
                        if len(lea_hits) <= 20:
                            print(f"  0x{instr_addr:X}: lea {reg_name}, [0x{computed:X}]")
    
    print(f"  Total LEA hits: {len(lea_hits)}")
    
    # Also search for MOV reg, imm64 (B8+r for 32-bit, REX.W B8+r for 64-bit)
    print(f"\n[2] Searching for MOV reg, 0x{TARGET_BYTE_ADDR:X} (64-bit immediate)...")
    target_bytes = struct.pack('<Q', TARGET_BYTE_ADDR)
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(target_bytes, idx)
            if i == -1:
                break
            instr_addr = PRX_BASE + seg['vaddr'] + i
            # Check if preceded by REX.W + B8+r
            if i >= 2:
                prev2 = seg_data[i - 2]
                prev1 = seg_data[i - 1]
                if prev2 in (0x48, 0x49, 0x4C, 0x4D) and 0xB8 <= prev1 <= 0xBF:
                    reg = prev1 - 0xB8
                    regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi']
                    rex_r = (prev2 >> 2) & 1
                    reg_name = regs[reg + (rex_r * 8)] if reg + (rex_r * 8) < 16 else f'r{reg + (rex_r * 8)}'
                    print(f"  0x{instr_addr - 2:X}: mov {reg_name}, 0x{TARGET_BYTE_ADDR:X}")
            idx = i + 1
    
    # ===== Search for the flag address as a 64-bit constant in DATA sections =====
    # This would indicate the address is stored in a data structure (like a vtable or method table)
    print(f"\n[3] Searching for 0x{TARGET_BYTE_ADDR:X} as 64-bit constant in DATA sections...")
    for seg in segments:
        if seg['type'] != 1 or (seg['flags'] & 1):
            continue  # Skip code segments, only search data
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = seg_data.find(target_bytes, idx)
            if i == -1:
                break
            runtime = PRX_BASE + seg['vaddr'] + i
            seg_type = 'DATA-W' if seg['flags'] & 2 else 'DATA-R'
            print(f"  Found at 0x{runtime:X} ({seg_type})")
            # Show context
            context_start = max(0, i - 16)
            context = seg_data[context_start:i + 24]
            print(f"    Context: ...{context.hex()}...")
            idx = i + 1
    
    # ===== Search for the flag as part of a structure write =====
    # If the flag is at offset X within a structure, and a function writes to [base + X],
    # we need to find the base address and the offset
    
    # The flag is at 0x808D67B98
    # Let's check if there's a common base address used in the IL2CPP runtime
    # The flag array base was 0x808B55698
    # 0x808D67B98 - 0x808B55698 = 0x212500
    
    # Let's search for writes to [reg + 0x212500] or similar
    print(f"\n[4] Searching for writes to [reg + 0x212500] (flag offset from array base)...")
    flag_offset = TARGET_BYTE_ADDR - 0x808B55698  # = 0x212500
    print(f"  Flag offset from array base: 0x{flag_offset:X}")
    
    # This is a large offset, unlikely to be used directly
    # Let's try a different approach: search for the flag address minus common IL2CPP structure offsets
    
    # ===== Check RELA relocations more broadly =====
    print(f"\n[5] Checking RELA for relocations near flag address...")
    # Parse section headers
    e_shoff = struct.unpack_from('<Q', data, 0x28)[0]
    e_shentsize = struct.unpack_from('<H', data, 0x3A)[0]
    e_shnum = struct.unpack_from('<H', data, 0x3C)[0]
    e_shstrndx = struct.unpack_from('<H', data, 0x3E)[0]
    
    if e_shoff > 0 and e_shnum > 0 and e_shoff < len(data):
        shstr_hdr_off = e_shoff + e_shstrndx * e_shentsize
        if shstr_hdr_off + e_shentsize <= len(data):
            shstr_offset = struct.unpack_from('<Q', data, shstr_hdr_off + 0x18)[0]
            
            for sec_idx in range(e_shnum):
                sh_off = e_shoff + sec_idx * e_shentsize
                if sh_off + e_shentsize > len(data):
                    break
                sh_name_idx = struct.unpack_from('<I', data, sh_off)[0]
                sh_type = struct.unpack_from('<I', data, sh_off + 4)[0]
                sh_offset = struct.unpack_from('<Q', data, sh_off + 0x18)[0]
                sh_size = struct.unpack_from('<Q', data, sh_off + 0x20)[0]
                
                if sh_type != 4:  # SHT_RELA
                    continue
                
                name_start = shstr_offset + sh_name_idx
                name_end = data.find(b'\x00', name_start)
                sec_name = data[name_start:name_end].decode('ascii', errors='replace')
                
                entry_count = sh_size // 24
                target_vaddr = TARGET_BYTE_ADDR - PRX_BASE
                
                for j in range(entry_count):
                    entry_off = sh_offset + j * 24
                    if entry_off + 24 > len(data):
                        break
                    r_offset = struct.unpack_from('<Q', data, entry_off)[0]
                    r_info = struct.unpack_from('<Q', data, entry_off + 8)[0]
                    r_addend = struct.unpack_from('<q', data, entry_off + 16)[0]
                    
                    # Check within ±0x1000 bytes
                    if abs(r_offset - target_vaddr) < 0x1000:
                        r_type = r_info & 0xFFFFFFFF
                        r_sym = r_info >> 32
                        type_names = {1: 'R_X86_64_64', 7: 'JUMP_SLOT', 8: 'RELATIVE', 9: 'GLOB_DAT', 0x16: 'IRELATIVE'}
                        type_name = type_names.get(r_type, f'type={r_type}')
                        diff = r_offset - target_vaddr
                        print(f"  RELA entry #{j} in {sec_name}: r_offset=0x{r_offset:X} (diff={diff:+d}) type={type_name} addend=0x{r_addend:X}")
    
    # ===== Summary =====
    print(f"\n{'='*80}")
    print("SUMMARY")
    print("=" * 80)
    print(f"""
Flag address: 0x{TARGET_BYTE_ADDR:X}
LEA instructions loading flag address: {len(lea_hits)}

ANALYSIS:
  All 3 direct write instructions check the flag BEFORE writing.
  If flag == 0, the write is SKIPPED (chicken-and-egg problem).
  
  The flag must be set by an INDIRECT mechanism:
  1. A register-based write (mov [reg+offset], 1) where reg points to the flag
  2. A REP STOSB or similar string operation
  3. An IL2CPP runtime C function (not generated code)
  4. A memcpy or memset call
  
  The LEA instructions that load the flag address are the key:
  - They show which functions KNOW about the flag address
  - The function that loads the address and writes through it is the initial setter
""")

if __name__ == '__main__':
    main()
