#!/usr/bin/env python3
"""EXP-038 Task 5: Find il2cpp_codegen_register in the PRX.

In standard IL2CPP, il2cpp_codegen_register registers all metadata
(code registration, metadata registration). It's typically called
during il2cpp_init.

Let me search for this symbol in the PRX's export table.
"""
import struct
from pathlib import Path

PRX = Path("/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx")
data = PRX.read_bytes()

# Parse ELF
e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
e_phnum = struct.unpack_from('<H', data, 0x38)[0]
e_phentsize = struct.unpack_from('<H', data, 0x36)[0]

# Find PT_DYNAMIC
dyn_foff = None
dyn_size = 0
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type = struct.unpack_from('<I', data, off)[0]
    if p_type == 2:
        dyn_foff = struct.unpack_from('<Q', data, off + 8)[0]
        dyn_size = struct.unpack_from('<Q', data, off + 32)[0]
        break

# Parse dynamic entries
dt = {}
i = 0
while i < dyn_size:
    d_tag, d_val = struct.unpack_from('<qQ', data, dyn_foff + i)
    if d_tag == 0: break
    dt[d_tag] = d_val
    i += 16

# Get STRTAB and SYMTAB
strtab_addr = dt.get(5, 0)
strtab_size = dt.get(10, 0)
symtab_addr = dt.get(6, 0)
syment = dt.get(11, 24)

# Also check SCE-specific strtab/symtab
sce_strtab = dt.get(0x61000016, strtab_addr)
sce_strsz = dt.get(0x61000017, strtab_size)
sce_symtab = dt.get(0x61000018, symtab_addr)
sce_symtabsz = dt.get(0x61000019, 0)

print(f"STRTAB: 0x{strtab_addr:X} size=0x{strtab_size:X}")
print(f"SYMTAB: 0x{symtab_addr:X} syment={syment}")
print(f"SCE_STRTAB: 0x{sce_strtab:X} size=0x{sce_strsz:X}")
print(f"SCE_SYMTAB: 0x{sce_symtab:X} size=0x{sce_symtabsz:X}")

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

# Read string table
strtab_foff = vaddr_to_foff(strtab_addr)
if strtab_foff:
    strtab_data = data[strtab_foff:strtab_foff + strtab_size]
    # Search for il2cpp_codegen_register and related strings
    search_strings = [
        b'il2cpp_codegen_register',
        b'il2cpp_codegen_initialize',
        b'il2cpp_codegen_initialize_runtime_metadata',
        b'il2cpp_register',
        b'Il2CppCodeRegistration',
        b'Il2CppMetadataRegistration',
        b's_Il2CppCodegenRegistration',
        b'sCodeGenRegistration',
        b'RegisterCodegenMetadata',
        b'il2cpp_init',
        b'il2cpp_add_internal_call',
    ]
    
    print("\n=== Searching string table for registration symbols ===")
    for s in search_strings:
        pos = strtab_data.find(s)
        if pos >= 0:
            # Read the full null-terminated string
            end = strtab_data.find(b'\x00', pos)
            full_str = strtab_data[pos:end].decode('ascii', errors='replace')
            print(f"  FOUND: '{full_str}' at strtab offset 0x{pos:X}")

# Read symbol table and look for registration functions
symtab_foff = vaddr_to_foff(symtab_addr)
if symtab_foff and strtab_foff:
    # Estimate number of symbols
    # We don't have SYMTABSZ for standard, try SCE
    symtab_size = sce_symtabsz if sce_symtabsz else 0
    if symtab_size == 0:
        # Estimate from the next section
        symtab_size = 0x10000  # arbitrary
    
    num_syms = symtab_size // syment if symtab_size else 1000
    print(f"\n=== Searching symbol table ({num_syms} symbols) ===")
    
    for i in range(num_syms):
        off = symtab_foff + i * syment
        if off + syment > len(data):
            break
        st_name, st_info, st_other, st_shndx, st_value, st_size = \
            struct.unpack_from('<IBBHQQ', data, off)
        if st_name == 0:
            continue
        # Read name from strtab
        if st_name < len(strtab_data):
            end = strtab_data.find(b'\x00', st_name)
            name = strtab_data[st_name:end].decode('ascii', errors='replace')
            # Check for registration-related symbols
            if any(kw in name.lower() for kw in ['register', 'codegen', 'metadata', 'init']):
                bind = st_info >> 4
                typ = st_info & 0xf
                bind_names = {0: 'LOCAL', 1: 'GLOBAL', 2: 'WEAK'}
                type_names = {0: 'NOTYPE', 1: 'OBJECT', 2: 'FUNC', 3: 'SECTION'}
                print(f"  [{i}] {name}: value=0x{st_value:X} bind={bind_names.get(bind,'?')} type={type_names.get(typ,'?')}")
