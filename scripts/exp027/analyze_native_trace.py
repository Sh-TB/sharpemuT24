#!/usr/bin/env python3
"""
EXP-027: Analyze native SharpEmu trace logs and compare with synthetic CPU.

This script parses the log files produced by the EXP-027 C# instrumentation
patches and compares each instruction's register/flag state with the synthetic
CPU's expected state. It identifies the FIRST divergence point.

INPUT FILES (produced by _Exp027ResolverTracer.cs):
    /tmp/exp027_logs/test4_full_trace.log
    /tmp/exp027_logs/test1_rflags.log
    /tmp/exp027_logs/test2_registers.log
    /tmp/exp027_logs/test3_strcmp.log
    /tmp/exp027_logs/test3_sf_preservation.log

OUTPUT:
    EXP027_FIRST_DIVERGENCE_REPORT.md
"""

import re
import json
import sys
from pathlib import Path

LOG_DIR = Path('/tmp/exp027_logs')

# Resolver instruction addresses and their semantic meaning
INSTRUCTION_INFO = {
    0x804ED9B90: ('push',    'rbp',                     'prologue'),
    0x804ED9B91: ('mov',     'rbp, rsp',                'frame pointer'),
    0x804ED9B94: ('push',    'r15; r14; r12; rbx',      'save callee-saved'),
    0x804ED9B9B: ('mov',     'r15, [rip+0x3c79b66]',    'r15 = list_head_struct (= sentinel)'),
    0x804ED9BA2: ('mov',     'rbx, [r15+8]',            'rbx = root node'),
    0x804ED9BA6: ('cmp',     'byte [rbx+0x19], 0',      'check matched flag (sentinel?)'),
    0x804ED9BAA: ('je',      'do_lookup',               'if not matched, do lookup'),
    0x804ED9BAC: ('xor',     'eax, eax',                'return 0'),
    0x804ED9BAE: ('pop',     'rbx; r12; r14; r15; rbp', 'epilogue'),
    0x804ED9BB6: ('ret',     '',                        'return'),
    0x804ED9BB7: ('mov',     'r14, rdi',                'r14 = query string'),
    0x804ED9BBA: ('mov',     'r12, r15',                'r12 = candidate = sentinel'),
    0x804ED9BBD: ('nop',     '',                        'alignment'),
    0x804ED9BC0: ('mov',     'rdi, [rbx+0x20]',         'rdi = NODE symbol name (loop_start)'),
    0x804ED9BC4: ('mov',     'rsi, r14',                'rsi = QUERY'),
    0x804ED9BC7: ('call',    'strcmp',                  'strcmp(NODE, QUERY)'),
    0x804ED9BCC: ('test',    'eax, eax',                'set SF/ZF based on strcmp'),
    0x804ED9BCE: ('lea',     'rcx, [rbx+0x10]',         'rcx = LEFT child addr (default)'),
    0x804ED9BD2: ('cmovns',  'rcx, rbx',                'if SF=0: rcx = rbx (RIGHT)'),
    0x804ED9BD6: ('cmovns',  'r12, rbx',                'if SF=0: r12 = rbx (candidate)'),
    0x804ED9BDA: ('mov',     'rbx, [rcx]',              'rbx = next node'),
    0x804ED9BDD: ('cmp',     'byte [rbx+0x19], 0',      'sentinel check'),
    0x804ED9BE1: ('je',      'loop_start',              'loop if not sentinel'),
    0x804ED9BE3: ('cmp',     'r12, r15',                'candidate == sentinel?'),
    0x804ED9BE6: ('je',      'return_0',                'if no candidate, return 0'),
    0x804ED9BE8: ('mov',     'rsi, [r12+0x20]',         'rsi = CANDIDATE name'),
    0x804ED9BED: ('mov',     'rdi, r14',                'rdi = QUERY'),
    0x804ED9BF0: ('call',    'strcmp',                  'strcmp(QUERY, CANDIDATE)'),
    0x804ED9BF5: ('test',    'eax, eax',                'set SF/ZF'),
    0x804ED9BF7: ('js',      'return_0',                'if SF=1 (QUERY<CANDIDATE), return 0'),
    0x804ED9BF9: ('mov',     'rax, [r12+0x28]',         'rax = func_impl (SUCCESS)'),
}


def parse_native_trace(log_path):
    """Parse test4_full_trace.log into a list of step records."""
    if not log_path.exists():
        return None

    steps = []
    pattern = re.compile(
        r"\[EXP027-T1\] call=(\d+) step=(\d+) rip=0x([0-9a-f]+) "
        r"RAX=0x([0-9a-f]+) RBX=0x([0-9a-f]+) RCX=0x([0-9a-f]+) RDX=0x([0-9a-f]+) "
        r"RSI=0x([0-9a-f]+) RDI=0x([0-9a-f]+) R12=0x([0-9a-f]+) R13=0x([0-9a-f]+) "
        r"R14=0x([0-9a-f]+) R15=0x([0-9a-f]+) RBP=0x([0-9a-f]+) RSP=0x([0-9a-f]+) "
        r"RFLAGS=0x([0-9a-f]+) \(([^)]+)\)"
    )

    with open(log_path) as f:
        for line in f:
            m = pattern.search(line)
            if m:
                call_num = int(m.group(1))
                step = int(m.group(2))
                rip = int(m.group(3), 16)
                rax = int(m.group(4), 16)
                rbx = int(m.group(5), 16)
                rcx = int(m.group(6), 16)
                rdx = int(m.group(7), 16)
                rsi = int(m.group(8), 16)
                rdi = int(m.group(9), 16)
                r12 = int(m.group(10), 16)
                r13 = int(m.group(11), 16)
                r14 = int(m.group(12), 16)
                r15 = int(m.group(13), 16)
                rbp = int(m.group(14), 16)
                rsp = int(m.group(15), 16)
                rflags = int(m.group(16), 16)
                flags_str = m.group(17)

                # Parse flag values
                flag_match = re.search(r'CF=(\d+) PF=(\d+) AF=(\d+) ZF=(\d+) SF=(\d+) OF=(\d+)', flags_str)
                if flag_match:
                    cf, pf, af, zf, sf, of = [int(x) for x in flag_match.groups()]
                else:
                    cf = pf = af = zf = sf = of = 0

                steps.append({
                    'call': call_num, 'step': step, 'rip': rip,
                    'rax': rax, 'rbx': rbx, 'rcx': rcx, 'rdx': rdx,
                    'rsi': rsi, 'rdi': rdi, 'r12': r12, 'r13': r13,
                    'r14': r14, 'r15': r15, 'rbp': rbp, 'rsp': rsp,
                    'rflags': rflags,
                    'flags': {'CF': cf, 'PF': pf, 'AF': af, 'ZF': zf, 'SF': sf, 'OF': of},
                })

    return steps


def load_synthetic_trace():
    """Load the synthetic CPU trace for il2cpp_init."""
    synth_path = Path('/home/z/my-project/scripts/exp026_synthetic_trace.json')
    if not synth_path.exists():
        return None
    return json.loads(synth_path.read_text())


def find_first_divergence(native_steps, synth_trace):
    """Compare native and synthetic step-by-step. Return first divergence."""
    if not native_steps or not synth_trace:
        return None

    # Get the synthetic trace for the first query (il2cpp_init)
    synth_steps = synth_trace.get('queries', [])
    if not synth_steps:
        # Try alternative format
        synth_steps = synth_trace.get('first_query_full_trace', [])
    if not synth_steps:
        return None

    # The synthetic trace has 'rip' as hex strings; convert
    # Match step-by-step
    max_steps = min(len(native_steps), len(synth_steps))

    for i in range(max_steps):
        native = native_steps[i]
        synth = synth_steps[i]

        native_rip = native['rip']
        synth_rip = int(synth['rip'], 16)

        if native_rip != synth_rip:
            return {
                'step': i,
                'native': native,
                'synth': synth,
                'reason': f'RIP divergence: native=0x{native_rip:x} synth=0x{synth_rip:x}',
            }

        # Compare key registers
        diffs = []
        for reg in ['rax', 'rbx', 'rcx', 'rdi', 'rsi', 'r12', 'r14', 'r15']:
            n_val = native[reg]
            s_val = int(synth[reg.upper()], 16) if reg.upper() in synth else int(synth.get(reg, '0'), 16)
            if n_val != s_val:
                diffs.append(f"{reg.upper()}: native=0x{n_val:x} synth=0x{s_val:x}")

        if diffs:
            return {
                'step': i,
                'native': native,
                'synth': synth,
                'reason': f"Register divergence at RIP 0x{native_rip:x}: " + "; ".join(diffs),
            }

    return None


def main():
    print("=" * 100)
    print("EXP-027: Native Trace Analysis")
    print("=" * 100)
    print()

    # Check if logs exist
    if not LOG_DIR.exists():
        print(f"[!] Log directory not found: {LOG_DIR}")
        print(f"[!] Run SharpEmu with EXP-027 instrumentation patches first.")
        print(f"[!] See /home/z/my-project/download/exp027/_Exp027_Patch_Instructions.md")
        sys.exit(1)

    # Parse native trace
    native_steps = parse_native_trace(LOG_DIR / 'test4_full_trace.log')
    if not native_steps:
        print(f"[!] No native trace found in {LOG_DIR}/test4_full_trace.log")
        print(f"[!] Make sure the EXP-027 patches are installed and the game was run.")
        sys.exit(1)

    print(f"[*] Parsed {len(native_steps)} native trace steps")

    # Load synthetic trace
    synth_trace = load_synthetic_trace()
    if synth_trace:
        print(f"[*] Loaded synthetic trace")
    else:
        print(f"[!] Synthetic trace not found — run exp026_synthetic_cpu.py first")

    # Find first divergence
    div = find_first_divergence(native_steps, synth_trace) if synth_trace else None

    # Generate report
    report_path = Path('/home/z/my-project/download/exp027/EXP027_FIRST_DIVERGENCE_REPORT.md')
    with open(report_path, 'w') as f:
        f.write("# EXP-027 — First Divergence Report\n\n")
        f.write(f"**Native trace steps:** {len(native_steps)}\n")
        f.write(f"**Synthetic trace steps:** {len(synth_trace.get('first_query_full_trace', [])) if synth_trace else 'N/A'}\n\n")

        if not synth_trace:
            f.write("## Status: AWAITING SYNTHETIC TRACE\n\n")
            f.write("Run `python3 /home/z/my-project/scripts/exp026_synthetic_cpu.py il2cpp_init` first.\n\n")
        elif div is None:
            f.write("## Status: NO DIVERGENCE FOUND\n\n")
            f.write("Native and synthetic traces agree on all comparable steps.\n")
            f.write("If the resolver still returns 0, the divergence is in a step\n")
            f.write("not captured by the breakpoint instrumentation.\n\n")
        else:
            f.write("## Status: DIVERGENCE FOUND\n\n")
            f.write(f"**First divergence at step {div['step']}**\n\n")
            f.write(f"**Reason:** {div['reason']}\n\n")
            f.write("### Native State\n")
            n = div['native']
            f.write(f"- RIP: 0x{n['rip']:x}\n")
            f.write(f"- RAX: 0x{n['rax']:x}\n")
            f.write(f"- RBX: 0x{n['rbx']:x}\n")
            f.write(f"- RCX: 0x{n['rcx']:x}\n")
            f.write(f"- R12: 0x{n['r12']:x}\n")
            f.write(f"- R14: 0x{n['r14']:x}\n")
            f.write(f"- R15: 0x{n['r15']:x}\n")
            f.write(f"- RFLAGS: 0x{n['rflags']:x} (SF={n['flags']['SF']} ZF={n['flags']['ZF']})\n\n")
            f.write("### Synthetic State\n")
            s = div['synth']
            f.write(f"- RIP: {s['rip']}\n")
            f.write(f"- RAX: {s['RAX']}\n")
            f.write(f"- RBX: {s['RBX']}\n")
            f.write(f"- RCX: {s['RCX']}\n")
            f.write(f"- R12: {s['R12']}\n")
            f.write(f"- R14: {s['R14']}\n")
            f.write(f"- R15: {s['R15']}\n")
            f.write(f"- RFLAGS: {s['RFLAGS']}\n\n")
            f.write("### Instruction\n")
            if n['rip'] in INSTRUCTION_INFO:
                mnem, ops, desc = INSTRUCTION_INFO[n['rip']]
                f.write(f"- Address: 0x{n['rip']:x}\n")
                f.write(f"- Mnemonic: {mnem} {ops}\n")
                f.write(f"- Description: {desc}\n\n")
            f.write("### Root Cause Hypothesis\n\n")
            f.write("Based on the diverging register/flag, the bug is likely in:\n")
            if 'RFLAGS' in div['reason'] or 'SF' in div['reason'] or 'ZF' in div['reason']:
                f.write("- **Flag computation or preservation** — the diverging instruction's\n")
                f.write("  flag output differs from what the synthetic CPU expects.\n")
            elif 'RAX' in div['reason']:
                f.write("- **strcmp return value** — the strcmp call returned a different value\n")
                f.write("  in native execution vs synthetic.\n")
            elif 'RBX' in div['reason'] or 'RCX' in div['reason'] or 'R12' in div['reason']:
                f.write("- **cmovns execution or memory read** — the register was updated\n")
                f.write("  differently, possibly due to wrong flag state or wrong memory read.\n")
            else:
                f.write("- **General CPU emulation bug** — see register diff above.\n")

        # Full trace dump (first 50 steps)
        f.write("\n## Full Native Trace (first 50 steps)\n\n")
        f.write("```\n")
        f.write(f"{'step':4s}  {'rip':18s}  {'RAX':18s}  {'RBX':18s}  {'RCX':18s}  {'R12':18s}  SF ZF\n")
        f.write("-" * 110 + "\n")
        for n in native_steps[:50]:
            sf = n['flags']['SF']
            zf = n['flags']['ZF']
            mnem_info = INSTRUCTION_INFO.get(n['rip'], ('?', '?', '?'))
            f.write(f"{n['step']:4d}  0x{n['rip']:x}  0x{n['rax']:016x}  0x{n['rbx']:016x}  0x{n['rcx']:016x}  0x{n['r12']:016x}  {sf}  {zf}  ; {mnem_info[0]} {mnem_info[1]}\n")
        f.write("```\n")

    print(f"[+] Wrote report: {report_path}")

    if div:
        print()
        print("=" * 100)
        print(f"FIRST DIVERGENCE AT STEP {div['step']}")
        print("=" * 100)
        print(div['reason'])
        print()
        n = div['native']
        print(f"Native:  RIP=0x{n['rip']:x} RAX=0x{n['rax']:x} RBX=0x{n['rbx']:x} RCX=0x{n['rcx']:x} R12=0x{n['r12']:x}")
        print(f"         RFLAGS=0x{n['rflags']:x} (SF={n['flags']['SF']} ZF={n['flags']['ZF']})")


if __name__ == '__main__':
    main()
