#!/usr/bin/env python3
"""EXP-097 Step 4: Search for indirect call instructions (call [reg], call [reg+offset],
call [rip+disp]) that could dispatch to the 4 dead-code functions.

Also search for the function addresses as immediate values in MOV instructions
(mov reg, imm64) that could then be stored to memory.
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


def find_indirect_calls_near_targets(elf, image_base, targets):
    """Find all indirect call instructions (FF /2 — call [reg] or call [reg+disp])
    in the PRX executable segment. These are the dispatch points that could call
    any of the dead-code functions via a function pointer."""
    
    indirect_calls = []
    
    for seg in elf.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1):
            continue
        seg_vaddr = seg['p_vaddr']
        seg_bytes = elf.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        
        # FF /2 = call [reg] or call [reg+disp]
        # Patterns: FF 15 disp32 (call [rip+disp32]), FF D0-D7 (call reg), 
        #           FF 14 70-77 (call [reg*1]), FF 54 24 disp8 (call [rsp+disp8]), etc.
        # The most common for function pointer dispatch is FF 15 disp32 (call [rip+disp32])
        
        i = 0
        while i < len(seg_bytes) - 6:
            if seg_bytes[i] == 0xFF:
                modrm = seg_bytes[i + 1]
                reg_field = (modrm >> 3) & 0x07
                mod_field = (modrm >> 6) & 0x03
                rm_field = modrm & 0x07
                
                if reg_field == 2:  # /2 = call
                    insn_addr = image_base + seg_vaddr + i
                    target_desc = ""
                    
                    if mod_field == 0 and rm_field == 5:  # [rip+disp32]
                        disp32 = struct.unpack_from('<i', seg_bytes, i + 2)[0]
                        target_addr = insn_addr + 6 + disp32
                        target_desc = f"call [rip+0x{disp32 & 0xFFFFFFFFFFFFFFFF:X}] -> [0x{target_addr:X}]"
                        indirect_calls.append((insn_addr, "rip-relative", target_addr))
                    elif mod_field == 3:  # call reg (direct register)
                        regs = ["rax","rcx","rdx","rbx","rsp","rbp","rsi","rdi"]
                        reg = regs[rm_field]
                        target_desc = f"call {reg}"
                        indirect_calls.append((insn_addr, "reg", 0))
                    elif mod_field == 0 and rm_field != 4 and rm_field != 5:
                        regs = ["rax","rcx","rdx","rbx","rsp","rbp","rsi","rdi"]
                        reg = regs[rm_field]
                        target_desc = f"call [{reg}]"
                        indirect_calls.append((insn_addr, "mem-reg", 0))
                    
                    i += 2  # skip past FF + modrm
                    continue
            i += 1
    
    return indirect_calls


def main():
    prx = ElfImage(PRX_PATH)
    
    print("===== Step 4: Find indirect call instructions in PRX =====")
    print("Searching for: FF 15 disp32 (call [rip+disp32]), FF D0-D7 (call reg), FF /2 [reg]")
    print()
    
    indirect_calls = find_indirect_calls_near_targets(prx, PRX_BASE, set(TARGETS))
    
    # Count by type
    by_type = {}
    for insn_addr, call_type, target_addr in indirect_calls:
        by_type.setdefault(call_type, []).append((insn_addr, target_addr))
    
    print(f"Total indirect call instructions: {len(indirect_calls)}")
    for call_type, entries in by_type.items():
        print(f"  {call_type}: {len(entries)}")
    
    # For rip-relative calls, check if any target a global that could hold one of our function addresses
    rip_relative = by_type.get("rip-relative", [])
    print(f"\n===== RIP-relative indirect calls ({len(rip_relative)}) =====")
    print("These call [global_var] — checking if any global is near our targets...")
    
    # The dead-code function addresses are in the 0x804F456E0..0x804FA210F range
    # Globals that store function pointers would be in the RW data segment
    # Let's list all unique rip-relative call targets
    unique_targets = set()
    for insn_addr, target_addr in rip_relative:
        unique_targets.add(target_addr)
    
    print(f"Unique RIP-relative call targets: {len(unique_targets)}")
    
    # Check which of these targets are in the RW data segment (function pointer globals)
    rw_globals_called = []
    for target in sorted(unique_targets):
        file_vaddr = target - PRX_BASE
        for seg in prx.segments:
            if seg['p_type'] == 1 and seg['p_vaddr'] <= file_vaddr < seg['p_vaddr'] + seg['p_memsz']:
                flags = ''
                if seg['p_flags'] & 4: flags += 'R'
                if seg['p_flags'] & 2: flags += 'W'
                if seg['p_flags'] & 1: flags += 'X'
                if 'W' in flags:  # RW data segment = function pointer global
                    # Read the initial value
                    offset_in_seg = file_vaddr - seg['p_vaddr']
                    if offset_in_seg < seg['p_filesz']:
                        file_off = seg['p_offset'] + offset_in_seg
                        val = struct.unpack_from('<Q', prx.raw, file_off)[0]
                        # Count how many call sites target this global
                        caller_count = sum(1 for _, t in rip_relative if t == target)
                        rw_globals_called.append((target, val, caller_count))
                break
    
    print(f"\nRW data globals called via [rip+disp]: {len(rw_globals_called)}")
    for target, val, count in rw_globals_called[:30]:
        val_str = f"0x{val:016X}"
        marker = ""
        if val in TARGETS:
            marker = f" *** MATCHES {LABELS[TARGETS.index(val)]} ***"
        elif val == 0:
            val_str = "0x0 (NULL — set at runtime)"
            marker = " *** RUNTIME-SET FUNCTION POINTER ***"
        elif val == 0xFFFFFFFFFFFFFFFF:
            val_str = "0xFFFF... (sentinel)"
        print(f"  [0x{target:X}] = {val_str}  ({count} call sites){marker}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
