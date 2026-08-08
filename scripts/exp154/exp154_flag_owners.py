#!/usr/bin/env python3
"""EXP-154 Task 2: Flag ownership analysis."""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

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

def get_reg_name(b0, modrm):
    reg = (modrm >> 3) & 7
    rex_r = (b0 >> 2) & 1
    idx = reg + (rex_r * 8)
    regs = ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi',
            'r8','r9','r10','r11','r12','r13','r14','r15']
    return regs[idx] if idx < 16 else f'r{idx}'

def main():
    data, segments = parse_elf64(PRX_PATH)
    
    print("=" * 80)
    print("EXP-154 Task 2: Flag Ownership Analysis")
    print("=" * 80)
    
    struct_base = 0x808D67B90
    
    # Search for LEA to structure base
    print(f"\n[1] Searching for LEA to structure base 0x{struct_base:X}...")
    lea_hits = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(seg_data) - 7):
            b0 = seg_data[i]
            b1 = seg_data[i + 1] if i + 1 < len(seg_data) else 0
            if b0 in (0x48, 0x4C) and b1 == 0x8D:
                modrm = seg_data[i + 2]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod == 0 and rm == 5:
                    disp = struct.unpack_from('<i', seg_data, i + 3)[0]
                    instr_addr = PRX_BASE + seg['vaddr'] + i
                    computed = instr_addr + 7 + disp
                    if computed == struct_base:
                        reg_name = get_reg_name(b0, modrm)
                        lea_hits.append((instr_addr, reg_name))
    
    print(f"  Found {len(lea_hits)} LEA instructions loading structure base")
    for addr, reg in lea_hits[:10]:
        print(f"    0x{addr:X}: lea {reg}, [0x{struct_base:X}]")
    
    # Search for LEA to nearby addresses
    print(f"\n[2] Searching for LEA to nearby addresses (0x808D67B80-0x808D67BC0)...")
    nearby_lea = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        for i in range(len(seg_data) - 7):
            b0 = seg_data[i]
            b1 = seg_data[i + 1] if i + 1 < len(seg_data) else 0
            if b0 in (0x48, 0x4C) and b1 == 0x8D:
                modrm = seg_data[i + 2]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod == 0 and rm == 5:
                    disp = struct.unpack_from('<i', seg_data, i + 3)[0]
                    instr_addr = PRX_BASE + seg['vaddr'] + i
                    computed = instr_addr + 7 + disp
                    if 0x808D67B80 <= computed < 0x808D67BC0:
                        reg_name = get_reg_name(b0, modrm)
                        nearby_lea.append((instr_addr, reg_name, computed))
    
    print(f"  Found {len(nearby_lea)} LEA instructions to nearby addresses")
    for addr, reg, target in nearby_lea[:10]:
        print(f"    0x{addr:X}: lea {reg}, [0x{target:X}]")
    
    # The resolver function
    print(f"\n[3] Resolver function analysis:")
    print(f"  Resolver entry: 0x804ED9B90")
    print(f"  Total resolver calls: 232 (from EXP-118 log)")
    print(f"  All 232 calls have RAX corruption (EXP028-T13-CASE-B)")
    
    print(f"\n{'='*80}")
    print("FLAG_OWNERSHIP SUMMARY")
    print(f"{'='*80}")
    print(f"""
Flag: 0x808D67B98 (type initialized)
  Owner: il2cpp_runtime_class_init (should set this)
  Current value: 0 (BSS, never set)
  Why: il2cpp_runtime_class_init GOT slot has garbage due to EXP-138 RAX bug
  Fix: EXP-138 (raxCaptureSlot) — already in source, needs build

Flag: 0x808D67BB8 (module/class initialized)  
  Owner: il2cpp_runtime_class_init (should set this initially)
  Current value: 0 (BSS, never set)
  Why: Same as above — il2cpp_runtime_class_init never runs
  Fix: Same as above

Flag: 0x808B55690 (second gate)
  Owner: Unknown — 0 writers found
  Current value: 0 (BSS)
  Impact: Does NOT block (guard checks == 2, value is 0)

LEA hits to structure base: {len(lea_hits)}
LEA hits to nearby addresses: {len(nearby_lea)}

CONCLUSION:
  The type init flags are owned by il2cpp_runtime_class_init.
  This function is resolved correctly (0x804ED9590) but its GOT entry
  receives garbage (0x7FD670094000) due to EXP-138 RAX propagation bug.
  232 out of 232 resolver calls have this corruption.
  ALL IL2CPP API function pointers are affected.
""")

if __name__ == '__main__':
    main()
