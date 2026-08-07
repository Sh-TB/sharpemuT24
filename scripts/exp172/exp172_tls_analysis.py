#!/usr/bin/env python3
"""EXP-172: TLS initialization validation — static analysis."""

import struct

EBOOT_PATH = "/tmp/exp162_games/eboot.bin"
PRX_PATH = "/tmp/exp162_games/Il2cppUserAssemblies.prx"
EBOOT_BASE = 0x800000000
PRX_BASE = 0x804CD5000

def parse_elf64_full(path):
    data = open(path, 'rb').read()
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]
    e_shoff = struct.unpack_from('<Q', data, 0x28)[0]
    e_shentsize = struct.unpack_from('<H', data, 0x3A)[0]
    e_shnum = struct.unpack_from('<H', data, 0x3C)[0]
    e_shstrndx = struct.unpack_from('<H', data, 0x3E)[0]
    
    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        p_flags = struct.unpack_from('<I', data, off + 4)[0]
        p_offset = struct.unpack_from('<Q', data, off + 8)[0]
        p_vaddr = struct.unpack_from('<Q', data, off + 16)[0]
        p_filesz = struct.unpack_from('<Q', data, off + 32)[0]
        p_memsz = struct.unpack_from('<Q', data, off + 40)[0]
        p_align = struct.unpack_from('<Q', data, off + 48)[0]
        segments.append({'type': p_type, 'flags': p_flags, 'offset': p_offset,
                         'vaddr': p_vaddr, 'filesz': p_filesz, 'memsz': p_memsz, 'align': p_align})
    
    return data, segments

def search_string(data, pattern):
    pat = pattern.encode('utf-8') + b'\x00'
    idx = data.find(pat)
    if idx >= 0:
        return idx
    return None

def search_symbol_in_strtab(data, segments, symbol_name, base):
    """Search for symbol name in string tables."""
    # Search in all readable segments
    pat = symbol_name.encode('utf-8') + b'\x00'
    hits = []
    for seg in segments:
        if seg['type'] != 1:
            continue
        sd = data[seg['offset']:seg['offset'] + seg['filesz']]
        idx = 0
        while True:
            i = sd.find(pat, idx)
            if i == -1:
                break
            runtime = base + seg['vaddr'] + i
            hits.append(runtime)
            idx = i + 1
    return hits

def main():
    eboot_data, eboot_segs = parse_elf64_full(EBOOT_PATH)
    prx_data, prx_segs = parse_elf64_full(PRX_PATH)
    
    print("=" * 80)
    print("EXP-172: TLS Initialization Validation (Static Analysis)")
    print("=" * 80)
    
    # ===== Check TLS segments (PT_TLS = 7) =====
    print("\n[1] TLS Segments (PT_TLS = 7):")
    
    for label, data, segs, base in [("EBOOT", eboot_data, eboot_segs, EBOOT_BASE),
                                     ("PRX", prx_data, prx_segs, PRX_BASE)]:
        tls_segs = [s for s in segs if s['type'] == 7]
        if tls_segs:
            for tls in tls_segs:
                print("  %s: vaddr=0x%X filesz=0x%X memsz=0x%X align=0x%X" % (
                    label, base + tls['vaddr'], tls['filesz'], tls['memsz'], tls['align']))
        else:
            print("  %s: NO PT_TLS segment" % label)
    
    # ===== Search for __tls_get_addr string =====
    print("\n[2] Search for '__tls_get_addr' string:")
    
    for label, data, segs, base in [("EBOOT", eboot_data, eboot_segs, EBOOT_BASE),
                                     ("PRX", prx_data, prx_segs, PRX_BASE)]:
        hits = search_symbol_in_strtab(data, segs, "__tls_get_addr", base)
        if hits:
            print("  %s: Found at %s" % (label, ', '.join('0x%X' % h for h in hits)))
        else:
            print("  %s: NOT FOUND" % label)
    
    # Also search for related TLS functions
    print("\n[3] Search for TLS-related strings:")
    tls_strings = ["__tls_get_addr", "tls_get_addr", "__tls", "TLS", "tls_init",
                   "__cxa_thread_atexit", "thread_local", "tcbhead", "tls_block"]
    for s in tls_strings:
        for label, data, segs, base in [("EBOOT", eboot_data, eboot_segs, EBOOT_BASE),
                                         ("PRX", prx_data, prx_segs, PRX_BASE)]:
            hits = search_symbol_in_strtab(data, segs, s, base)
            if hits:
                print("  '%s' in %s: %d hits (first: 0x%X)" % (s, label, len(hits), hits[0]))
    
    # ===== Search for __tls_get_addr as an import =====
    print("\n[4] Search for __tls_get_addr in dynamic symbol table:")
    
    # Check eboot dynamic entries for NEEDED libraries
    for label, data, segs, base in [("EBOOT", eboot_data, eboot_segs, EBOOT_BASE),
                                     ("PRX", prx_data, prx_segs, PRX_BASE)]:
        # Find PT_DYNAMIC
        dyn_seg = None
        for seg in segs:
            if seg['type'] == 2:  # PT_DYNAMIC
                dyn_seg = seg
                break
        
        if dyn_seg:
            # Parse dynamic entries
            entries = []
            for i in range(dyn_seg['filesz'] // 16):
                off = dyn_seg['offset'] + i * 16
                if off + 16 > len(data):
                    break
                d_tag = struct.unpack_from('<q', data, off)[0]
                d_val = struct.unpack_from('<Q', data, off + 8)[0]
                if d_tag == 0:
                    break
                entries.append((d_tag, d_val))
            
            # Find DT_STRTAB and DT_SYMTAB
            strtab_addr = None
            symtab_addr = None
            strsz = 0
            syment = 0
            for tag, val in entries:
                if tag == 5:  # DT_STRTAB
                    strtab_addr = val
                elif tag == 6:  # DT_SYMTAB
                    symtab_addr = val
                elif tag == 10:  # DT_STRSZ
                    strsz = val
                elif tag == 11:  # DT_SYMENT
                    syment = val
            
            if strtab_addr is not None and strsz > 0:
                # Search for __tls_get_addr in string table
                strtab_data = data[strtab_addr:strtab_addr + strsz]
                idx = strtab_data.find(b'__tls_get_addr\x00')
                if idx >= 0:
                    print("  %s: '__tls_get_addr' found in strtab at offset 0x%X" % (label, idx))
                else:
                    print("  %s: '__tls_get_addr' NOT in strtab" % label)
    
    # ===== Check SharpEmu source for __tls_get_addr =====
    print("\n[5] Check SharpEmu source for TLS handling:")
    
    # Check if __tls_get_addr is handled in the source
    import os
    src_dir = "/tmp/my-project/work/sharpemuT24/work/sharpemuT24/src"
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if f.endswith('.cs'):
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, 'r') as fh:
                        content = fh.read()
                    if '__tls_get_addr' in content or 'tls_get_addr' in content:
                        print("  Found in: %s" % fpath)
                except:
                    pass
    
    # Check for TLS-related handling
    print("\n[6] TLS-related code in SharpEmu:")
    tls_keywords = ['TlsAlloc', 'TlsInit', 'TlsSetup', '__tls', 'PT_TLS', 'tls_block', 
                    'TlsOffset', 'TlsIndex', 'ThreadLocalStorage']
    for kw in tls_keywords:
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith('.cs'):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, 'r') as fh:
                            content = fh.read()
                        if kw in content:
                            print("  '%s' found in: %s" % (kw, fpath))
                    except:
                        pass

if __name__ == '__main__':
    main()
