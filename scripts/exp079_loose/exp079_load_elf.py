#!/usr/bin/env python3
"""EXP-079: Robust ELF loader - use program headers only (PS5 eboot has bad section headers)."""
import sys, os, struct
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_REG, CS_OP_MEM, CS_OP_IMM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PRX_PATH = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"

class ElfImage:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.raw = f.read()
        # Parse ELF header only
        if self.raw[:4] != b'\x7fELF':
            raise ValueError(f"not ELF: {path}")
        # 64-bit little-endian
        e_phoff = struct.unpack_from('<Q', self.raw, 0x20)[0]
        e_phnum = struct.unpack_from('<H', self.raw, 0x38)[0]
        e_phent = struct.unpack_from('<H', self.raw, 0x36)[0]
        e_entry = struct.unpack_from('<Q', self.raw, 0x18)[0]
        self.entry = e_entry
        self.segments = []
        for i in range(e_phnum):
            off = e_phoff + i * e_phent
            p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
                struct.unpack_from('<IIQQQQQQ', self.raw, off)
            self.segments.append({
                'p_type': p_type, 'p_flags': p_flags, 'p_offset': p_offset,
                'p_vaddr': p_vaddr, 'p_paddr': p_paddr, 'p_filesz': p_filesz,
                'p_memsz': p_memsz, 'p_align': p_align
            })
        # Build virtual address space from PT_LOAD segments
        self.min_vaddr = min(s['p_vaddr'] for s in self.segments if s['p_type'] == 1) if any(s['p_type']==1 for s in self.segments) else 0
        self.max_vaddr = max(s['p_vaddr'] + s['p_memsz'] for s in self.segments if s['p_type'] == 1) if any(s['p_type']==1 for s in self.segments) else 0
        # Allocate memory image
        self.memsize = self.max_vaddr - self.min_vaddr
        self.mem = bytearray(self.memsize)
        self.loaded_segs = []
        for s in self.segments:
            if s['p_type'] == 1:  # PT_LOAD
                start = s['p_vaddr'] - self.min_vaddr
                data = self.raw[s['p_offset']:s['p_offset'] + s['p_filesz']]
                self.mem[start:start+len(data)] = data
                self.loaded_segs.append((s['p_vaddr'], s['p_vaddr']+s['p_memsz'], s['p_flags']))
    
    def vaddr_to_offset(self, vaddr):
        """Convert runtime vaddr to file offset (uses file content if available, else mem image)."""
        for s in self.segments:
            if s['p_type'] == 1 and s['p_vaddr'] <= vaddr < s['p_vaddr'] + s['p_filesz']:
                return s['p_offset'] + (vaddr - s['p_vaddr'])
        return None
    
    def read_bytes(self, vaddr, size):
        """Read bytes at virtual address from memory image."""
        if vaddr < self.min_vaddr or vaddr + size > self.max_vaddr:
            return None
        off = vaddr - self.min_vaddr
        return bytes(self.mem[off:off + size])
    
    def read_u64(self, vaddr):
        b = self.read_bytes(vaddr, 8)
        if b is None or len(b) < 8:
            return None
        return struct.unpack('<Q', b)[0]
    
    def read_u32(self, vaddr):
        b = self.read_bytes(vaddr, 4)
        if b is None or len(b) < 4:
            return None
        return struct.unpack('<I', b)[0]
    
    def read_u8(self, vaddr):
        b = self.read_bytes(vaddr, 1)
        if b is None or len(b) < 1:
            return None
        return b[0]

def main():
    print("=== EBOOT ===")
    e = ElfImage(EBOOT_PATH)
    print(f"  size: {len(e.raw)} bytes")
    print(f"  entry: 0x{e.entry:X}")
    print(f"  vaddr range: 0x{e.min_vaddr:X} .. 0x{e.max_vaddr:X}")
    print(f"  segments ({len(e.segments)}):")
    for s in e.segments:
        if s['p_type'] == 1:  # PT_LOAD
            flags = ''
            if s['p_flags'] & 4: flags += 'R'
            if s['p_flags'] & 2: flags += 'W'
            if s['p_flags'] & 1: flags += 'X'
            print(f"    LOAD vaddr=0x{s['p_vaddr']:X} off=0x{s['p_offset']:X} filesz=0x{s['p_filesz']:X} memsz=0x{s['p_memsz']:X} flags={flags}")
    
    # Try mapping CLEAR addr 0x800A9F750
    for tgt_name, tgt_addr in [("CLEAR", 0x800A9F750), ("Gate", 0x800AA0207), ("SignalSema_ret", 0x800AA0223)]:
        off = e.vaddr_to_offset(tgt_addr)
        in_mem = e.min_vaddr <= tgt_addr < e.max_vaddr
        print(f"\n  {tgt_name} 0x{tgt_addr:X}: file_off={('0x%X'%off) if off else 'NONE'} in_mem={in_mem}")
        if in_mem:
            b = e.read_bytes(tgt_addr, 16)
            if b:
                print(f"    bytes: {b.hex()}")
    
    print("\n=== PRX (Il2cppUserAssemblies) ===")
    p = ElfImage(PRX_PATH)
    print(f"  size: {len(p.raw)} bytes")
    print(f"  entry: 0x{p.entry:X}")
    print(f"  vaddr range: 0x{p.min_vaddr:X} .. 0x{p.max_vaddr:X}")
    print(f"  segments ({len(p.segments)}):")
    for s in p.segments:
        if s['p_type'] == 1:
            flags = ''
            if s['p_flags'] & 4: flags += 'R'
            if s['p_flags'] & 2: flags += 'W'
            if s['p_flags'] & 1: flags += 'X'
            print(f"    LOAD vaddr=0x{s['p_vaddr']:X} off=0x{s['p_offset']:X} filesz=0x{s['p_filesz']:X} memsz=0x{s['p_memsz']:X} flags={flags}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
