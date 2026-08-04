#!/usr/bin/env python3
"""
EXP-112 step 5 — find all callers of 0x804f3e660 (the SECOND writer to
the gate global). If this function runs before real_init's call #152,
it might set the gate to non-zero, causing #152 to be skipped.

Also: find all callers of 0x804f3df90 (call #152 target / first writer)
so we know all the entry points that could trigger the gate-set logic.

Also: check the value both writers write — they both write `esi`. Find
the callers and check what they pass in rsi.
"""
import os
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, CS_OP_IMM

PRX_PATH = "/tmp/games/yatzi/Il2cppUserAssemblies.prx"
PRX_RUNTIME_BASE = 0x804CD5000


def load_prx_text():
    with open(PRX_PATH, "rb") as f:
        data = f.read()
    elf = ELFFile(BytesIO(data))
    for i in range(elf["e_phnum"]):
        hdr = elf._get_segment_header(i)
        seg = Segment(hdr, elf.stream)
        if seg["p_type"] == "PT_LOAD" and (seg["p_flags"] & 1):
            return seg["p_vaddr"], seg.data()
    raise RuntimeError("no exec segment")


def find_callers(text_data, text_base, target_elf_va):
    """
    Find all `call rel32` instructions whose target is target_elf_va.
    call rel32 is encoded as E8 + 4-byte rel32 (little-endian).
    Target = (call_instruction_address + 5) + rel32.
    So rel32 = target_elf_va - (call_instruction_address + 5).

    We can compute the expected rel32 for each potential call site and
    search for the byte pattern E8 + rel32_le.
    """
    # We need to scan all 5-byte sequences starting with E8 and check if they
    # decode to a call to target_elf_va.
    # Faster: for each position p in text, check if text[p] == 0xE8 and
    # (p + 5 + rel32) == target_elf_va.
    n = len(text_data)
    callers = []
    target = target_elf_va
    
    # Use a stride of 1 (byte-by-byte) but only check positions where byte == 0xE8
    # This is much faster than full disasm.
    pos = 0
    while pos < n - 5:
        if text_data[pos] == 0xE8:
            rel32 = struct.unpack_from('<i', text_data, pos + 1)[0]
            call_target = (text_base + pos + 5 + rel32) & 0xFFFFFFFF
            if call_target == target:
                callers.append(text_base + pos)  # elf_va of call site
        pos += 1
    
    return callers


def find_function_for_site(site_elf_va, sorted_func_starts):
    """Return the function start VA containing site_elf_va."""
    from bisect import bisect_right
    if not sorted_func_starts:
        return None
    idx = bisect_right(sorted_func_starts, site_elf_va)
    if idx == 0:
        return None
    return sorted_func_starts[idx - 1]


def main():
    text_base, text_data = load_prx_text()
    print(f"[+] text_base=0x{text_base:x}  size=0x{len(text_data):x}")

    # Build function-start table
    n = len(text_data)
    align = 16
    func_starts = []
    for off in range(0, n, align):
        if off >= 16 and text_data[off-1] != 0xCC:
            tail = text_data[max(0, off-8):off]
            if 0xCC not in tail:
                continue
        if off + 4 <= n:
            sig = text_data[off:off+4]
            if (sig == b"\xF3\x0F\x1E\xFA" or
                sig[0] == 0x55 or
                (sig[0] == 0x41 and sig[1] in (0x54,0x55,0x56,0x57)) or
                (sig[0] == 0x48 and sig[1] == 0x83 and sig[2] == 0xEC) or
                (sig[0] == 0x48 and sig[1] == 0x81 and sig[2] == 0xEC)):
                func_starts.append(text_base + off)
    sorted_starts = sorted(func_starts)
    print(f"[+] function starts: {len(sorted_starts)}")

    targets = [
        (0x269660, "0x804F3E660 (second gate writer)"),
        (0x268f90, "0x804F3DF90 (call #152 target / first gate writer)"),
        (0x269450, "0x804F3E450 (called by BOTH writers — investigate)"),
        (0x26a0c0, "0x804F3F0C0 (called by #152)"),
        (0x1eb9e0, "0x804EB99E0 (called by second writer's loop)"),
    ]

    for target_elf, label in targets:
        print()
        print("=" * 78)
        print(f"Callers of {label}")
        print("=" * 78)
        callers = find_callers(text_data, text_base, target_elf)
        print(f"  total callers: {len(callers)}")
        for site_elf in callers[:30]:
            func_start = find_function_for_site(site_elf, sorted_starts)
            site_rt = site_elf + PRX_RUNTIME_BASE
            func_rt = (func_start + PRX_RUNTIME_BASE) if func_start else None
            print(f"  call site elf=0x{site_elf:x}  runtime=0x{site_rt:x}  in func 0x{func_rt:x}" if func_rt else f"  call site elf=0x{site_elf:x}  runtime=0x{site_rt:x}  (no containing func)")
        if len(callers) > 30:
            print(f"  ... ({len(callers)-30} more)")


if __name__ == "__main__":
    main()
