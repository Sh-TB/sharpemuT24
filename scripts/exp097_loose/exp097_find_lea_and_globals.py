#!/usr/bin/env python3
"""EXP-097 Step 2+3: Search for RIP-relative LEA instructions that compute the
addresses of the 4 dead-code functions, and check the IL2CPP registration globals.

If the function addresses don't appear as stored qwords in data segments (Step 1
found 0 hits), they must be computed at runtime via LEA rip+disp32 and then stored
somewhere. Finding LEA instructions that compute these addresses tells us WHERE
the function pointers are being stored.

Also reads the 3 IL2CPP registration globals (0x808B542E8/F0/F8) from the PRX
data segment to check if any of them contain (directly or indirectly) the dead-code
function addresses.
"""

import os
import sys
import struct

sys.path.insert(0, "/home/z/my-project/scripts")
from exp079_load_elf import ElfImage, PRX_PATH

PRX_BASE = 0x804CD5000

TARGETS = [
    0x804F456E0,  # contains call site #1
    0x804F9FA80,  # contains call site #2
    0x804FA1440,  # contains call site #3
    0x804FA1FE0,  # contains caller of site#2's function
    0x804F6EC20,  # the work-submission function itself
]

LABELS = ["site#1 func", "site#2 func", "site#3 func", "caller of site#2", "work-submit func"]

# IL2CPP registration globals (from EXP-093)
IL2CPP_GLOBALS = {
    0x808B542E8: "Il2CppCodeRegistration* (saved by il2cpp_codegen_register)",
    0x808B542F0: "Il2CppMetadataRegistration* (saved by il2cpp_codegen_register)",
    0x808B542F8: "method pointers array (saved by il2cpp_codegen_register)",
}


def find_lea_targets(elf, image_base, targets):
    """Find all LEA instructions (48 8D xx rel32 or 4C 8D xx rel32) that compute
    any of the target addresses via RIP-relative addressing."""
    hits = []
    
    for seg in elf.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1):  # executable only
            continue
        seg_vaddr = seg['p_vaddr']
        seg_bytes = elf.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        
        # Scan for LEA patterns:
        # 48 8D 05 disp32  = lea rax, [rip+disp32]
        # 48 8D 0D disp32  = lea rcx, [rip+disp32]
        # 48 8D 15 disp32  = lea rdx, [rip+disp32]
        # 48 8D 1D disp32  = lea rbx, [rip+disp32]
        # 48 8D 2D disp32  = lea rbp, [rip+disp32]
        # 48 8D 35 disp32  = lea rsi, [rip+disp32]
        # 48 8D 3D disp32  = lea rdi, [rip+disp32]
        # 4C 8D 05 disp32  = lea r8,  [rip+disp32]
        # 4C 8D 0D disp32  = lea r9,  [rip+disp32]
        # 4C 8D 15 disp32  = lea r10, [rip+disp32]
        # 4C 8D 1D disp32  = lea r11, [rip+disp32]
        # 4C 8D 25 disp32  = lea r12, [rip+disp32]
        # 4C 8D 2D disp32  = lea r13, [rip+disp32]
        # 4C 8D 35 disp32  = lea r14, [rip+disp32]
        # 4C 8D 3D disp32  = lea r15, [rip+disp32]
        
        for i in range(len(seg_bytes) - 7):
            b0, b1, b2 = seg_bytes[i], seg_bytes[i+1], seg_bytes[i+2]
            is_lea = False
            reg = ""
            if b0 == 0x48 and b1 == 0x8D and (b2 & 0xC7) == 0x05:
                is_lea = True
                reg_num = (b2 >> 3) & 0x07
                regs = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"]
                reg = regs[reg_num]
            elif b0 == 0x4C and b1 == 0x8D and (b2 & 0xC7) == 0x05:
                is_lea = True
                reg_num = (b2 >> 3) & 0x07
                regs = ["r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]
                reg = regs[reg_num]
            
            if is_lea:
                disp32 = struct.unpack_from('<i', seg_bytes, i + 3)[0]
                insn_addr = image_base + seg_vaddr + i
                # RIP after the instruction = insn_addr + 7
                target_addr = insn_addr + 7 + disp32
                if target_addr in targets:
                    hits.append((insn_addr, reg, target_addr))
    
    return hits


def read_il2cpp_globals(elf, image_base):
    """Read the 3 IL2CPP registration globals and their pointed-to data."""
    results = {}
    for global_addr, desc in IL2CPP_GLOBALS.items():
        file_vaddr = global_addr - image_base
        # Read the 8-byte pointer value from the data segment
        ptr_val = elf.read_u64(file_vaddr)
        if ptr_val is not None:
            results[global_addr] = (ptr_val, desc)
            # Also try to read what the pointer points to (first 64 bytes)
            if ptr_val != 0:
                pointed_file_vaddr = ptr_val - image_base
                pointed_data = elf.read_bytes(pointed_file_vaddr, 64)
                if pointed_data:
                    results[global_addr] = (ptr_val, desc, pointed_data)
                else:
                    results[global_addr] = (ptr_val, desc, None)
            else:
                results[global_addr] = (ptr_val, desc, None)
        else:
            results[global_addr] = (None, desc, None)
    return results


def main():
    prx = ElfImage(PRX_PATH)
    
    print("===== Step 2: Find LEA instructions that compute dead-code function addresses =====")
    print(f"Searching for LEA rip+disp32 instructions targeting the 5 dead-code addresses...")
    print()
    
    lea_hits = find_lea_targets(prx, PRX_BASE, set(TARGETS))
    print(f"LEA hits: {len(lea_hits)}")
    
    # Group by target
    by_target = {}
    for insn_addr, reg, target_addr in lea_hits:
        by_target.setdefault(target_addr, []).append((insn_addr, reg))
    
    for target_addr in TARGETS:
        label = LABELS[TARGETS.index(target_addr)]
        hits_for_this = by_target.get(target_addr, [])
        print(f"\n  0x{target_addr:X} ({label}): {len(hits_for_this)} LEA instructions")
        for insn_addr, reg in hits_for_this[:10]:
            print(f"    0x{insn_addr:X}: lea {reg}, [rip+...] -> 0x{target_addr:X}")
    
    print()
    print("===== Step 3: Read IL2CPP registration globals =====")
    globals_data = read_il2cpp_globals(prx, PRX_BASE)
    
    for global_addr, (ptr_val, desc, pointed_data) in globals_data.items():
        display_val = ptr_val if ptr_val is not None else 0
        print(f"\n  [0x{global_addr:X}] = 0x{display_val:X}  ({desc})")
        if pointed_data:
            print(f"    Pointed-to data (first 64 bytes):")
            for i in range(0, 64, 8):
                val = struct.unpack_from('<Q', pointed_data, i)[0]
                # Check if this value matches any target
                marker = ""
                if val in TARGETS:
                    marker = f" *** MATCHES {LABELS[TARGETS.index(val)]} ***"
                print(f"      +0x{i:02X}: 0x{val:016X}{marker}")
        elif ptr_val == 0:
            print(f"    (NULL — zero-initialized, set at runtime)")
        else:
            print(f"    (cannot read pointed-to data — out of PRX file range)")
    
    # Summary
    print()
    print("===== SUMMARY =====")
    print(f"LEA hits total: {len(lea_hits)}")
    for target_addr in TARGETS:
        label = LABELS[TARGETS.index(target_addr)]
        count = len(by_target.get(target_addr, []))
        print(f"  0x{target_addr:X} ({label}): {count} LEA instructions compute this address")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
