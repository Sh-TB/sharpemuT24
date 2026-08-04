#!/usr/bin/env python3
"""
EXP-111 (filtered) — enumerate all `call [reg+0x08]` sites in
Il2cppUserAssemblies.prx, map each site to its containing function,
check whether any of those containing functions belong to the known
reachable cluster.

Uses program headers (segments) instead of section headers since
PS5 PRX files typically have stripped/bogus section headers.
"""
import json
import os
from collections import defaultdict
from bisect import bisect_right
from io import BytesIO

from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG

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


def load_prx():
    with open(PRX_PATH, "rb") as f:
        data = f.read()
    return ELFFile(BytesIO(data)), data


def iter_segments_safe(elf):
    """Iterate program headers without triggering DynamicSegment parsing
    on possibly-malformed PT_DYNAMIC entries."""
    from elftools.elf.constants import SH_FLAGS
    for i in range(elf["e_phnum"]):
        hdr = elf._get_segment_header(i)
        from elftools.elf.segments import Segment
        seg = Segment(hdr, elf.stream)
        yield seg


def find_exec_segment(elf):
    """Return first executable PT_LOAD segment."""
    for seg in iter_segments_safe(elf):
        if seg["p_type"] == "PT_LOAD" and (seg["p_flags"] & 1):
            return seg
    raise RuntimeError("no executable PT_LOAD segment found")


def find_symbols(elf):
    """Try symbol tables, but PRX has bogus section headers — return empty on failure."""
    syms = {}
    try:
        for sec_name in (".symtab", ".dynsym"):
            try:
                sec = elf.get_section_by_name(sec_name)
            except Exception:
                continue
            if sec is None:
                continue
            for sym in sec.iter_symbols():
                if sym["st_info"]["type"] == "STT_FUNC" and sym["st_value"] != 0:
                    if sym.name:
                        syms.setdefault(sym["st_value"], sym.name)
    except Exception as e:
        print(f"[!] symbol table unreadable: {e}")
        print("    (Expected for stripped PS5 PRX; will rely on heuristic function starts only.)")
    return syms


def find_function_starts_from_padding(text_data, text_elf_base):
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
            if (sig == b"\xF3\x0F\x1E\xFA" or
                sig[0] == 0x55 or
                (sig[0] == 0x41 and sig[1] in (0x54,0x55,0x56,0x57)) or
                (sig[0] == 0x48 and sig[1] == 0x83 and sig[2] == 0xEC) or
                (sig[0] == 0x48 and sig[1] == 0x81 and sig[2] == 0xEC)):
                starts.add(text_elf_base + off)
    return starts


def build_function_table(elf, text_data, text_elf_base, text_size, syms):
    text_end = text_elf_base + text_size
    sym_in_text = {va for va in syms.keys() if text_elf_base <= va < text_end}
    heur_starts = find_function_starts_from_padding(text_data, text_elf_base)
    all_starts = sorted(sym_in_text | heur_starts)
    print(f"[+] function starts: {len(sym_in_text)} from symbols, {len(heur_starts)} from heuristic, {len(all_starts)} total")
    return all_starts


def containing_function(va, sorted_starts):
    if not sorted_starts:
        return None
    idx = bisect_right(sorted_starts, va)
    if idx == 0:
        return None
    return sorted_starts[idx - 1]


def scan_indirect_calls(text_data, text_elf_base, sorted_starts):
    """
    Disassemble function-by-function (rather than a single linear sweep over
    the entire 45MB text — that would be slow and produce garbage over data
    padding/jump tables). For each detected function start, disassemble up
    to the next start, scanning for the two patterns.
    """
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    sites = []
    pat_a = 0
    pat_b = 0
    total_funcs = len(sorted_starts)
    funcs_done = 0

    text_end = text_elf_base + len(text_data)

    for k, start in enumerate(sorted_starts):
        if start < text_elf_base or start >= text_end:
            continue
        next_start = sorted_starts[k+1] if k+1 < total_funcs else text_end
        if next_start > text_end:
            next_start = text_end
        off = start - text_elf_base
        size = next_start - start
        if size <= 0 or size > 0x100000:  # cap absurdly large "functions" (likely heuristic noise)
            continue
        chunk = text_data[off:off+size]
        try:
            insns = list(md.disasm(chunk, start))
        except Exception:
            continue

        for i, ins in enumerate(insns):
            if ins.mnemonic == "call":
                ops = ins.operands
                if len(ops) == 1 and ops[0].type == CS_OP_MEM:
                    mem = ops[0].mem
                    if mem.disp == 0x08 and mem.base != 0 and mem.index == 0:
                        sites.append({
                            "site_va": ins.address,
                            "pattern": "A_call_mem_indirect_disp8",
                            "reg": ins.reg_name(mem.base),
                            "insn": f"{ins.mnemonic} {ins.op_str}",
                            "containing_func_elf_va": start,
                        })
                        pat_a += 1

            if ins.mnemonic == "mov" and len(ins.operands) == 2:
                dst, src = ins.operands
                if (dst.type == CS_OP_REG and
                    src.type == CS_OP_MEM and
                    src.mem.disp == 0x08 and
                    src.mem.base != 0 and
                    src.mem.index == 0):
                    dst_reg = dst.reg
                    for j in range(i+1, min(i+9, len(insns))):
                        nxt = insns[j]
                        if nxt.mnemonic == "call" and len(nxt.operands) == 1 and nxt.operands[0].type == CS_OP_REG and nxt.operands[0].reg == dst_reg:
                            sites.append({
                                "site_va": ins.address,
                                "pattern": "B_mov_load_then_call",
                                "load_reg": ins.reg_name(dst_reg),
                                "base_reg": ins.reg_name(src.mem.base),
                                "call_site_va": nxt.address,
                                "insn": f"mov {ins.op_str}  // -> call {nxt.op_str}",
                                "containing_func_elf_va": start,
                            })
                            pat_b += 1
                            break
                        if nxt.mnemonic in ("mov", "xor", "or", "and", "lea") and len(nxt.operands) >= 1 and nxt.operands[0].type == CS_OP_REG and nxt.operands[0].reg == dst_reg:
                            break

        funcs_done += 1
        if funcs_done % 2000 == 0:
            print(f"    ... {funcs_done}/{total_funcs} funcs scanned, sites so far: A={pat_a} B={pat_b}")

    print(f"[+] Pattern A (call [reg+0x08]): {pat_a}")
    print(f"[+] Pattern B (mov r,[reg+0x08]; ... call r): {pat_b}")
    return sites


def main():
    print(f"[*] Loading PRX: {PRX_PATH}")
    elf, raw = load_prx()

    print(f"[+] ELF header:")
    print(f"    e_type     = {elf['e_type']}")
    print(f"    e_machine  = {elf['e_machine']}")
    print(f"    e_entry    = {hex(elf['e_entry'])}")
    print(f"    segments   = {elf['e_phnum']}")

    print(f"[+] Program headers (PT_LOAD only):")
    for seg in iter_segments_safe(elf):
        if seg["p_type"] == "PT_LOAD":
            flags = seg["p_flags"]
            r = "R" if flags & 4 else "-"
            w = "W" if flags & 2 else "-"
            x = "X" if flags & 1 else "-"
            print(f"    p_vaddr=0x{seg['p_vaddr']:x}  p_offset=0x{seg['p_offset']:x}  p_filesz=0x{seg['p_filesz']:x}  p_memsz=0x{seg['p_memsz']:x}  [{r}{w}{x}]")

    seg = find_exec_segment(elf)
    text_elf_base = seg["p_vaddr"]
    text_off = seg["p_offset"]
    text_size = seg["p_filesz"]
    text_data = seg.data()
    print(f"\n[+] exec segment: elf_va=0x{text_elf_base:x}  size=0x{text_size:x}  file_off=0x{text_off:x}")

    real_init_elf_va = 0x804F04BA0 - PRX_RUNTIME_BASE
    if text_elf_base <= real_init_elf_va < text_elf_base + text_size:
        print(f"[+] real_init at elf_va=0x{real_init_elf_va:x} — INSIDE text (base assumption correct)")
        runtime_offset = PRX_RUNTIME_BASE
    else:
        print(f"[!] real_init at elf_va=0x{real_init_elf_va:x} — OUTSIDE exec segment")
        print(f"    exec range: 0x{text_elf_base:x}..0x{text_elf_base+text_size:x}")
        runtime_offset = 0

    syms = find_symbols(elf)
    print(f"[+] symbols: {len(syms)}")

    sorted_starts = build_function_table(elf, text_data, text_elf_base, text_size, syms)

    known_elf = {va - PRX_RUNTIME_BASE: name for va, name in KNOWN_REACHABLE.items()}

    sites = scan_indirect_calls(text_data, text_elf_base, sorted_starts)

    report = []
    reachable_hits = []

    for s in sites:
        site_elf_va = s["site_va"]
        # The scanner already attached containing_func_elf_va from sorted_starts.
        # But re-derive via containing_function() for sites where scanner hit a
        # function larger than 0x100000 cap (those were skipped). For sites that
        # DID fire, this should match what scanner already set.
        func_start_elf = s.get("containing_func_elf_va") or containing_function(site_elf_va, sorted_starts)
        if func_start_elf is None:
            s["containing_func_elf_va"] = None
            s["containing_func_runtime_va"] = None
            s["func_symbol"] = None
            s["in_known_cluster"] = False
            s["cluster_label"] = None
        else:
            s["containing_func_elf_va"] = func_start_elf
            s["containing_func_runtime_va"] = func_start_elf + runtime_offset
            s["func_symbol"] = syms.get(func_start_elf, "")
            if func_start_elf in known_elf:
                s["in_known_cluster"] = True
                s["cluster_label"] = known_elf[func_start_elf]
                reachable_hits.append(s)
            else:
                s["in_known_cluster"] = False
                s["cluster_label"] = None
        s["site_runtime_va"] = site_elf_va + runtime_offset
        report.append(s)

    os.makedirs("/home/z/my-project/scripts/exp111", exist_ok=True)
    with open("/home/z/my-project/scripts/exp111/exp111_sites.json", "w") as f:
        json.dump({
            "prx_path": PRX_PATH,
            "prx_runtime_base": hex(PRX_RUNTIME_BASE),
            "text_elf_base": hex(text_elf_base),
            "text_size": hex(text_size),
            "total_sites": len(sites),
            "sites": report,
            "reachable_hits": reachable_hits,
            "known_reachable_runtime_vas": {hex(k): v for k, v in KNOWN_REACHABLE.items()},
        }, f, indent=2, default=str)

    print()
    print("=" * 72)
    print(f"TOTAL indirect-disp8 sites: {len(sites)}")
    print(f"HITS in known reachable cluster: {len(reachable_hits)}")
    print("=" * 72)
    if reachable_hits:
        print("\nReachable cluster hits:")
        for h in reachable_hits:
            print(f"  site=0x{h['site_runtime_va']:x}  func=0x{h['containing_func_runtime_va']:x} ({h['func_symbol'] or 'no symbol'})  pattern={h['pattern']}  insn='{h['insn']}'")
    else:
        print("\n*** NO indirect-disp8 sites fall inside the known reachable cluster. ***")

    func_count = defaultdict(int)
    for s in report:
        if s["containing_func_elf_va"] is not None:
            key = (s["containing_func_elf_va"], s["func_symbol"])
            func_count[key] += 1
    print(f"\nTop 15 containing functions (by site count):")
    for (fa, sym), cnt in sorted(func_count.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cnt:3d} sites in 0x{fa+runtime_offset:x}  ({sym or 'no symbol'})")

    print(f"\nDistinct containing functions: {len(func_count)}")


if __name__ == "__main__":
    main()
