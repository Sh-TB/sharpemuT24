#!/usr/bin/env python3
"""EXP-153 Step 2: Search for writes to ALL related flags."""

import struct

PRX_PATH = "/tmp/exp151_games/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

# Flags identified in writer function 1:
# 0x808D67BB8 — FIRST guard (function entry) — if 0, return early
# 0x808D67B98 — SECOND guard (before write) — target flag, if 0 skip write
# 0x808B55690 — THIRD guard — if == 2, skip write

TARGETS = [0x808D67BB8, 0x808D67B98, 0x808B55690]

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

def search_writes(data, segments, target_addr, load_base):
    """Search for WRITE instructions (not cmp/test) to target_addr."""
    writers = []
    write_opcodes = {0xC6, 0xC7, 0x88, 0x89, 0x80, 0x81, 0x83, 0x09, 0x01, 0x08, 0x21, 0x31, 0xFE, 0xF6}
    
    for seg in segments:
        if seg['type'] != 1 or not (seg['flags'] & 1):
            continue
        seg_data = data[seg['offset']:seg['offset'] + seg['filesz']]
        
        for i in range(len(seg_data) - 11):
            for prefix_len in range(0, 2):
                if prefix_len == 1:
                    p = seg_data[i]
                    if p not in (0xF0, 0x48, 0x4C, 0x66):
                        continue
                opcode_offset = prefix_len
                if i + opcode_offset >= len(seg_data):
                    continue
                opcode = seg_data[i + opcode_offset]
                if opcode not in write_opcodes:
                    continue
                modrm_offset = opcode_offset + 1
                if i + modrm_offset >= len(seg_data):
                    continue
                modrm = seg_data[i + modrm_offset]
                mod = (modrm >> 6) & 3
                rm = modrm & 7
                if mod != 0 or rm != 5:
                    continue
                disp_offset = modrm_offset + 1
                if i + disp_offset + 4 > len(seg_data):
                    continue
                disp = struct.unpack_from('<i', seg_data, i + disp_offset)[0]
                reg = (modrm >> 3) & 7
                base_len = disp_offset + 4
                imm_len = 0
                if opcode in (0xC6, 0x80, 0x83, 0xFE, 0xF6):
                    imm_len = 1
                elif opcode in (0xC7, 0x81):
                    imm_len = 4
                instr_len = base_len + imm_len
                instr_addr = load_base + seg['vaddr'] + i
                computed = instr_addr + instr_len + disp
                
                if computed == target_addr:
                    # Skip CMP (read-only)
                    is_cmp = (opcode in (0x80, 0x81, 0x83) and reg == 7)
                    is_test = (opcode == 0xF6 and reg in (0, 1))
                    if is_cmp or is_test:
                        continue
                    prefix_str = ''
                    if prefix_len == 1:
                        p = seg_data[i]
                        if p == 0xF0: prefix_str = 'lock '
                        elif p in (0x48, 0x4C): prefix_str = 'rex.W '
                    raw = seg_data[i:i+instr_len].hex()
                    writers.append({
                        'address': instr_addr,
                        'instruction': f'{prefix_str}0x{opcode:02X} reg={reg}',
                        'raw_bytes': raw,
                    })
                    break
    return writers

def main():
    data, segments = parse_elf64(PRX_PATH)
    
    for target in TARGETS:
        print(f"\n{'='*80}")
        print(f"Searching for writes to 0x{target:X}")
        print(f"{'='*80}")
        
        # Check if in BSS
        target_vaddr = target - PRX_BASE
        for seg in segments:
            if seg['type'] == 1:
                end = seg['vaddr'] + seg['memsz']
                if seg['vaddr'] <= target_vaddr < end:
                    file_backed = seg['vaddr'] + seg['filesz']
                    if target_vaddr < file_backed:
                        byte_foff = seg['offset'] + (target_vaddr - seg['vaddr'])
                        byte_val = data[byte_foff]
                        print(f"  Location: file-backed data, value = 0x{byte_val:X}")
                    else:
                        print(f"  Location: BSS (value = 0 at runtime)")
                    break
        
        writers = search_writes(data, segments, target, PRX_BASE)
        print(f"  Writers found: {len(writers)}")
        for w in writers:
            print(f"    0x{w['address']:X}: {w['instruction']} bytes={w['raw_bytes']}")
        
        if len(writers) == 0:
            print(f"  *** NO WRITES — flag is NEVER set ***")
    
    # Now search for the FIRST guard flag (0x808D67BB8) more broadly
    # This flag controls whether the writer function runs at all
    print(f"\n{'='*80}")
    print(f"Key question: Does 0x808D67BB8 get set to non-zero?")
    print(f"{'='*80}")
    print(f"""
If 0x808D67BB8 is set to non-zero:
  → Writer function 0x804FB1B90 continues past first guard
  → Second guard checks 0x808D67B98
  → If 0x808D67B98 is 0, write is SKIPPED (but function continues)
  → If 0x808D67B98 is non-0, write is SKIPPED (already set)

Wait — the second guard is:
  cmp byte [0x808D67B98], 0
  je +0x17 (skip write if flag == 0)

This means: if flag == 0, SKIP the write. If flag != 0, continue to the write.
But if flag != 0, it's ALREADY set! Why write again?

This is a "set flag if not already set" pattern, but inverted:
  if (flag == 0) skip;  ← skip if NOT set
  else set flag = 1;   ← set if ALREADY set (redundant!)

This doesn't make sense. Let me re-examine the conditional jump.

Actually, looking at the bytes again:
  0x804FB1C05: 83 3D 8C 5F DB 03 00   cmp byte [0x808D67B98], 0
  0x804FB1C0C: 74 17                    je +0x17 → 0x804FB1C25

  0x804FB1C0E: 83 3D 7B 3A BA 03 02   cmp byte [0x808B55690], 2
  0x804FB1C15: 0F 84 DA 00 00 00       je +0xDA → 0x804FB1CF5

  0x804FB1C1B: C7 05 73 5F DB 03 01 00 00 00   mov dword [0x808D67B98], 1

The je at 0x804FB1C0C jumps to 0x804FB1C25 (PAST the mov instruction).
So if flag == 0: jump PAST the write (SKIP write)
If flag != 0: fall through to check second condition, then write.

This is indeed inverted from what I'd expect. The write only happens if:
1. 0x808D67B98 != 0 (already initialized)
2. 0x808B55690 != 2 (another condition)

And the write sets 0x808D67B98 = 1 (which it already is, since we checked != 0).

This looks like a "refresh" or "re-initialize" pattern, NOT an initial setter.

The INITIAL setter must be somewhere else entirely.
""")

if __name__ == '__main__':
    main()
