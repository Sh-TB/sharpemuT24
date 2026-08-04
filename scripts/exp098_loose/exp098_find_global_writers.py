#!/usr/bin/env python3
"""EXP-098: Find what WRITES to the 7 working function pointer globals.

The 7 globals from EXP-097 are all populated at runtime:
  0x808B417E0 = 0x804F09550
  0x808B417E8 = 0x800C76C60
  0x808B417F8 = 0x800C76CA0
  0x808B418E8 = 0x804FB0B30
  0x808B418F0 = 0x804FBF820  (35 call sites)
  0x808B41900 = 0x804FBF760  (15 call sites)
  0x808B41938 = 0x804D49340

Plus the once-init guard that's NOT cleared:
  0x808B418D8 = 0xFFFFFFFFFFFFFFFF (sentinel, never cleared)

Strategy: search for `mov [rip+disp32], reg` instructions that target these
addresses. The writes tell us WHICH functions populate the globals, and those
functions are the "correct mechanism" template.

Also search for writes to the dead-code function addresses themselves —
maybe they're written to a DIFFERENT global (not one of the 7 we found).
"""

import sys
import struct

sys.path.insert(0, "/home/z/my-project/scripts")
from exp079_load_elf import ElfImage, PRX_PATH

PRX_BASE = 0x804CD5000

# The 7 working globals + the once-init guard
WORKING_GLOBALS = [
    0x808B417E0,
    0x808B417E8,
    0x808B417F8,
    0x808B418D8,  # once-init guard (sentinel)
    0x808B418E8,
    0x808B418F0,  # 35 call sites
    0x808B41900,  # 15 call sites
    0x808B41938,
]

# The 5 dead-code functions
DEAD_CODE = [
    0x804F456E0,
    0x804F9FA80,
    0x804FA1440,
    0x804FA1FE0,
    0x804F6EC20,
]

def find_writers_to_globals(elf, image_base, targets):
    """Find all `mov [rip+disp32], reg` instructions that write to any target address.
    
    Pattern: 48 89 XX disp32 (REX.W + MOV r/m64, r64)
    where XX has mod=00, rm=101 (RIP-relative)
    
    Also search for:
    - mov [rip+disp], imm32 (C7 05 disp32 imm32)
    - lea + mov (indirect writes via register)
    """
    writers = []
    target_set = set(targets)
    
    for seg in elf.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1):
            continue
        seg_vaddr = seg['p_vaddr']
        seg_bytes = elf.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        
        for i in range(len(seg_bytes) - 7):
            b0, b1, b2 = seg_bytes[i], seg_bytes[i+1], seg_bytes[i+2]
            
            # Pattern 1: 48 89 XX disp32 — mov [rip+disp32], reg64
            # XX = 05 (rax), 0D (rcx), 15 (rdx), 1D (rbx), 2D (rbp), 35 (rsi), 3D (rdi)
            #      05,0D,15,1D,25,2D,35,3D for 48 prefix
            #      05,0D,15,1D,25,2D,35,3D for 4C prefix (r8-r15)
            is_mov_rip = False
            reg = ""
            
            if b0 in (0x48, 0x4C) and b1 == 0x89:
                mod = (b2 >> 6) & 3
                rm = b2 & 7
                if mod == 0 and rm == 5:  # [rip+disp32]
                    is_mov_rip = True
                    reg_field = (b2 >> 3) & 7
                    regs = ["rax","rcx","rdx","rbx","rsp","rbp","rsi","rdi"]
                    reg = regs[reg_field]
                    if b0 == 0x4C:
                        reg = "r" + str(reg_field + 8)
            
            # Pattern 2: C7 05 disp32 imm32 — mov [rip+disp32], imm32
            elif b0 == 0xC7 and b1 == 0x05:
                disp32 = struct.unpack_from('<i', seg_bytes, i + 2)[0]
                insn_addr = image_base + seg_vaddr + i
                target = insn_addr + 6 + disp32  # RIP after = insn_addr + 6 (C7 05 + 4 bytes disp)
                # Actually: C7 05 disp32 imm32 = 2 + 4 + 4 = 10 bytes
                # RIP after disp32 = insn_addr + 6
                target = insn_addr + 6 + disp32
                if target in target_set:
                    imm32 = struct.unpack_from('<i', seg_bytes, i + 6)[0]
                    writers.append((insn_addr, "mov [rip], imm32", target, f"imm32=0x{imm32 & 0xFFFFFFFF:X}"))
                continue
            
            if is_mov_rip:
                disp32 = struct.unpack_from('<i', seg_bytes, i + 3)[0]
                insn_addr = image_base + seg_vaddr + i
                target = insn_addr + 7 + disp32  # 48 89 XX + 4 bytes disp = 7 bytes total
                if target in target_set:
                    writers.append((insn_addr, f"mov [rip], {reg}", target, ""))
    
    return writers


def main():
    prx = ElfImage(PRX_PATH)
    
    print("===== Searching for WRITES to the 8 globals (7 working + 1 guard) =====")
    print(f"Targets: {', '.join(f'0x{a:X}' for a in WORKING_GLOBALS)}")
    print()
    
    writers = find_writers_to_globals(prx, PRX_BASE, WORKING_GLOBALS)
    
    print(f"Total write instructions found: {len(writers)}")
    print()
    
    # Group by target
    by_target = {}
    for insn_addr, mnemonic, target, extra in writers:
        by_target.setdefault(target, []).append((insn_addr, mnemonic, extra))
    
    for target in WORKING_GLOBALS:
        writes = by_target.get(target, [])
        label = ""
        if target == 0x808B418D8:
            label = " (once-init guard — 0xFFFF... at runtime)"
        elif target == 0x808B418F0:
            label = " (35 call sites — most used)"
        elif target == 0x808B41900:
            label = " (15 call sites)"
        print(f"\n  0x{target:X}{label}: {len(writes)} write(s)")
        for insn_addr, mnemonic, extra in writes[:5]:
            print(f"    0x{insn_addr:X}: {mnemonic} -> 0x{target:X}  {extra}")
    
    # Now check: are any of these write instructions inside functions that are
    # actually called? Find the function containing each write.
    print("\n\n===== Functions containing the writes =====")
    for target in WORKING_GLOBALS:
        writes = by_target.get(target, [])
        for insn_addr, mnemonic, extra in writes[:3]:
            # Find function start by scanning backward for push rbp preceded by int3/ret
            func_start = None
            for offset in range(0, 0x1000, 1):
                check_addr = insn_addr - offset
                raw = prx.read_bytes(check_addr - PRX_BASE, 4)
                if raw is None:
                    continue
                if raw[0] == 0x55 and raw[1] == 0x48 and raw[2] == 0x89 and raw[3] == 0xE5:
                    prev = prx.read_bytes(check_addr - PRX_BASE - 1, 1)
                    if prev and (prev[0] == 0xCC or prev[0] == 0xC3):
                        func_start = check_addr
                        break
            if func_start:
                # Find callers of this function
                callers = []
                for seg in prx.segments:
                    if seg['p_type'] != 1 or not (seg['p_flags'] & 1):
                        continue
                    seg_vaddr = seg['p_vaddr']
                    seg_bytes = prx.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
                    for j in range(len(seg_bytes) - 5):
                        if seg_bytes[j] == 0xE8:
                            rel32 = struct.unpack_from('<i', seg_bytes, j + 1)[0]
                            call_addr = PRX_BASE + seg_vaddr + j
                            tgt = call_addr + 5 + rel32
                            if tgt == func_start:
                                callers.append(call_addr)
                print(f"  Write at 0x{insn_addr:X} -> 0x{target:X}: in function 0x{func_start:X} ({len(callers)} callers)")
            else:
                print(f"  Write at 0x{insn_addr:X} -> 0x{target:X}: function start not found within 0x1000 bytes")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
