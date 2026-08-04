#!/usr/bin/env python3
"""EXP-079 TASK 2e: Find callers of the init function at 0x800A9F210."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PS5_BASE = 0x800000000

TARGETS = [0x800A9F210, 0x800A9F8E0, 0x800A9F910]

def main():
    img = ElfImage(EBOOT_PATH)
    target_bytes_le_8 = {t: struct.pack('<Q', t) for t in TARGETS}
    
    print(f"=== Searching for callers/references to {[hex(t) for t in TARGETS]} ===")
    
    for tgt in TARGETS:
        print(f"\n--- Target 0x{tgt:X} ---")
        direct_calls = []
        lea_refs = []
        ptr_refs = []
        
        # Scan executable segments for CALL/JMP rel32
        for seg in img.segments:
            if seg['p_type'] != 1: continue
            if not (seg['p_flags'] & 1): continue
            seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
            for i in range(len(seg_data) - 5):
                if seg_data[i] in (0xE8, 0xE9):
                    rel32 = struct.unpack_from('<i', seg_data, i + 1)[0]
                    instr_runtime = PS5_BASE + seg['p_vaddr'] + i
                    target_runtime = instr_runtime + 5 + rel32
                    if target_runtime == tgt:
                        direct_calls.append((instr_runtime, seg_data[i]))
            # LEA r64, [rip+disp32] = 48 8D /r with mod=00 r/m=101
            # Encodings: 48 8D 05 (rax), 0D (rcx), 15 (rdx), 1D (rbx), 25 (rsp-), 2D (rbp), 35 (rsi), 3D (rdi)
            # Also 4C 8D 05 (r8), 0D (r9), 15 (r10), 1D (r11), 25 (r12), 2D (r13), 35 (r14), 3D (r15)
            lea_prefixes = [b'\x48\x8d\x05', b'\x48\x8d\x0d', b'\x48\x8d\x15', b'\x48\x8d\x1d',
                            b'\x48\x8d\x2d', b'\x48\x8d\x35', b'\x48\x8d\x3d',
                            b'\x4c\x8d\x05', b'\x4c\x8d\x0d', b'\x4c\x8d\x15', b'\x4c\x8d\x1d',
                            b'\x4c\x8d\x25', b'\x4c\x8d\x2d', b'\x4c\x8d\x35', b'\x4c\x8d\x3d']
            for i in range(len(seg_data) - 7):
                for prefix in lea_prefixes:
                    if seg_data[i:i+3] == prefix:
                        disp32 = struct.unpack_from('<i', seg_data, i + 3)[0]
                        instr_runtime = PS5_BASE + seg['p_vaddr'] + i
                        target_runtime = instr_runtime + 7 + disp32
                        if target_runtime == tgt:
                            lea_refs.append((instr_runtime, prefix.hex()))
                        break
            # Pointer-sized literal in code (rare)
            for i in range(len(seg_data) - 8):
                if seg_data[i:i+8] == target_bytes_le_8[tgt]:
                    instr_runtime = PS5_BASE + seg['p_vaddr'] + i
                    ptr_refs.append(instr_runtime)
        
        # Scan non-executable segments for stored pointers
        for seg in img.segments:
            if seg['p_type'] != 1: continue
            if seg['p_flags'] & 1: continue  # skip X (already scanned)
            seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
            for i in range(len(seg_data) - 8):
                if seg_data[i:i+8] == target_bytes_le_8[tgt]:
                    runtime_addr = PS5_BASE + seg['p_vaddr'] + i
                    ptr_refs.append(runtime_addr)
        
        # Scan RELA for addend = tgt's vaddr
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
        rela_off = img.vaddr_to_offset(info.get(7, 0))
        relasz = info.get(8, 0)
        n_rela = relasz // 24
        rela_matches = []
        tgt_vaddr = tgt - PS5_BASE
        for i in range(n_rela):
            off = rela_off + i * 24
            if off + 24 > len(img.raw): break
            r_offset, r_info, r_addend = struct.unpack_from('<QQq', img.raw, off)
            if r_addend == tgt_vaddr:
                rela_matches.append((r_offset, r_info & 0xFFFFFFFF, r_addend))
        
        print(f"  Direct CALL/JMP: {len(direct_calls)}")
        for addr, op in direct_calls[:10]:
            print(f"    0x{addr:X}: {'CALL' if op==0xE8 else 'JMP'} 0x{tgt:X}")
        print(f"  LEA references: {len(lea_refs)}")
        for addr, prefix in lea_refs[:10]:
            print(f"    0x{addr:X}: LEA ({prefix}) 0x{tgt:X}")
        print(f"  Pointer-sized in data: {len(ptr_refs)}")
        for addr in ptr_refs[:10]:
            print(f"    0x{addr:X}: PTR 0x{tgt:X}")
        print(f"  RELA addend matches: {len(rela_matches)}")
        for r_off, r_type, r_add in rela_matches[:10]:
            rel_type_name = {1:'R_X86_64_64', 8:'R_X86_64_RELATIVE', 37:'R_X86_64_IRELATIVE'}.get(r_type, f'TYPE_{r_type}')
            print(f"    reloc at 0x{r_off:X} type={rel_type_name} addend=0x{r_add:X} → runtime 0x{r_off+PS5_BASE:X}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
