#!/usr/bin/env python3
"""EXP-038 Task 5b: Search PRX string table for registration symbols."""
import struct
from pathlib import Path

PRX = Path("/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx")
data = PRX.read_bytes()

e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

def vaddr_to_foff(vaddr):
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type != 1: continue
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        if p_vaddr <= vaddr < p_vaddr + p_filesz:
            return p_offset + (vaddr - p_vaddr)
    return None

# STRTAB at vaddr 0x4094780, size 0x2684
strtab_vaddr = 0x4094780
strtab_size = 0x2684
strtab_foff = vaddr_to_foff(strtab_vaddr)

if strtab_foff:
    strtab = data[strtab_foff:strtab_foff + strtab_size]
    print(f"String table: {len(strtab)} bytes")
    
    # Extract all strings
    strings = []
    idx = 0
    while idx < len(strtab):
        end = strtab.find(b'\x00', idx)
        if end < 0:
            end = len(strtab)
        s = strtab[idx:end]
        if len(s) > 0:
            strings.append((idx, s.decode('ascii', errors='replace')))
        idx = end + 1
    
    print(f"Total strings: {len(strings)}")
    
    # Search for registration-related strings
    print("\n=== Registration-related strings ===")
    for off, s in strings:
        sl = s.lower()
        if any(kw in sl for kw in ['register', 'codegen', 'metadata', 'init', 'il2cpp']):
            print(f"  0x{off:X}: '{s}'")
    
    # Also print ALL strings (they might be NIDs or short names)
    print(f"\n=== All strings (first 50) ===")
    for off, s in strings[:50]:
        print(f"  0x{off:X}: '{s}'")
    
    # Check if any string looks like a NID (11 chars, alphanumeric)
    print(f"\n=== NID-like strings (first 20) ===")
    nid_count = 0
    for off, s in strings:
        if len(s) == 11 and s.isalnum():
            print(f"  0x{off:X}: '{s}'")
            nid_count += 1
            if nid_count >= 20:
                break
    print(f"  ... total NID-like: {sum(1 for _, s in strings if len(s) == 11 and s.isalnum())}")
