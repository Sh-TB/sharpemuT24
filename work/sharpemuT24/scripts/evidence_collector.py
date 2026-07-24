#!/usr/bin/env python3
"""
SharpEmu Evidence Collector — parses a run log and produces:
1. Boot Timeline (which boot stages were reached)
2. Missing NID Analyzer (unknown NIDs with call counts + params)
3. Crash Fingerprint (RIP, registers, call stack, last imports)
4. GPU Metrics (draws, flips, swapchain, shaders)
5. Image Metrics (framebuffer count, nonblack %, hashes)
6. Comparison summary (before/after)

Usage: python3 evidence_collector.py <log_file> <game_name> <evidence_dir>
"""
import re
import sys
import os
import json
from collections import Counter, defaultdict
from pathlib import Path

def parse_log(log_path, game_name, ev_dir):
    with open(log_path, 'r', errors='replace') as f:
        log = f.read()
    lines = log.split('\n')
    
    report = {
        "game": game_name,
        "log_file": str(log_path),
        "log_lines": len(lines),
    }
    
    # ===== 1. BOOT TIMELINE =====
    timeline = []
    checks = [
        ("ELF Loaded", r"Loading:.*eboot\.bin|Loading:.*\.elf"),
        ("Modules Loaded", r"Module preload summary.*loaded=(\d+)"),
        ("Imports Resolved", r"Setup.*import stubs|Created.*import stubs"),
        ("Data Relocations", r"Imported data rebind.*rebound=(\d+).*unresolved=(\d+)"),
        ("Execute Started", r"=== Execute START ==="),
        ("Runtime Symbols", r"RuntimeSymbols: (\d+)"),
        ("GLFW Platform", r"GLFW windowing platform in use: (\S+)"),
        ("Vulkan Device", r"Vulkan device: (.+)"),
        ("VideoOut Ready", r"Vulkan VideoOut ready: (\S+ \S+)"),
        ("First AGC Submit", r"agc\.driver_submit_dcb"),
        ("First Draw", r"agc\.dcb_draw_index_offset"),
        ("First Flip", r"agc\.dcb_set_flip"),
        ("First Frame Presented", r"presented first frame: (\S+)"),
        ("Guest Frame Presented", r"presented guest frame"),
        ("First Swapchain Image", r"vk\.swapchain_image"),
        ("Execute Ended", r"=== Execute END ==="),
    ]
    for stage, pattern in checks:
        m = re.search(pattern, log)
        if m:
            detail = m.group(1) if m.lastindex else "yes"
            timeline.append({"stage": stage, "reached": True, "detail": detail})
        else:
            timeline.append({"stage": stage, "reached": False, "detail": ""})
    report["boot_timeline"] = timeline
    
    # ===== 2. MISSING NID ANALYZER =====
    # Unresolved imports (no handler at all)
    unresolved_re = re.compile(r'unresolved: nid=([A-Za-z0-9+-]+)')
    unresolved_nids = Counter(unresolved_re.findall(log))
    
    # Imports that returned errors (NOT_FOUND, MEMORY_FAULT, etc.)
    warn_import_re = re.compile(
        r'Import#(\d+) result: (\S+) \(([A-Za-z0-9+-]+)\).*?rdi=(0x[0-9A-Fa-f]+).*?rsi=(0x[0-9A-Fa-f]+).*?rdx=(0x[0-9A-Fa-f]+)'
    )
    error_imports = defaultdict(lambda: {"count": 0, "errors": Counter(), "params": []})
    for m in warn_import_re.finditer(log):
        imp_num, error, nid, rdi, rsi, rdx = m.groups()
        error_imports[nid]["count"] += 1
        error_imports[nid]["errors"][error] += 1
        if len(error_imports[nid]["params"]) < 3:
            error_imports[nid]["params"].append({"rdi": rdi, "rsi": rsi, "rdx": rdx})
    
    # IL2CPP lookup failures
    il2cpp_re = re.compile(r"il2cpp_api_lookup_symbol failed: name='([^']+)'")
    il2cpp_fails = Counter(il2cpp_re.findall(log))
    
    nid_report = {
        "completely_unresolved": [
            {"nid": nid, "call_count": cnt} for nid, cnt in unresolved_nids.most_common()
        ],
        "error_returning_imports": [
            {
                "nid": nid,
                "call_count": data["count"],
                "errors": dict(data["errors"]),
                "sample_params": data["params"],
            }
            for nid, data in sorted(error_imports.items(), key=lambda x: -x[1]["count"])
        ],
        "il2cpp_lookup_failures": [
            {"function": fn, "count": cnt} for fn, cnt in il2cpp_fails.most_common(20)
        ],
    }
    report["nid_analysis"] = nid_report
    
    # ===== 3. CRASH FINGERPRINT =====
    crash = {}
    sig_re = re.compile(r'posix-signal#(\d+): sig=(\d+) rip=(0x[0-9A-Fa-f]+) fault=(0x[0-9A-Fa-f]+) access=(\d+)')
    m = sig_re.search(log)
    if m:
        crash["signal_num"] = int(m.group(2))
        crash["rip"] = m.group(3)
        crash["fault_address"] = m.group(4)
        crash["access_type"] = m.group(5)
    
    # Registers
    reg_re = re.compile(r'(R\w+):\s+(0x[0-9A-Fa-f]+)')
    reg_section = log[log.find("RIP:"):] if "RIP:" in log else ""
    regs = {}
    for m in reg_re.finditer(reg_section):
        regs[m.group(1)] = m.group(2)
    crash["registers"] = regs
    
    # AV details
    av_re = re.compile(r'AV (?:target|access): ([^\n]+)')
    crash["av_details"] = av_re.findall(log[:log.find("Stack qwords")] if "Stack qwords" in log else log)
    
    # Last imports before crash
    last_imports = []
    for line in lines:
        m = re.search(r'Import#(\d+).*?nid=([A-Za-z0-9+-]+)', line)
        if m:
            last_imports.append({"num": int(m.group(1)), "nid": m.group(2)})
        # Also capture the Native diagnostics format
        m = re.search(r'#(\d+).*?nid=([A-Za-z0-9+-]+)', line)
        if m:
            last_imports.append({"num": int(m.group(1)), "nid": m.group(2)})
    crash["last_5_imports"] = last_imports[-5:] if last_imports else []
    
    # Code at RIP
    code_re = re.compile(r'Code at RIP: ([0-9A-Fa-f ]+)')
    m = code_re.search(log)
    if m:
        crash["code_at_rip"] = m.group(1).strip()
    
    report["crash_fingerprint"] = crash
    
    # ===== 4. GPU METRICS =====
    gpu = {
        "agc_driver_submit_dcb": len(re.findall(r'agc\.driver_submit_dcb', log)),
        "agc_dcb_draw_index_offset": len(re.findall(r'agc\.dcb_draw_index_offset', log)),
        "agc_dcb_set_flip": len(re.findall(r'agc\.dcb_set_flip', log)),
        "agc_rt_writer": len(re.findall(r'agc\.rt_writer', log)),
        "vk_flip_capture": len(re.findall(r'vk\.flip_capture', log)),
        "vk_swapchain_image": len(re.findall(r'vk\.swapchain_image', log)),
        "shader_draw_seen": len(re.findall(r'agc\.shader_draw_seen', log)),
        "texture_source": len(re.findall(r'agc\.texture_source', log)),
    }
    report["gpu_metrics"] = gpu
    
    # ===== 5. IMAGE METRICS =====
    fb_dir = Path(ev_dir) / "fb"
    fb_files = list(fb_dir.glob("*.bgra")) if fb_dir.exists() else []
    
    swapchain_re = re.compile(r'vk\.swapchain_image.*nonblack_pixels=(\d+)/(\d+).*hash=(0x[0-9A-Fa-f]+)')
    swaps = swapchain_re.findall(log)
    hashes = set(h for _, _, h in swaps)
    nonblack_pcts = [int(nb)*100/int(t) for nb, t, h in swaps] if swaps else []
    
    report["image_metrics"] = {
        "framebuffer_files": len(fb_files),
        "swapchain_events": len(swaps),
        "unique_hashes": len(hashes),
        "nonblack_pct_first": nonblack_pcts[0] if nonblack_pcts else 0,
        "nonblack_pct_last": nonblack_pcts[-1] if nonblack_pcts else 0,
        "nonblack_pct_max": max(nonblack_pcts) if nonblack_pcts else 0,
    }
    
    # ===== 6. SUMMARY =====
    reached = [t["stage"] for t in timeline if t["reached"]]
    report["summary"] = {
        "boot_stages_reached": len(reached),
        "boot_stages_total": len(timeline),
        "last_stage": reached[-1] if reached else "none",
        "has_crash": bool(crash),
        "has_framebuffer": len(fb_files) > 0,
        "exit_status": "crash" if crash else ("hang" if "Execute END" not in log else "exit"),
    }
    
    return report

def print_report(report):
    game = report["game"]
    print(f"\n{'='*60}")
    print(f"  {game}")
    print(f"{'='*60}")
    
    print(f"\n--- Boot Timeline ---")
    for t in report["boot_timeline"]:
        mark = "✔" if t["reached"] else "✖"
        detail = f" ({t['detail']})" if t["detail"] else ""
        print(f"  {mark} {t['stage']}{detail}")
    
    s = report["summary"]
    print(f"\n--- Summary ---")
    print(f"  Stages reached: {s['boot_stages_reached']}/{s['boot_stages_total']}")
    print(f"  Last stage: {s['last_stage']}")
    print(f"  Exit status: {s['exit_status']}")
    print(f"  Has framebuffer: {s['has_framebuffer']}")
    
    g = report["gpu_metrics"]
    print(f"\n--- GPU Metrics ---")
    for k, v in g.items():
        print(f"  {k}: {v}")
    
    im = report["image_metrics"]
    print(f"\n--- Image Metrics ---")
    for k, v in im.items():
        print(f"  {k}: {v}")
    
    if report["crash_fingerprint"]:
        c = report["crash_fingerprint"]
        print(f"\n--- Crash Fingerprint ---")
        print(f"  Signal: {c.get('signal_num', '?')}")
        print(f"  RIP: {c.get('rip', '?')}")
        print(f"  Fault address: {c.get('fault_address', '?')}")
        print(f"  Access type: {c.get('access_type', '?')}")
        if c.get("code_at_rip"):
            print(f"  Code at RIP: {c['code_at_rip'][:60]}...")
        if c.get("last_5_imports"):
            print(f"  Last imports:")
            for imp in c["last_5_imports"]:
                print(f"    #{imp['num']}: {imp['nid']}")
    
    na = report["nid_analysis"]
    if na["completely_unresolved"] or na["error_returning_imports"] or na["il2cpp_lookup_failures"]:
        print(f"\n--- Missing NID Analysis ---")
        if na["completely_unresolved"]:
            print(f"  Completely unresolved ({len(na['completely_unresolved'])}):")
            for n in na["completely_unresolved"][:5]:
                print(f"    {n['nid']}: {n['call_count']} calls")
        if na["error_returning_imports"]:
            print(f"  Error-returning imports ({len(na['error_returning_imports'])}):")
            for n in na["error_returning_imports"][:5]:
                print(f"    {n['nid']}: {n['call_count']} calls, errors={n['errors']}")
        if na["il2cpp_lookup_failures"]:
            print(f"  IL2CPP lookup failures ({len(na['il2cpp_lookup_failures'])}):")
            for n in na["il2cpp_lookup_failures"][:5]:
                print(f"    {n['function']}: {n['count']}")

if __name__ == '__main__':
    games = [
        ("Dreaming Sarah", "dreaming_sarah"),
        ("Arise", "arise"),
        ("Harvest Days", "harvest_days"),
    ]
    ev_base = Path("/home/z/my-project/download/evidence")
    all_reports = []
    for name, dirname in games:
        log_path = ev_base / dirname / "full_log.txt"
        if log_path.exists():
            report = parse_log(str(log_path), name, str(ev_base / dirname))
            all_reports.append(report)
            print_report(report)
            # Save JSON
            with open(ev_base / dirname / "metrics.json", 'w') as f:
                json.dump(report, f, indent=2, default=str)
        else:
            print(f"\n{'='*60}\n  {name} — NO LOG FOUND\n{'='*60}")
    
    # Save combined
    with open(ev_base / "analysis" / "all_games_metrics.json", 'w') as f:
        json.dump(all_reports, f, indent=2, default=str)
    print(f"\n\nAll metrics saved to {ev_base}/analysis/all_games_metrics.json")
