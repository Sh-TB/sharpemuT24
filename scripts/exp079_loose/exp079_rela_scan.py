#!/usr/bin/env python3
"""EXP-079 TASK 2d: Scan RELA table for relocations whose addend is CLEAR's address."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000
TARGET = 0x800A9F750  # CLEAR

def main():
    img = ElfImage(EBOOT_PATH)
    
    # Get RELA info from dynamic
    dyn_seg = None
    for s in img.segments:
        if s['p_type'] == 2:
            dyn_seg = s
            break
    dyn_raw = img.raw[dyn_seg['p_offset']:dyn_seg['p_offset'] + dyn_seg['p_filesz']]
    info = {}
    for i in range(0, len(dyn_raw), 16):
        if i + 16 > len(dyn_raw): break
        d_tag, d_val = struct.unpack_from('<qQ', dyn_raw, i)
        if d_tag == 0: break
        info[d_tag] = d_val
    
    rela_vaddr = info.get(7)
    relasz = info.get(8)
    jmprel_vaddr = info.get(23)
    jmprel_size = info.get(2)
    
    print(f"RELA: vaddr=0x{rela_vaddr:X}, size=0x{relasz:X}")
    print(f"JMPREL: vaddr=0x{jmprel_vaddr:X}, size=0x{jmprel_size:X}")
    
    # Parse RELA entries (24 bytes each: r_offset, r_info, r_addend)
    if rela_vaddr and relasz:
        rela_off = img.vaddr_to_offset(rela_vaddr)
        n = relasz // 24
        print(f"\n  Total RELA entries: {n}")
        
        # Find entries with addend == TARGET (function pointer in init array)
        # And entries that target the address 0x801EA3230 (the slot we found)
        matches_target_addend = []
        targets_slot = []
        slot_runtime = 0x801EA3230
        slot_vaddr = slot_runtime - PS5_BASE  # 0x1EA3230
        
        # Also check for ALL stores that store to addresses near the init function's writes
        # The init function writes to:
        # 0x801EA32BC (from 0x800A9F2C3: mov [rip + 0x13f97f6], rax)
        #   target = 0x800A9F2C3 + 7 + 0x13f97f6 = 0x800A9F2CA + 0x013F97F6 = 0x801EA32C0
        # 0x801EA32B5 (from 0x800A9F2CA: mov [rip + 0x13f98eb], 0)
        #   target = 0x800A9F2CA + 11 + 0x013F98EB = 0x800A9F2D5 + 0x013F98EB = 0x801EA32C0
        # (size and alignment may differ)
        # Let me just compute all targets from the init function disassembly
        init_targets = {
            0x801EA32C0: 'from mov [rip+0x13f97f6], rax (0x800A9F2C3)',
            0x801EA32B4: 'from mov [rip+0x13f98eb], 0 (0x800A9F2CA)',  # need recompute
            0x801EA32B4 + 4: '... continuation',
            0x801EA32AE: 'from mov [rip+0x13f98e9], 0x4f (0x800A9F2D5)',
            0x801EA32A8: 'from mov [rip+0x13f98e6], 0x10 (0x800A9F2DF)',
            0x801EA3230: 'from mov [rip+0x13f9923], rcx (CLEAR ptr)',  # 0x800A9F306
            0x801EA3220: 'from mov [rip+0x13f9929], rcx (0x800A9F2F8)',
            0x801EA320D: 'from mov [rip+0x13f990c], rax (0x800A9F30D)',
            0x801EA320C: 'from mov byte [rip+0x13f990c], 0 (0x800A9F325)',
            0x801EA320D + 1: '...',
            0x801EA320A: 'from mov [rip+0x13f990a], 0 (0x800A9F333)',
        }
        
        # Better: scan RELA for entries that target any of these
        for i in range(n):
            off = rela_off + i * 24
            if off + 24 > len(img.raw): break
            r_offset, r_info, r_addend = struct.unpack_from('<QQq', img.raw, off)
            sym_idx = r_info >> 32
            rel_type = r_info & 0xFFFFFFFF
            
            # R_X86_64_RELATIVE = 8 — relocation: *r_offset = base + r_addend
            # R_X86_64_64 = 1 — *r_offset = S + r_addend (where S = symbol value)
            # R_X86_64_IRELATIVE = 37 — *r_offset = resolver(base + r_addend)
            
            # If addend matches CLEAR's offset (vaddr 0xA9F750) and type is RELATIVE
            if r_addend == 0xA9F750:  # vaddr of CLEAR
                matches_target_addend.append((r_offset, rel_type, r_addend, sym_idx))
            
            # If this reloc targets the slot we found
            if r_offset == slot_vaddr:
                targets_slot.append((r_offset, rel_type, r_addend, sym_idx))
        
        print(f"\n  RELA entries with addend=0x{0xA9F750:X} (CLEAR's vaddr): {len(matches_target_addend)}")
        for r_offset, rel_type, r_addend, sym_idx in matches_target_addend[:20]:
            rel_type_name = {1:'R_X86_64_64', 8:'R_X86_64_RELATIVE', 37:'R_X86_64_IRELATIVE'}.get(rel_type, f'TYPE_{rel_type}')
            runtime_offset = r_offset + PS5_BASE
            print(f"    reloc: file_vaddr=0x{r_offset:X} (runtime 0x{runtime_offset:X}) type={rel_type_name} addend=0x{r_addend:X} sym#{sym_idx}")
        
        print(f"\n  RELA entries targeting slot 0x{slot_vaddr:X} (runtime 0x{slot_runtime:X}): {len(targets_slot)}")
        for r_offset, rel_type, r_addend, sym_idx in targets_slot[:20]:
            rel_type_name = {1:'R_X86_64_64', 8:'R_X86_64_RELATIVE', 37:'R_X86_64_IRELATIVE'}.get(rel_type, f'TYPE_{rel_type}')
            print(f"    reloc: file_vaddr=0x{r_offset:X} type={rel_type_name} addend=0x{r_addend:X} sym#{sym_idx}")
    
    # Also search data segments for stored 8-byte address
    print(f"\n  Scanning data segments for stored 0x{TARGET:X}...")
    target_bytes = struct.pack('<Q', TARGET)
    found_in_data = []
    for seg in img.segments:
        if seg['p_type'] != 1: continue
        if seg['p_flags'] & 1: continue  # skip X
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        for i in range(len(seg_data) - 8):
            if seg_data[i:i+8] == target_bytes:
                runtime_addr = PS5_BASE + seg['p_vaddr'] + i
                found_in_data.append(runtime_addr)
    print(f"  Found in data: {len(found_in_data)}")
    for a in found_in_data[:10]:
        print(f"    0x{a:X}")
    
    # Also check .init_array — that's where 0x800A9F210 (the init function) should be registered
    init_array_vaddr = info.get(25)  # DT_INIT_ARRAY
    init_arraysz = info.get(27)  # DT_INIT_ARRAYSZ
    if init_array_vaddr:
        print(f"\n  DT_INIT_ARRAY: vaddr=0x{init_array_vaddr:X}, size=0x{init_arraysz:X}")
        ia_off = img.vaddr_to_offset(init_array_vaddr)
        n_init = init_arraysz // 8
        print(f"  Init array entries: {n_init}")
        for i in range(n_init):
            val = struct.unpack_from('<Q', img.raw, ia_off + i * 8)[0]
            runtime_addr = val + PS5_BASE if val < 0x10000000 else val
            print(f"    [{i}] = 0x{val:X} (runtime 0x{runtime_addr:X})")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
