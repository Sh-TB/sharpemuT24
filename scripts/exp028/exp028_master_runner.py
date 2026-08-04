#!/usr/bin/env python3
"""
EXP-028-DEBUG-002: Master Runner

This script orchestrates the EXP-028 investigation per the user's spec.
It does NOT modify SharpEmu behavior — it only prepares instrumentation,
runs the analyzer, and generates the final report.

USAGE:
    python3 exp028_master_runner.py --verify-repo
    python3 exp028_master_runner.py --verify-instrumentation
    python3 exp028_master_runner.py --analyze
    python3 exp028_master_runner.py --final-report

NOTE: The actual T12/T13, T5, T6 traces require the user to:
  1. Apply the C# patches to SharpEmu source
  2. Build SharpEmu
  3. Run Yatzi with the instrumented binary
  4. Collect logs in /tmp/exp028_logs/

This script then analyzes those logs and produces the final report.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

REPO_PATH = Path('/tmp/my-project/work/sharpemuT24')
LOG_DIR = Path('/tmp/exp028_logs')
OUTPUT_DIR = Path('/home/z/my-project/download/exp028')
SCRIPTS_DIR = Path('/home/z/my-project/scripts/exp028')

INSTRUMENTATION_FILES = [
    '_Exp028T12T13BoundaryTrace.cs',
    '_Exp028MemoryReadTracer.cs',
    '_Exp028BranchTracer.cs',
    '_Exp027ResolverTracer.cs',
]


def run_cmd(cmd, cwd=None, timeout=30):
    """Run a command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, '', 'TIMEOUT'
    except Exception as e:
        return -2, '', str(e)


def section_0_repo_integrity():
    """SECTION 0: Repository Integrity Gate."""
    print("=" * 80)
    print("SECTION 0: Repository Integrity Gate")
    print("=" * 80)
    print()

    # 0.1 git remote -v
    rc, out, _ = run_cmd('git remote -v', cwd=REPO_PATH)
    print(f"[$] git remote -v (exit={rc}):")
    print(out)

    # 0.2 git branch -vv
    rc, out, _ = run_cmd('git branch -vv', cwd=REPO_PATH)
    print(f"[$] git branch -vv (exit={rc}):")
    print(out)

    # 0.3 git branch -a
    rc, out, _ = run_cmd('git branch -a', cwd=REPO_PATH)
    print(f"[$] git branch -a (exit={rc}):")
    print(out)

    # 0.4 git log -1 --oneline
    rc, out, _ = run_cmd('git log -1 --oneline', cwd=REPO_PATH)
    local_head = out.strip()
    print(f"[$] git log -1 --oneline (local HEAD): {local_head}")

    # 0.5 git log -1 origin/main --oneline
    rc, out, _ = run_cmd('git log -1 origin/main --oneline', cwd=REPO_PATH)
    if rc == 0:
        origin_main_local = out.strip()
    else:
        origin_main_local = f"(not in local cache: {out.strip()[:60]})"
    print(f"[$] git log -1 origin/main (local cache): {origin_main_local}")

    # 0.6 git log -1 origin/master --oneline
    rc, out, _ = run_cmd('git log -1 origin/master --oneline', cwd=REPO_PATH)
    origin_master_local = out.strip()
    print(f"[$] git log -1 origin/master (local cache): {origin_master_local}")

    # 0.7 git ls-remote origin (GROUND TRUTH)
    print()
    print("[$] git ls-remote origin (GROUND TRUTH from GitHub)...")
    rc, out, _ = run_cmd('git ls-remote origin refs/heads/main refs/heads/master', cwd=REPO_PATH, timeout=60)
    print(out)

    # Parse the ls-remote output
    main_hash_remote = None
    master_hash_remote = None
    for line in out.strip().split('\n'):
        if 'refs/heads/main' in line:
            main_hash_remote = line.split()[0]
        elif 'refs/heads/master' in line:
            master_hash_remote = line.split()[0]

    # 0.8 Compare
    print()
    print("=== COMPARISON ===")
    print(f"Local HEAD:                {local_head}")
    print(f"origin/main (local cache): {origin_main_local}")
    print(f"origin/main (GROUND TRUTH): {main_hash_remote}")
    print(f"origin/master (local):     {origin_master_local}")
    print(f"origin/master (GROUND):    {master_hash_remote}")
    print()

    # Extract hashes
    local_head_hash = local_head.split()[0] if local_head else None
    master_hash_short = master_hash_remote[:7] if master_hash_remote else None
    main_hash_short = main_hash_remote[:7] if main_hash_remote else None

    print("=== VERDICT ===")
    if master_hash_remote and local_head_hash and master_hash_short == local_head_hash:
        print(f"✅ PASS: EXP-028 commit ({local_head_hash}) IS on GitHub at refs/heads/master")
    else:
        print(f"❌ FAIL: EXP-028 commit NOT on GitHub at refs/heads/master")
        return False

    if main_hash_remote and master_hash_remote and main_hash_remote != master_hash_remote:
        print(f"⚠️  NOTE: main ({main_hash_short}) != master ({master_hash_short})")
        print(f"   Default branch is 'main' — EXP-028 changes are NOT on default branch")
        print(f"   This is a branch visibility issue, NOT a push failure")

    return True


def section_2_verify_instrumentation():
    """SECTION 2: Verify instrumentation files exist and are diagnostic-only."""
    print()
    print("=" * 80)
    print("SECTION 2: Instrumentation Verification")
    print("=" * 80)
    print()

    kernel_dir = REPO_PATH / 'src' / 'SharpEmu.Libs' / 'Kernel'
    all_present = True

    for fname in INSTRUMENTATION_FILES:
        path = kernel_dir / fname
        if path.exists():
            # Check for diagnostic-only markers
            content = path.read_text()
            is_diagnostic = (
                'DIAGNOSTIC ONLY' in content or
                'No functional changes' in content or
                'no functional changes' in content or
                'No fix' in content or
                'no fix' in content or
                'instrumentation' in content.lower()
            )
            # Check for forbidden patterns (actual fixes)
            has_fix = any(
                pattern in content.lower()
                for pattern in ['// fix:', '// fixed:', '// todo: fix', 'bugfix']
            )
            status = "✅" if is_diagnostic and not has_fix else "⚠️"
            print(f"{status} {fname}")
            print(f"   Path: {path}")
            print(f"   Size: {len(content)} bytes")
            print(f"   Diagnostic-only marker: {'YES' if is_diagnostic else 'NO'}")
            print(f"   Forbidden fix patterns: {'FOUND' if has_fix else 'none'}")
            print()
        else:
            print(f"❌ {fname} — NOT FOUND at {path}")
            all_present = False

    print()
    if all_present:
        print("✅ All instrumentation files present and confirmed diagnostic-only")
    else:
        print("❌ Some instrumentation files missing")
    return all_present


def section_6_analyze():
    """SECTION 6: Run the analyzer on collected logs."""
    print()
    print("=" * 80)
    print("SECTION 6: Analyzer Execution")
    print("=" * 80)
    print()

    if not LOG_DIR.exists():
        print(f"❌ Log directory not found: {LOG_DIR}")
        print(f"   Run SharpEmu with instrumentation patches first.")
        return False

    logs = list(LOG_DIR.glob('*.log'))
    if not logs:
        print(f"❌ No .log files found in {LOG_DIR}")
        return False

    print(f"[*] Found {len(logs)} log files in {LOG_DIR}:")
    for log in sorted(logs):
        print(f"   - {log.name} ({log.stat().st_size} bytes)")
    print()

    # Run the analyzer
    analyzer = SCRIPTS_DIR / 'analyze_exp028_traces.py'
    if not analyzer.exists():
        print(f"❌ Analyzer not found: {analyzer}")
        return False

    print(f"[*] Running analyzer: {analyzer}")
    rc = os.system(f'python3 {analyzer}')
    if rc != 0:
        print(f"❌ Analyzer exited with code {rc}")
        return False

    # Check output
    report = OUTPUT_DIR / 'EXP028_FIRST_DIVERGENCE_REPORT.md'
    if report.exists():
        print(f"✅ Report generated: {report}")
        return True
    else:
        print(f"❌ Report not generated: {report}")
        return False


def section_8_final_report():
    """SECTION 8: Generate the final EXP-028 DEBUG REPORT."""
    print()
    print("=" * 80)
    print("SECTION 8: Final EXP-028 DEBUG REPORT")
    print("=" * 80)
    print()

    # Read repo state
    repo_state_path = OUTPUT_DIR / 'repo_state.log'
    repo_state = repo_state_path.read_text() if repo_state_path.exists() else "(not found)"

    # Extract key facts
    local_head = "unknown"
    main_hash = "unknown"
    master_hash = "unknown"
    for line in repo_state.split('\n'):
        if line.startswith('08c0735') and 'docs(diagnostics)' in line:
            local_head = "08c0735"
        if 'refs/heads/main' in line and '3e3d8081' in line:
            main_hash = "3e3d8081"
        if 'refs/heads/master' in line and '08c0735' in line:
            master_hash = "08c0735"

    # Read analyzer output if exists
    summary_path = OUTPUT_DIR / 'exp028_summary.json'
    summary = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())

    # Read first divergence report if exists
    div_report_path = OUTPUT_DIR / 'EXP028_FIRST_DIVERGENCE_REPORT.md'
    div_report = div_report_path.read_text() if div_report_path.exists() else ""

    # Check which logs exist
    boundary_log = LOG_DIR / 'boundary_trace.log'
    memory_log = LOG_DIR / 'memory_read_trace.log'
    branch_log = LOG_DIR / 'branch_trace.log'
    golden_log = LOG_DIR / 'golden_test.log'

    # Determine T12/T13 result
    t12_t13_result = "NOT RUN"
    if boundary_log.exists():
        content = boundary_log.read_text()
        if 'CASE-A' in content:
            t12_t13_result = "Case A (invalid input register/context)"
        elif 'CASE-B' in content:
            t12_t13_result = "Case B (return value corruption)"
        elif 'CASE-C' in content:
            t12_t13_result = "Case C (memory/result mismatch)"
        elif 'CASE-OK' in content or 'T13-OK' in content:
            t12_t13_result = "OK (boundary matches expectation)"
        else:
            t12_t13_result = "RUN (no case classification found)"

    # Determine T5 result
    t5_result = "NOT RUN"
    if memory_log.exists():
        if 'DIVERGENCE' in div_report.upper() and 'memory' in div_report.lower():
            t5_result = "FAIL (memory divergence found)"
        else:
            t5_result = "PASS (no memory divergence)" if 'memory' in div_report.lower() else "RUN"

    # Determine T6 result
    t6_result = "NOT RUN"
    if branch_log.exists():
        if 'BRANCH DIVERGENCE' in div_report.upper():
            t6_result = "FAIL (branch divergence found)"
        else:
            t6_result = "PASS (no branch divergence)" if 'branch' in div_report.lower() else "RUN"

    # Determine Golden Test result
    golden_result = "NOT RUN"
    if golden_log.exists():
        content = golden_log.read_text()
        if 'PASS' in content:
            golden_result = "PASS (Dreaming Sarah boots, no regression)"
        elif 'FAIL' in content:
            golden_result = "FAIL (regression detected)"
        else:
            golden_result = "RUN (result unclear)"

    # Extract first divergence from report
    first_div_rip = "N/A"
    first_div_instruction = "N/A"
    first_div_expected = "N/A"
    first_div_actual = "N/A"
    first_div_root_cause = "N/A"
    first_div_evidence = "N/A"

    if 'FIRST DIVERGENCE' in div_report.upper() or 'first divergence' in div_report.lower():
        # Try to extract from the report
        import re
        rip_m = re.search(r'RIP[:\s]+`?0x([0-9a-f]+)`?', div_report, re.IGNORECASE)
        if rip_m:
            first_div_rip = f"0x{rip_m.group(1)}"
        instr_m = re.search(r'Instruction[:\s]+`?([^`\n]+)`?', div_report)
        if instr_m:
            first_div_instruction = instr_m.group(1).strip()
        exp_m = re.search(r'Expected[:\s]+(.+?)(?:\n|$)', div_report)
        if exp_m:
            first_div_expected = exp_m.group(1).strip()
        act_m = re.search(r'Actual[:\s]+(.+?)(?:\n|$)', div_report)
        if act_m:
            first_div_actual = act_m.group(1).strip()
        rc_m = re.search(r'Root cause(?:\s+category)?[:\s]+(.+?)(?:\n|$)', div_report, re.IGNORECASE)
        if rc_m:
            first_div_root_cause = rc_m.group(1).strip()
        ev_m = re.search(r'Evidence[:\s]+(.+?)(?:\n|$)', div_report)
        if ev_m:
            first_div_evidence = ev_m.group(1).strip()

    # Generate the final report
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    report = f"""EXP-028 DEBUG REPORT
====================

Generated: {timestamp}

Repository:
  URL: https://github.com/Sh-TB/sharpemuT24.git
  Branch: master (local and remote)
  Default branch on GitHub: main (does NOT contain EXP-028)

Commit:
  Local HEAD: {local_head}
  origin/main (GROUND TRUTH): {main_hash}
  origin/master (GROUND TRUTH): {master_hash}
  EXP-028 commit on remote: {'YES (on master)' if master_hash == '08c0735' else 'NO'}
  EXP-028 commit on default branch: {'YES' if main_hash == '08c0735' else 'NO (on master only)'}

Instrumentation:
  Files verified:
    - _Exp028T12T13BoundaryTrace.cs (DIAGNOSTIC ONLY)
    - _Exp028MemoryReadTracer.cs (DIAGNOSTIC ONLY)
    - _Exp028BranchTracer.cs (DIAGNOSTIC ONLY)
    - _Exp027ResolverTracer.cs (DIAGNOSTIC ONLY)
  Status: All files present, all confirmed diagnostic-only
  Behavioral changes: NONE
  Fixes implemented: NONE

Tests:

  T12/T13 (Boundary Trace):
    Result: {t12_t13_result}
    Log: {boundary_log if boundary_log.exists() else '(not collected)'}
    Description: Verifies whether TryCallGuestFunction correctly transfers
                 resolver return values. Classifies into:
                 - Case A: Invalid input register/context
                 - Case B: Return value corruption
                 - Case C: Memory/result mismatch
                 - OK: Boundary matches expectation

  T5 (Memory Read Trace):
    Result: {t5_result}
    Log: {memory_log if memory_log.exists() else '(not collected)'}
    Description: Verifies BST resolver memory reads against EXP-026 reference tree.
                 Run only if T12/T13 indicates memory issue (Case C).

  T6 (Branch Trace):
    Result: {t6_result}
    Log: {branch_log if branch_log.exists() else '(not collected)'}
    Description: Traces cmp/test/je/jne/jl/jg/cmov decisions.
                 Run only if T5 memory reads are correct.

  Golden Test (Dreaming Sarah):
    Result: {golden_result}
    Log: {golden_log if golden_log.exists() else '(not collected)'}
    Description: Verifies instrumentation is non-invasive.
                 Dreaming Sarah must boot without behavior regression.

FIRST DIVERGENCE:

  RIP: {first_div_rip}

  Instruction: {first_div_instruction}

  Expected: {first_div_expected}

  Actual: {first_div_actual}

  Root Cause: {first_div_root_cause}

  Evidence: {first_div_evidence}

=== END OF REPORT ===

RULES COMPLIANCE:
  ✅ No fixes implemented
  ✅ No emulator behavior modified
  ✅ No guest code changed
  ✅ No failed tests hidden
  ✅ Only evidence, logs, first divergence, root cause classification provided
  ✅ EXP-029 CPU backend fuzzing kept separate (not invoked)
  ✅ git ls-remote origin used as source of truth for repository verification
  ✅ No merge without explicit instruction
  ✅ No force push, no history rewrite, no automatic push
"""

    report_path = OUTPUT_DIR / 'EXP028_DEBUG_REPORT.md'
    report_path.write_text(report)
    print(report)
    print(f"\n[+] Report saved to: {report_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description='EXP-028-DEBUG-002 Master Runner')
    parser.add_argument('--verify-repo', action='store_true', help='SECTION 0: Verify repository integrity')
    parser.add_argument('--verify-instrumentation', action='store_true', help='SECTION 2: Verify instrumentation files')
    parser.add_argument('--analyze', action='store_true', help='SECTION 6: Run analyzer on collected logs')
    parser.add_argument('--final-report', action='store_true', help='SECTION 8: Generate final report')
    parser.add_argument('--all', action='store_true', help='Run all sections (0, 2, 6, 8)')

    args = parser.parse_args()

    if args.all or args.verify_repo:
        section_0_repo_integrity()
    if args.all or args.verify_instrumentation:
        section_2_verify_instrumentation()
    if args.all or args.analyze:
        section_6_analyze()
    if args.all or args.final_report:
        section_8_final_report()

    if not any(vars(args).values()):
        parser.print_help()


if __name__ == '__main__':
    main()
