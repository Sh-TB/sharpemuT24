#!/usr/bin/env python3
"""
EXP-111 (filtered, FAST byte-pattern scan) — find all `call [reg+0x08]`
and `mov rXX, [reg+0x08]; ...; call rXX` sites in Il2cppUserAssemblies.prx
using direct byte-pattern search (no capstone sweep over the entire text).

Then:
1. Map each site to its containing function (heuristic INT3-padding function starts)
2. Cross-reference containing function vs. known reachable cluster
3. If hits exist, list them; if none, declare mechanism unreachable for this subsystem

Output: /home/z/my-project/scripts/exp111/exp111_sites.json + summary
"""
import json
import os
import re
from collections import defaultdict
from bisect import bisect_right
from io import BytesIO

from elftools.elf.elffile import ELFFile
from elftools.elf.segments import Segment

PRX_PATH = "/tmp/games/yatzi/Il2cppUserAssemblies.prx"
PRX_RUNTIME_BASE = 0x804CD5000

KNOWN_REACHABLE = {
    0x804F04BA0: "real_init (IL2CPP init)",
    0x804F527C0: "parent of registration (calls 0x804FA20E0)",
    0x804FA20E0: "registration function (reached)",
    0x804F889D0: "registration helper (reached)",
    0x804F88A76: "callback storage xchg [r14], rax",
    0x804FC33B0: "once-init primitive (returns eax=0)",
}

# Also known to be reached indirectly (callers of registration chain)
# These were observed reached in prior EXPs:
#  - 0x804F527F9 is the call site inside 0x804F527C0 that calls 0x804FA20E0
# We will also include the *containing* function of any KNOWN_REACHABLE address
# in the cluster check, in case the entry was a mid-function address (like 0x804F88A76).
# So we resolve to function-start for each known address too.


def load_prx():
    with open(PRX_PATH, "rb") as f:
        data = f.read()
    return ELFFile(BytesIO(data)), data


def iter_segments_safe(elf):
    for i in range(elf["e_phnum"]):
        hdr = elf._get_segment_header(i)
        yield Segment(hdr, elf.stream)


def find_exec_segment(elf):
    for seg in iter_segments_safe(elf):
        if seg["p_type"] == "PT_LOAD" and (seg["p_flags"] & 1):
            return seg
    raise RuntimeError("no executable PT_LOAD segment found")


def find_function_starts_from_padding(text_data, text_elf_base):
    """Heuristic: function starts at 16-byte aligned offsets preceded by 0xCC padding
    and beginning with a known prologue signature."""
    starts = set()
    n = len(text_data)
    align = 16
    for off in range(0, n, align):
        if off >= 16 and text_data[off-1] != 0xCC:
            tail = text_data[max(0, off-8):off]
            if 0xCC not in tail:
                continue
        if off + 4 <= n:
            sig = text_data[off:off+4]
            if (sig == b"\xF3\x0F\x1E\xFA" or                  # endbr64
                sig[0] == 0x55 or                                # push rbp
                (sig[0] == 0x41 and sig[1] in (0x54,0x55,0x56,0x57)) or  # push r1x
                (sig[0] == 0x48 and sig[1] == 0x83 and sig[2] == 0xEC) or  # sub rsp, imm8
                (sig[0] == 0x48 and sig[1] == 0x81 and sig[2] == 0xEC) or  # sub rsp, imm32
                (sig[0] == 0x48 and sig[1] == 0x89 and sig[2] == 0x5C) or  # mov [rsp+...], r11 (rare)
                (sig[0] == 0x48 and sig[1] == 0x83 and sig[2] == 0xEC) or
                (sig[0] == 0xF2 and sig[1] == 0x0F and sig[2] == 0x10)):   # movsd xmm0, ...
                starts.add(text_elf_base + off)
    return starts


def containing_function(va, sorted_starts):
    if not sorted_starts:
        return None
    idx = bisect_right(sorted_starts, va)
    if idx == 0:
        return None
    return sorted_starts[idx - 1]


# ---------- Byte patterns for `call [reg+0x08]` (Pattern A) ----------
#
# x86_64 encoding for `call qword ptr [reg+0x08]`:
#   For rax..rdi (no REX needed):  FF 5X 08  where X = reg (rax=0..rdi=7)
#     but rax..rdi with mod=01 (disp8), reg=010 (CALL r/m), r/m = reg
#     ModR/M = 0b01_010_rrr = 0x50 + rrr
#     - rax(0)=0x50, rcx(1)=0x51, rdx(2)=0x52, rbx(3)=0x53,
#       rsp(4)=0x54 NEEDS SIB (special: 0x54 means "SIB follows"),
#       rbp(5)=0x55, rsi(6)=0x56, rdi(7)=0x57
#   For r8..r15 (REX.B needed):  41 FF 5X 08 with same r/m encoding (rsp/r12 special)
#
# `call [rsp+0x08]` is encoded as:  FF 54 24 08     (SIB byte 0x24 = base=rsp, index=none, scale=1)
# `call [r12+0x08]` is encoded as:  41 FF 54 24 08  (REX.B + same SIB)
#
# Note: `[rbp+0x08]` encoding with mod=01 disp8 — that's standard `FF 55 08`
# (rbp DOES NOT need a SIB byte; only rsp does among low regs).

PATTERN_A_REGEX_BYTES = []

# rax..rdi (low regs, no REX)
# rsp (rrr=4) special — needs SIB
low_regs_no_rex = [
    (0, "rax"), (1, "rcx"), (2, "rdx"), (3, "rbx"),
    (5, "rbp"), (6, "rsi"), (7, "rdi"),
]
for rm, name in low_regs_no_rex:
    modrm = 0x50 | rm   # 0b01_010_rrr
    PATTERN_A_REGEX_BYTES.append((bytes([0xFF, modrm, 0x08]), name, None))

# rsp (rrr=4): SIB follows. SIB=0x24 means base=rsp, no index, scale=1.
PATTERN_A_REGEX_BYTES.append((bytes([0xFF, 0x54, 0x24, 0x08]), "rsp", None))

# r8..r15 (REX.B = 0x41 prefix), r/m = reg-8
high_regs = [
    (8,  "r8"),  (9,  "r9"),  (10, "r10"), (11, "r11"),
    (12, "r12"), (13, "r13"), (14, "r14"), (15, "r15"),
]
for rm, name in high_regs:
    if name == "r12":
        # rsp/r12 special — SIB byte follows
        PATTERN_A_REGEX_BYTES.append((bytes([0x41, 0xFF, 0x54, 0x24, 0x08]), name, None))
    else:
        modrm = 0x50 | (rm - 8)
        PATTERN_A_REGEX_BYTES.append((bytes([0x41, 0xFF, modrm, 0x08]), name, None))


# ---------- Byte patterns for `mov rXX, [reg+0x08]` (Pattern B, load half) ----------
#
# We only need the LOAD half — Pattern B is "load then call same reg".
# Encoding: `mov r64, r/m64` is REX.W + 8B /r (or REX.W + 8A /r for 8-bit; we want 64-bit so 8B).
# The destination reg is encoded in the /r (reg field), the source is r/m (the memory operand).
#
# We want ANY destination register, ANY source register, disp=8.
# So pattern: [REX] 8B [modrm = 01_rrr_mmm] 08
#   - REX.W must be set (W=1). REX.R extends the dst reg; REX.B extends the src reg.
#   - Possible REX prefixes: 0x48 (W only), 0x49 (W+B), 0x4C (W+R), 0x4D (W+R+B)
#   - ModR/M byte: mod=01, reg=any (dst), r/m=any (src) — but rsp(4)/r12(12) need SIB
#   - For mod=01, r/m=4 → SIB follows (1 extra byte before the disp8)
#   - For mod=01, r/m=5 (rbp/r13) → it's actually [rbp+disp8] (NOT rip-relative; that's mod=00 r/m=5)
#     So rbp/r13 with mod=01 + disp8 is fine.
#
# Constructing a single regex covering all cases:
#   - 4 REX prefixes × 8 dst_reg × 8 src_reg combinations, minus the SIB ones.
#   - Easier: just scan with two regex variants.
#
# Variant 1: load from non-SIB source (rax..rdi except rsp; r8..r15 except r12)
#   [REX] 8B [modrm=01_xxx_yyy] 08
#   REX ∈ {0x48, 0x49, 0x4C, 0x4D}
#   modrm = 0x40 + (dst_reg & 7) * 8 + (src_reg & 7),  with src_reg&7 != 4 (not rsp/r12)
#
# Variant 2: load from SIB source (rsp / r12)
#   [REX] 8B [modrm=01_xxx_100] 24 08    (SIB byte 0x24 = base=rsp, no index, scale=1)
#   REX ∈ {0x48, 0x49 (for r12 source), 0x4C (for r8-15 dst), 0x4D (for r8-15 dst + r12 src)}

import re as _re

# Build regex bytes for Pattern B variant 1 (non-SIB source)
# We'll compile a single Python regex that matches any of these byte sequences.
b_variants = []  # list of bytes objects

rex_options = [0x48, 0x49, 0x4C, 0x4D]
for rex in rex_options:
    for dst_low in range(8):       # rax..rdi as dst (REX.R extends)
        for src_low in range(8):   # rax..rdi as src
            if src_low == 4:       # skip rsp/r12 (SIB)
                continue
            modrm = 0x40 | (dst_low << 3) | src_low
            b_variants.append(bytes([rex, 0x8B, modrm, 0x08]))

# Variant 2: SIB source (rsp/r12)
for rex in rex_options:
    for dst_low in range(8):
        modrm = 0x40 | (dst_low << 3) | 0x04  # r/m=100 → SIB
        b_variants.append(bytes([rex, 0x8B, modrm, 0x24, 0x08]))

# Compile into a single alternation regex
pat_b_regex = _re.compile(b"|".join(_re.escape(b) for b in b_variants))

# Pattern A regexes
pat_a_regexes = []
for seq, name, _ in PATTERN_A_REGEX_BYTES:
    pat_a_regexes.append((_re.compile(_re.escape(seq)), name, seq))

# ---------- Call register (Pattern B "call rXX" suffix) ----------
# `call r64` is: FF /2 with mod=11 (register direct)
# Encoding: FF [modrm = 11_010_rrr]  (reg field = 010 = CALL)
# For rax..rdi: FF D0+rrr (D0=rax, D1=rcx, ..., D7=rdi)
# For r8..r15: 41 FF D0+(rrr)  (REX.B)
call_reg_patterns = {}
for rrr in range(8):
    call_reg_patterns[rrr] = bytes([0xFF, 0xD0 | rrr])           # rax..rdi
    call_reg_patterns[rrr + 8] = bytes([0x41, 0xFF, 0xD0 | rrr])  # r8..r15


def scan_pattern_a(text_data, text_elf_base):
    """Find all `call [reg+0x08]` sites."""
    sites = []
    for rgx, reg_name, seq in pat_a_regexes:
        for m in rgx.finditer(text_data):
            site_va = text_elf_base + m.start()
            sites.append({
                "site_va": site_va,
                "pattern": "A_call_mem_indirect_disp8",
                "reg": reg_name,
                "insn_bytes": seq.hex(),
            })
    return sites


def scan_pattern_b(text_data, text_elf_base):
    """Find all `mov rXX, [reg+0x08]; ... ; call rXX` sites.

    Two-step approach:
    1. Find all `mov rXX, [reg+0x08]` loads (any dst, any src reg).
    2. For each load, scan forward up to 16 bytes (4-8 instructions) for
       `call rXX` matching the loaded dst register. We need a small
       disassembler or heuristic to know the dst reg of each load.

    The dst reg encoding from the matched bytes:
       Match layout: [REX] 8B [modrm] [optional SIB] 08
       For non-SIB variant: 4 bytes, dst_reg = ((modrm >> 3) & 7) + (REX.R ? 8 : 0)
                                          src_reg = (modrm & 7) + (REX.B ? 8 : 0)
       For SIB variant: 5 bytes, same dst_reg formula, src_reg = 4 + (REX.B ? 8 : 0)
                                          (4 → rsp or 12 → r12)
    """
    # Build a quick lookup: for each matched load, compute (dst_reg, src_reg, site_va, end_off)
    loads = []
    for m in pat_b_regex.finditer(text_data):
        bs = m.group(0)
        off = m.start()
        rex = bs[0]
        modrm = bs[2] if len(bs) == 4 else bs[2]
        # If SIB variant (len==5), src is rsp/r12
        if len(bs) == 5:
            src_low = 4
        else:
            src_low = modrm & 0x07
        dst_low = (modrm >> 3) & 0x07
        dst_reg = dst_low + (8 if (rex & 0x04) else 0)  # REX.R bit
        src_reg = src_low + (8 if (rex & 0x01) else 0)  # REX.B bit
        site_va = text_elf_base + off
        loads.append({
            "site_va": site_va,
            "end_off": off + len(bs),
            "dst_reg": dst_reg,
            "src_reg": src_reg,
            "bytes": bs.hex(),
        })

    # For each load, scan forward up to 24 bytes for `call rXX` matching dst_reg
    sites = []
    n = len(text_data)
    call_seq = call_reg_patterns
    for ld in loads:
        target_call = call_seq[ld["dst_reg"]]
        scan_end = min(ld["end_off"] + 24, n)
        # Find first occurrence of target_call in [end_off, scan_end)
        # We must be careful: target_call can appear inside other instructions.
        # Heuristic: accept first byte-match within 24 bytes (≤8 typical instructions).
        window = text_data[ld["end_off"]:scan_end]
        idx = window.find(target_call)
        if idx >= 0:
            call_va = text_elf_base + ld["end_off"] + idx
            sites.append({
                "site_va": ld["site_va"],
                "pattern": "B_mov_load_then_call",
                "load_reg": f"r{ld['dst_reg']}",
                "src_reg": f"r{ld['src_reg']}",
                "call_site_va": call_va,
                "load_bytes": ld["bytes"],
                "call_bytes": target_call.hex(),
            })
    return sites


def main():
    print(f"[*] Loading PRX: {PRX_PATH}")
    elf, raw = load_prx()

    seg = find_exec_segment(elf)
    text_elf_base = seg["p_vaddr"]
    text_off = seg["p_offset"]
    text_size = seg["p_filesz"]
    text_data = seg.data()
    print(f"[+] exec segment: elf_va=0x{text_elf_base:x}  size=0x{text_size:x}  off=0x{text_off:x}")

    real_init_elf_va = 0x804F04BA0 - PRX_RUNTIME_BASE
    if text_elf_base <= real_init_elf_va < text_elf_base + text_size:
        print(f"[+] real_init at elf_va=0x{real_init_elf_va:x} — INSIDE text (base assumption correct)")
        runtime_offset = PRX_RUNTIME_BASE
    else:
        print(f"[!] real_init at elf_va=0x{real_init_elf_va:x} — OUTSIDE exec segment")
        runtime_offset = 0

    print("[+] Building function-start table via INT3 padding heuristic...")
    starts_set = find_function_starts_from_padding(text_data, text_elf_base)
    sorted_starts = sorted(starts_set)
    print(f"[+] function starts: {len(sorted_starts)}")

    # Resolve known reachable addresses to their containing function starts
    known_elf_to_label = {va - PRX_RUNTIME_BASE: name for va, name in KNOWN_REACHABLE.items()}
    known_func_starts = {}  # func_start_elf_va -> set of original labels
    for elf_va, label in known_elf_to_label.items():
        fs = containing_function(elf_va, sorted_starts)
        if fs is None:
            print(f"[!] known addr 0x{elf_va:x} ({label}) — could not resolve containing function")
            continue
        known_func_starts.setdefault(fs, set()).add(label)
        if fs != elf_va:
            print(f"[+] known addr 0x{elf_va:x} ({label}) → containing func 0x{fs:x}")

    print(f"[+] distinct known containing funcs: {len(known_func_starts)}")

    # Scan patterns
    print("[+] Scanning Pattern A (call [reg+0x08])...")
    sites_a = scan_pattern_a(text_data, text_elf_base)
    print(f"    Pattern A sites: {len(sites_a)}")

    print("[+] Scanning Pattern B (mov rXX,[reg+0x08]; ...; call rXX)...")
    sites_b = scan_pattern_b(text_data, text_elf_base)
    print(f"    Pattern B sites: {len(sites_b)}")

    all_sites = sites_a + sites_b

    # Map each site to its containing function and check known cluster
    report = []
    reachable_hits = []
    for s in all_sites:
        func_start_elf = containing_function(s["site_va"], sorted_starts)
        if func_start_elf is None:
            s["containing_func_elf_va"] = None
            s["containing_func_runtime_va"] = None
            s["in_known_cluster"] = False
            s["cluster_labels"] = []
        else:
            s["containing_func_elf_va"] = func_start_elf
            s["containing_func_runtime_va"] = func_start_elf + runtime_offset
            if func_start_elf in known_func_starts:
                s["in_known_cluster"] = True
                s["cluster_labels"] = sorted(known_func_starts[func_start_elf])
                reachable_hits.append(s)
            else:
                s["in_known_cluster"] = False
                s["cluster_labels"] = []
        s["site_runtime_va"] = s["site_va"] + runtime_offset
        report.append(s)

    os.makedirs("/home/z/my-project/scripts/exp111", exist_ok=True)
    with open("/home/z/my-project/scripts/exp111/exp111_sites.json", "w") as f:
        json.dump({
            "prx_path": PRX_PATH,
            "prx_runtime_base": hex(PRX_RUNTIME_BASE),
            "text_elf_base": hex(text_elf_base),
            "text_size": hex(text_size),
            "total_sites": len(all_sites),
            "pattern_a_count": len(sites_a),
            "pattern_b_count": len(sites_b),
            "sites": report,
            "reachable_hits": reachable_hits,
            "known_reachable_runtime_vas": {hex(k): v for k, v in KNOWN_REACHABLE.items()},
            "known_func_starts_resolved": {
                hex(fs + runtime_offset): sorted(labels)
                for fs, labels in known_func_starts.items()
            },
        }, f, indent=2, default=str)

    print()
    print("=" * 78)
    print(f"TOTAL indirect-disp8 sites: {len(all_sites)} (A={len(sites_a)}, B={len(sites_b)})")
    print(f"HITS in known reachable cluster: {len(reachable_hits)}")
    print("=" * 78)
    if reachable_hits:
        print("\nReachable cluster hits:")
        for h in reachable_hits:
            print(f"  site=0x{h['site_runtime_va']:x}  func=0x{h['containing_func_runtime_va']:x}  labels={h['cluster_labels']}  pattern={h['pattern']}  reg={h.get('reg') or h.get('load_reg')}  insn_bytes={h.get('insn_bytes') or h.get('load_bytes')}")
    else:
        print("\n*** NO indirect-disp8 sites fall inside the known reachable cluster. ***")

    # Top containing functions
    func_count = defaultdict(int)
    for s in report:
        if s["containing_func_elf_va"] is not None:
            func_count[s["containing_func_elf_va"]] += 1
    print(f"\nDistinct containing functions: {len(func_count)}")
    print(f"\nTop 15 containing functions (by site count):")
    for fs, cnt in sorted(func_count.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cnt:3d} sites in 0x{fs+runtime_offset:x}")


if __name__ == "__main__":
    main()
