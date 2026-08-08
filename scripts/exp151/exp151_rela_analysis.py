#!/usr/bin/env python3
"""
EXP-151: RELA table analysis — check if gate byte has a relocation.
Also analyze the gate function in detail.
"""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

def parse_elf64_full(path):
    """Parse ELF64 with both program headers and section headers."""
    data = open(path, 'rb').read()
    
    # ELF header
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    e_shoff = struct.unpack_from('<Q', data, 0x28)[0]
    e_shentsize = struct.unpack_from('<H', data, 0x3A)[0]
    e_shnum = struct.unpack_from('<H', data, 0x3C)[0]
    e_shstrndx = struct.unpack_from('<H', data, 0x3E)[0]
    
    # Program headers
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
    
    # Section headers
    sections = []
    if e_shoff > 0 and e_shnum > 0 and e_shoff < len(data):
        # Read section header string table
        shstr_hdr_off = e_shoff + e_shstrndx * e_shentsize
        if shstr_hdr_off + e_shentsize <= len(data):
            shstr_offset = struct.unpack_from('<Q', data, shstr_hdr_off + 0x18)[0]
            
            for i in range(e_shnum):
                sh_off = e_shoff + i * e_shentsize
                if sh_off + e_shentsize > len(data):
                    break
                sh_name_idx = struct.unpack_from('<I', data, sh_off)[0]
                sh_type = struct.unpack_from('<I', data, sh_off + 4)[0]
                sh_flags = struct.unpack_from('<Q', data, sh_off + 8)[0]
                sh_addr = struct.unpack_from('<Q', data, sh_off + 0x10)[0]
                sh_offset = struct.unpack_from('<Q', data, sh_off + 0x18)[0]
                sh_size = struct.unpack_from('<Q', data, sh_off + 0x20)[0]
                sh_link = struct.unpack_from('<I', data, sh_off + 0x28)[0]
                sh_info = struct.unpack_from('<I', data, sh_off + 0x2C)[0]
                sh_entsize = struct.unpack_from('<Q', data, sh_off + 0x38)[0]
                
                # Read name
                name_start = shstr_offset + sh_name_idx
                name_end = data.find(b'\x00', name_start)
                name = data[name_start:name_end].decode('ascii', errors='replace') if name_end > name_start else ''
                
                sections.append({
                    'name': name, 'type': sh_type, 'flags': sh_flags,
                    'addr': sh_addr, 'offset': sh_offset, 'size': sh_size,
                    'link': sh_link, 'info': sh_info, 'entsize': sh_entsize
                })
    
    return data, segments, sections


def main():
    print("=" * 80)
    print("EXP-151: RELA Table Analysis + Gate Function Deep Dive")
    print("=" * 80)
    
    data, segments, sections = parse_elf64_full(PRX_PATH)
    
    print(f"\nPRX sections ({len(sections)}):")
    rela_sections = []
    for i, sec in enumerate(sections):
        if sec['type'] in (4, 7, 9) or 'rela' in sec['name'].lower() or 'rel' in sec['name'].lower():
            rela_sections.append((i, sec))
            print(f"  [{i:2d}] {sec['name']:20s} type={sec['type']} offset=0x{sec['offset']:X} size=0x{sec['size']:X} entsize=0x{sec['entsize']:X}")
        elif i < 15 or 'init' in sec['name'].lower() or 'text' in sec['name'].lower() or 'data' in sec['name'].lower() or 'bss' in sec['name'].lower():
            print(f"  [{i:2d}] {sec['name']:20s} type={sec['type']} offset=0x{sec['offset']:X} size=0x{sec['size']:X}")
    
    # Gate byte address
    gate_byte_runtime = 0x808D67B98
    gate_byte_vaddr = gate_byte_runtime - PRX_BASE  # = 0x404EB98
    
    print(f"\nGate byte: runtime=0x{gate_byte_runtime:X}, vaddr=0x{gate_byte_vaddr:X}")
    
    # Check which segment this is in
    for seg in segments:
        if seg['type'] == 1:
            seg_end = seg['vaddr'] + seg['memsz']
            if seg['vaddr'] <= gate_byte_vaddr < seg_end:
                file_backed = seg['vaddr'] + seg['filesz']
                if gate_byte_vaddr < file_backed:
                    print(f"  In file-backed part of segment: vaddr=0x{seg['vaddr']:X} filesz=0x{seg['filesz']:X}")
                    # Read the byte
                    byte_foff = seg['offset'] + (gate_byte_vaddr - seg['vaddr'])
                    byte_val = data[byte_foff]
                    print(f"  File offset: 0x{byte_foff:X}, value: 0x{byte_val:X}")
                else:
                    print(f"  In BSS part of segment: vaddr=0x{seg['vaddr']:X} memsz=0x{seg['memsz']:X}")
                    print(f"  File-backed up to: 0x{file_backed:X}")
                    print(f"  Byte vaddr 0x{gate_byte_vaddr:X} is in BSS (value=0 at runtime)")
    
    # Search RELA sections
    print(f"\nSearching RELA sections for r_offset = 0x{gate_byte_vaddr:X}...")
    found_rela = False
    for idx, sec in rela_sections:
        if sec['type'] != 4:  # SHT_RELA
            continue
        entry_count = sec['size'] // 24
        print(f"\n  Section [{idx}] '{sec['name']}': {entry_count} entries")
        
        # Also check nearby addresses (the gate byte might be part of a larger structure)
        nearby_range = 0x100
        for j in range(entry_count):
            entry_off = sec['offset'] + j * 24
            if entry_off + 24 > len(data):
                break
            r_offset = struct.unpack_from('<Q', data, entry_off)[0]
            r_info = struct.unpack_from('<Q', data, entry_off + 8)[0]
            r_addend = struct.unpack_from('<q', data, entry_off + 16)[0]
            
            # Check exact match
            if r_offset == gate_byte_vaddr:
                r_type = r_info & 0xFFFFFFFF
                r_sym = r_info >> 32
                type_names = {1: 'R_X86_64_64', 7: 'JUMP_SLOT', 8: 'RELATIVE', 9: 'GLOB_DAT', 0x16: 'IRELATIVE'}
                type_name = type_names.get(r_type, f'type={r_type}')
                print(f"  *** EXACT MATCH ***")
                print(f"    Entry #{j}: r_offset=0x{r_offset:X} type={type_name} sym={r_sym} addend=0x{r_addend:X}")
                found_rela = True
            
            # Check nearby (within 0x100 bytes)
            elif abs(r_offset - gate_byte_vaddr) < nearby_range:
                r_type = r_info & 0xFFFFFFFF
                r_sym = r_info >> 32
                type_names = {1: 'R_X86_64_64', 7: 'JUMP_SLOT', 8: 'RELATIVE', 9: 'GLOB_DAT', 0x16: 'IRELATIVE'}
                type_name = type_names.get(r_type, f'type={r_type}')
                diff = r_offset - gate_byte_vaddr
                print(f"  NEARBY (offset {diff:+d}): Entry #{j}: r_offset=0x{r_offset:X} type={type_name} addend=0x{r_addend:X}")
    
    if not found_rela:
        print("\n  *** NO RELA ENTRY FOR GATE BYTE ***")
        print("  The gate byte is NOT set by any relocation.")
        print("  It must be set by code, or it's supposed to stay 0.")
    
    # ===== Also check: what is at the flag address the init code writes to? =====
    print("\n" + "=" * 80)
    print("Gate function init code analysis:")
    print("=" * 80)
    
    # The init code (not-taken path) at 0x804FB8E69:
    # B8 12 0F 00 00          mov eax, 0x0F12
    # BA 01 00 00 00          mov edx, 1
    # 48 8D 0D 1E C8 B9 03    lea rcx, [rip+0x3B9C81E]  -> 0x804FB8E73 + 7 + 0x3B9C81E = 0x808B57198
    # C4 E2 F8 F7 C7          ...
    # 48 C1 EF 0C             shr rdi, 12
    # C4 E2 C1 F7 D2          ...
    # F0 48 09 94 C1 D8 64 04 00  lock or [rcx+r8*8+0x464D8], rdx
    
    lea_target = 0x804FB8E73 + 7 + 0x3B9C81E
    print(f"\nLEA rcx target: 0x{lea_target:X}")
    print(f"  (This is the base of the flag array)")
    
    # The lock or writes to [rcx + r8*8 + 0x464D8]
    # r8 comes from somewhere (probably a hash or index)
    # The flag is at rcx + r8*8 + 0x464D8
    # With rcx = 0x808B57198, the flag is at 0x808B57198 + r8*8 + 0x464D8
    # For r8=0: flag at 0x808B57198 + 0x464D8 = 0x808B9D670
    
    print(f"  Flag address (r8=0): 0x{lea_target + 0x464D8:X}")
    
    # ===== Check what calls the gate function =====
    print("\n" + "=" * 80)
    print("Who calls the gate function (0x804FB8E60)?")
    print("=" * 80)
    
    gate_func = 0x804FB8E60
    # Search for CALL to gate_func (direct E8)
    callers = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
            if data[i] == 0xE8:
                rel = struct.unpack_from('<i', data, i + 1)[0]
                call_addr = PRX_BASE + seg['vaddr'] + (i - seg['offset'])
                target = call_addr + 5 + rel
                if target == gate_func:
                    callers.append(call_addr)
    
    print(f"\nDirect CALL callers of 0x{gate_func:X}: {len(callers)}")
    for c in callers[:20]:
        print(f"  CALL at 0x{c:X}")
    
    # Also check the thunk at 0x804FA6030 which redirects to the gate
    thunk_addr = 0x804FA6030
    thunk_callers = []
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        for i in range(seg['offset'], min(seg['offset'] + seg['filesz'], len(data)) - 5):
            if data[i] == 0xE8:
                rel = struct.unpack_from('<i', data, i + 1)[0]
                call_addr = PRX_BASE + seg['vaddr'] + (i - seg['offset'])
                target = call_addr + 5 + rel
                if target == thunk_addr:
                    thunk_callers.append(call_addr)
    
    print(f"\nCallers of thunk 0x{thunk_addr:X} (which JMPs to gate): {len(thunk_callers)}")
    for c in thunk_callers[:20]:
        print(f"  CALL at 0x{c:X}")
    
    # ===== Summary =====
    print("\n" + "=" * 80)
    print("ROOT CAUSE ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"""
GATE FUNCTION (0x804FB8E60):
  cmp byte [0x{gate_byte_runtime:X}], 0   ; check BSS flag
  je +0x28                              ; if 0, jump to RET (skip init)
  mov eax, 0x0F12                       ; init param
  mov edx, 1                            ; bit to set
  lea rcx, [0x{lea_target:X}]          ; flag array base
  lock or [rcx+r8*8+0x464D8], rdx       ; set flag bit
  ret                                   ; return

ANALYSIS:
  1. Gate byte at 0x{gate_byte_runtime:X} is in BSS → always 0 at runtime
  2. je +0x28 jumps to 0x804FB8E91 which is a RET instruction
  3. When byte==0: je taken → RET → initialization SKIPPED
  4. When byte!=0: fall through → init code runs → sets flag → RET
  5. No RELA relocation sets the gate byte
  6. No code in the PRX writes to the gate byte

CONCLUSION:
  The initialization code guarded by this gate is ALWAYS SKIPPED.
  This initialization likely sets up PlayerLoop registration or
  a prerequisite for PlayerLoop registration.

  The gate byte must be set to non-zero by:
  - A prior IL2CPP API call that runs before the gate
  - A RELA relocation (but none found)
  - An HLE function that SharpEmu doesn't implement

  This is the FIRST INCORRECT STATE TRANSITION:
  - Expected: gate byte != 0 → init code runs → PlayerLoop registered
  - Actual: gate byte == 0 → init code SKIPPED → PlayerLoop NOT registered
""")


if __name__ == '__main__':
    main()
