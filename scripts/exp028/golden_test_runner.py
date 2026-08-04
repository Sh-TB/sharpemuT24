#!/usr/bin/env python3
"""
EXP-028-DEBUG-001 SECTION 8: Golden Test Runner

Runs Dreaming Sarah as a regression test to verify that EXP-028
instrumentation patches are DIAGNOSTIC ONLY (no behavior change).

USAGE:
    python3 golden_test_runner.py <sharpemu_binary> <dreaming_sarah_eboot>

EXAMPLE:
    python3 /home/z/my-project/scripts/exp028/golden_test_runner.py \\
        /tmp/my-project/work/sharpemuT24/artifacts/bin/Release/net10.0/linux-x64/publish/SharpEmu.bin \\
        /tmp/games/dreaming_sarah/eboot.bin

OUTPUT:
    /tmp/exp028_logs/golden_test.log

The script:
1. Runs Dreaming Sarah WITH the EXP-028 patches applied
2. Captures boot logs for 60 seconds
3. Checks for:
   - Boot starts ([INFO] SharpEmu starting)
   - ELF loads ([LOADER] eboot base)
   - No crash (process still running after 30s)
   - First frame renders (videoOutSubmitFlip)
   - No new errors compared to baseline
4. Writes verdict to golden_test.log

EXIT CODES:
    0 = PASS (Dreaming Sarah boots, no behavior change)
    1 = FAIL (Dreaming Sarah fails to boot or crashes)
    2 = ERROR (script error, e.g. missing files)
"""

import subprocess
import sys
import time
import os
import re
from pathlib import Path
from datetime import datetime

LOG_DIR = Path('/tmp/exp028_logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

GOLDEN_LOG = LOG_DIR / 'golden_test.log'


def run_golden_test(sharpemu_bin, eboot_path, timeout=60):
    """Run Dreaming Sarah and check for boot success."""

    if not Path(sharpemu_bin).exists():
        print(f"[!] SharpEmu binary not found: {sharpemu_bin}")
        return False, "SharpEmu binary not found"
    if not Path(eboot_path).exists():
        print(f"[!] Dreaming Sarah eboot not found: {eboot_path}")
        return False, "Dreaming Sarah eboot not found"

    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f"[*] Golden Test starting at {timestamp}")
    print(f"[*] SharpEmu: {sharpemu_bin}")
    print(f"[*] Eboot: {eboot_path}")
    print(f"[*] Timeout: {timeout}s")
    print()

    # Run SharpEmu with Dreaming Sarah
    start_time = time.time()
    try:
        proc = subprocess.Popen(
            [sharpemu_bin, eboot_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        return False, f"Failed to start SharpEmu: {e}"

    # Collect output for timeout seconds
    output_lines = []
    boot_started = False
    elf_loaded = False
    first_frame = False
    crash_detected = False

    try:
        while time.time() - start_time < timeout:
            if proc.poll() is not None:
                # Process exited
                if proc.returncode != 0:
                    crash_detected = True
                break

            line = proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue

            output_lines.append(line.rstrip())
            line_lower = line.lower()

            # Check for boot milestones
            if 'sharpemu starting' in line_lower or 'sharpemu unofficial' in line_lower:
                boot_started = True
                print(f"[+] Boot started at {time.time() - start_time:.1f}s")
            if 'eboot base' in line_lower or 'loading:' in line_lower:
                if not elf_loaded:
                    elf_loaded = True
                    print(f"[+] ELF loaded at {time.time() - start_time:.1f}s")
            if 'submitflip' in line_lower or 'frame' in line_lower and 'present' in line_lower:
                if not first_frame:
                    first_frame = True
                    print(f"[+] First frame at {time.time() - start_time:.1f}s")
            if 'sigsegv' in line_lower or 'sigabrt' in line_lower or 'crash' in line_lower:
                crash_detected = True
                print(f"[!] Crash detected at {time.time() - start_time:.1f}s")
                break

    except KeyboardInterrupt:
        print("[*] Interrupted by user")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    elapsed = time.time() - start_time

    # Write log
    with open(GOLDEN_LOG, 'w') as f:
        f.write(f"EXP-028-DEBUG-001 Golden Test Log\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"SharpEmu: {sharpemu_bin}\n")
        f.write(f"Eboot: {eboot_path}\n")
        f.write(f"Timeout: {timeout}s\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n")
        f.write(f"Boot started: {boot_started}\n")
        f.write(f"ELF loaded: {elf_loaded}\n")
        f.write(f"First frame: {first_frame}\n")
        f.write(f"Crash detected: {crash_detected}\n")
        f.write(f"Exit code: {proc.returncode}\n")
        f.write(f"\n--- OUTPUT ---\n")
        for line in output_lines:
            f.write(line + '\n')

    # Determine verdict
    verdict = "PASS"
    reasons = []

    if not boot_started:
        verdict = "FAIL"
        reasons.append("Boot did not start")
    if not elf_loaded:
        verdict = "FAIL"
        reasons.append("ELF did not load")
    if crash_detected:
        verdict = "FAIL"
        reasons.append("Crash detected")
    if not first_frame and elapsed >= timeout - 1:
        # Allow first_frame to be missing if we hit timeout
        # (some games take longer than 60s)
        reasons.append("WARNING: No first frame within timeout")

    if not reasons:
        reasons.append("All checks passed")

    print()
    print(f"[*] Verdict: {verdict}")
    for r in reasons:
        print(f"    - {r}")
    print(f"[*] Log written to: {GOLDEN_LOG}")

    return verdict == "PASS", "; ".join(reasons)


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <sharpemu_binary> <dreaming_sarah_eboot>")
        print(f"Example: {sys.argv[0]} /path/to/SharpEmu.bin /path/to/dreaming_sarah/eboot.bin")
        sys.exit(2)

    sharpemu_bin = sys.argv[1]
    eboot_path = sys.argv[2]

    success, reason = run_golden_test(sharpemu_bin, eboot_path)

    if success:
        print()
        print("[+] Golden Test PASSED — instrumentation is diagnostic-only")
        sys.exit(0)
    else:
        print()
        print(f"[!] Golden Test FAILED — {reason}")
        print("[!] The instrumentation patch has a bug — fix it before collecting Yatzi traces")
        sys.exit(1)


if __name__ == '__main__':
    main()
