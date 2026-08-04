#!/usr/bin/env python3
"""
EXP-057 G3-T17: Co-occurring address reference finder.

Finds functions that reference BOTH CodeReg (0x8086E9000) AND MetaReg
(0x80885C580) within the same function body.

Strategy:
  1. For each target, find all RIP-relative refs (byte-level fast scan).
  2. For each ref, find the function it belongs to (walk back to INT3 padding).
  3. For each function, check if it has refs to BOTH targets.
  4. Report functions with co-occurring refs.

This is a reusable tool — add to scripts/ permanently.
"""
import struct
import sys

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000
EBOOT = "/tmp/games/yatzi/eboot.bin"
EBOOT_BASE = 0x800000000

TARGETS = {
    "CodeReg": 0x8086E9000,
    "MetaReg": 0x80885C580,
    "types[]": 0x80893E950,
    "methodPointers[]": 0x808791958,
}

def parse_segments(path, load_base):
    with open(path, "rb") as f:
        data = f.read()
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
            struct.unpack_from("<IIQQQQQQ", data, off)
        if p_type == 1:
            segments.append({
                "file_vaddr": p_vaddr, "filesz": p_filesz,
                "file_offset": p_offset, "flags": p_flags,
                "runtime_vaddr": p_vaddr + load_base,
                "content": data[p_offset:p_offset + p_filesz],
            })
    return data, segments

def find_rip_rel_refs(data, segments, load_base, target, insn_sizes=(7, 8)):
    """Find all RIP-relative refs to target via fast byte-level scan."""
    refs = []
    for seg in segments:
        if seg["flags"] & 1 == 0:  # not executable
            continue
        content = seg["content"]
        seg_runtime = seg["runtime_vaddr"]
        seg_file_vaddr = seg["file_vaddr"]
        n = len(content)
        for insn_size in insn_sizes:
            prefix_len = insn_size - 4
            for i in range(n - insn_size):
                expected_disp = target - load_base - (i + seg_file_vaddr) - insn_size
                if expected_disp < -0x80000000 or expected_disp > 0x7FFFFFFF:
                    continue
                actual = struct.unpack_from("<i", content, i + prefix_len)[0]
                if actual == expected_disp:
                    refs.append(seg_runtime + i)
    return refs

def find_func_start(data, segments, load_base, addr, max_back=0x2000):
    """Walk backwards from addr to find function start (INT3 + push pattern)."""
    for seg in segments:
        if seg["flags"] & 1 == 0:
            continue
        if seg["runtime_vaddr"] <= addr < seg["runtime_vaddr"] + seg["filesz"]:
            offset = addr - seg["runtime_vaddr"]
            content = seg["content"]
            for i in range(offset, max(0, offset - max_back), -1):
                if content[i] == 0xCC and i + 1 < len(content):
                    nb = content[i + 1]
                    if nb in (0x55, 0x53, 0x41, 0x48):
                        if i > 0 and content[i - 1] == 0xCC:
                            return seg["runtime_vaddr"] + i + 1
            return None
    return None

def main():
    print("=" * 78)
    print("EXP-057 G3-T17: Co-occurring address reference finder")
    print("=" * 78)

    # Parse PRX
    prx_data, prx_segments = parse_segments(PRX, PRX_BASE)
    print(f"\nPRX code segment: {sum(1 for s in prx_segments if s['flags'] & 1)} executable segment(s)")

    # Find refs to each target in PRX
    prx_refs = {}
    for name, target in TARGETS.items():
        refs = find_rip_rel_refs(prx_data, prx_segments, PRX_BASE, target)
        prx_refs[name] = refs
        print(f"  PRX refs to 0x{target:X} ({name}): {len(refs)}")

    # Find function for each ref
    prx_func_refs = {}  # func_start -> set of target names
    for name, refs in prx_refs.items():
        for ref_addr in refs:
            func_start = find_func_start(prx_data, prx_segments, PRX_BASE, ref_addr)
            if func_start:
                if func_start not in prx_func_refs:
                    prx_func_refs[func_start] = set()
                prx_func_refs[func_start].add(name)

    # Find functions with co-occurring refs
    print(f"\nFunctions with co-occurring refs (CodeReg + MetaReg):")
    co_occurring = []
    for func_start, targets in prx_func_refs.items():
        if "CodeReg" in targets and "MetaReg" in targets:
            co_occurring.append((func_start, targets))
            print(f"  0x{func_start:X}: refs={targets}")

    if not co_occurring:
        print("  NONE FOUND in PRX")

    # Also check functions referencing CodeReg + types[] or MetaReg + types[]
    print(f"\nFunctions referencing CodeReg + types[]:")
    for func_start, targets in prx_func_refs.items():
        if "CodeReg" in targets and "types[]" in targets:
            print(f"  0x{func_start:X}: refs={targets}")

    print(f"\nFunctions referencing MetaReg + types[]:")
    for func_start, targets in prx_func_refs.items():
        if "MetaReg" in targets and "types[]" in targets:
            print(f"  0x{func_start:X}: refs={targets}")

    # Parse eboot too
    eboot_data, eboot_segments = parse_segments(EBOOT, EBOOT_BASE)
    print(f"\nEboot code segment: {sum(1 for s in eboot_segments if s['flags'] & 1)} executable segment(s)")

    eboot_refs = {}
    for name, target in TARGETS.items():
        refs = find_rip_rel_refs(eboot_data, eboot_segments, EBOOT_BASE, target)
        eboot_refs[name] = refs
        print(f"  Eboot refs to 0x{target:X} ({name}): {len(refs)}")

    # Eboot functions with co-occurring refs
    eboot_func_refs = {}
    for name, refs in eboot_refs.items():
        for ref_addr in refs:
            func_start = find_func_start(eboot_data, eboot_segments, EBOOT_BASE, ref_addr)
            if func_start:
                if func_start not in eboot_func_refs:
                    eboot_func_refs[func_start] = set()
                eboot_func_refs[func_start].add(name)

    print(f"\nEboot functions with co-occurring refs (CodeReg + MetaReg):")
    for func_start, targets in eboot_func_refs.items():
        if "CodeReg" in targets and "MetaReg" in targets:
            print(f"  0x{func_start:X}: refs={targets}")

    # Summary
    print(f"\n{'=' * 78}")
    print("SUMMARY")
    print(f"{'=' * 78}")
    total_co = len(co_occurring)
    print(f"PRX functions referencing BOTH CodeReg and MetaReg: {total_co}")
    if total_co > 0:
        print(f"  -> These are consumer function candidates!")
        print(f"  -> Top candidate: 0x{co_occurring[0][0]:X}")

if __name__ == "__main__":
    main()
