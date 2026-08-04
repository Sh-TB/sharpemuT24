#!/usr/bin/env python3
"""EXP-079 TASK 5b: Find ALL code that signals a semaphore loaded from [reg+0x68]."""
import sys, struct
sys.path.insert(0, '/home/z/my-project/scripts')
from exp079_load_elf import ElfImage
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_REG_RIP, X86_OP_MEM, X86_OP_REG, X86_OP_IMM

EBOOT_PATH = "/tmp/games/yatzi/eboot.bin"
PRX_PATH = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PS5_BASE = 0x800000000

# SignalSema PLT address
SIGNALSEMA_PLT = 0x8019377B0

def scan_image_for_signal_pattern(img_path, img_label, base_offset):
    """Scan for 'call 0x8019377B0' (SignalSema) and check what was loaded before."""
    img = ElfImage(img_path)
    print(f"\n=== Scanning {img_label} for SignalSema call sites ===")
    
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    
    # Find all E8 calls to 0x8019377B0
    call_sites = []
    for seg in img.segments:
        if seg['p_type'] != 1 or not (seg['p_flags'] & 1):
            continue
        seg_data = img.raw[seg['p_offset']:seg['p_offset'] + seg['p_filesz']]
        for i in range(len(seg_data) - 5):
            if seg_data[i] == 0xE8:
                rel32 = struct.unpack_from('<i', seg_data, i + 1)[0]
                instr_runtime = base_offset + seg['p_vaddr'] + i
                target = instr_runtime + 5 + rel32
                if target == SIGNALSEMA_PLT:
                    call_sites.append(instr_runtime)
    
    print(f"  Found {len(call_sites)} call sites to SignalSema (0x{SIGNALSEMA_PLT:X})")
    
    # For each call site, disassemble 64 bytes before to see what was loaded into rdi
    interesting_patterns = []
    for site in call_sites:
        # Read 64 bytes before the call
        vaddr = site - base_offset
        before_vaddr = vaddr - 64
        if before_vaddr < img.min_vaddr:
            continue
        data = img.read_bytes(before_vaddr, 64 + 5)
        if data is None:
            continue
        # Disassemble the 64 bytes
        insns = list(md.disasm(data, site - 64))
        # Find the last "mov rdi, ..." instruction before the call
        last_rdi_load = None
        last_esi_load = None
        for ins in insns:
            if ins.address >= site:
                break
            if ins.mnemonic == 'mov' and ins.op_str.startswith('rdi,'):
                last_rdi_load = (ins.address, ins.op_str, ins.bytes.hex())
            elif ins.mnemonic == 'mov' and ins.op_str.startswith('esi,'):
                last_esi_load = (ins.address, ins.op_str, ins.bytes.hex())
        
        if last_rdi_load:
            # Check if rdi was loaded from [reg+0x68] or [rbx+0x68]
            rdi_src = last_rdi_load[1]
            if '0x68]' in rdi_src or '+ 0x68]' in rdi_src or '+0x68]' in rdi_src:
                interesting_patterns.append((site, last_rdi_load, last_esi_load))
    
    print(f"\n  Sites where rdi is loaded from [reg+0x68]: {len(interesting_patterns)}")
    for site, rdi_load, esi_load in interesting_patterns[:30]:
        print(f"    Call at 0x{site:X}:")
        print(f"      rdi: 0x{rdi_load[0]:X}: {rdi_load[2]} {rdi_load[1]}")
        if esi_load:
            print(f"      esi: 0x{esi_load[0]:X}: {esi_load[2]} {esi_load[1]}")
    
    # Also look at ALL call sites and their rdi source
    print(f"\n  All SignalSema call sites (with rdi source):")
    for site in call_sites[:50]:
        vaddr = site - base_offset
        before_vaddr = vaddr - 48
        if before_vaddr < img.min_vaddr:
            continue
        data = img.read_bytes(before_vaddr, 48 + 5)
        insns = list(md.disasm(data, site - 48))
        last_rdi_load = None
        for ins in insns:
            if ins.address >= site:
                break
            if ins.mnemonic == 'mov' and ins.op_str.startswith('rdi,'):
                last_rdi_load = (ins.address, ins.op_str)
        rdi_info = f"rdi={last_rdi_load[1]}" if last_rdi_load else "rdi=?"
        print(f"    0x{site:X}: {rdi_info}")
    
    return call_sites

def main():
    scan_image_for_signal_pattern(EBOOT_PATH, "EBOOT", PS5_BASE)
    # PRX is loaded at a different base — let's check SharpEmu source for the PRX load base
    return 0

if __name__ == "__main__":
    sys.exit(main())
