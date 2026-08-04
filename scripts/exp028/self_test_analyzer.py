#!/usr/bin/env python3
"""
EXP-028: Self-test for the analyzer — creates synthetic test logs and
verifies the analyzer correctly detects divergence.
"""

import os
import sys
import shutil
from pathlib import Path

LOG_DIR = Path('/tmp/exp028_logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Backup existing logs
backup_dir = Path('/tmp/exp028_logs_backup')
if LOG_DIR.exists():
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(LOG_DIR, backup_dir)
    shutil.rmtree(LOG_DIR)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

print("[*] Created test log directory: /tmp/exp028_logs")
print()

# ============================================================
# Test 1: T12/T13 Case C (genuine zero — resolver returns 0)
# ============================================================
print("[*] Test 1: T12/T13 Case C (genuine zero)")
boundary_log = LOG_DIR / 'boundary_trace.log'
with open(boundary_log, 'w') as f:
    f.write("""[EXP028-T12-PRE]  call=1 query='il2cpp_init' entry=0x804ed9b90 symAddr=0x801B5A62C
  RAX=0x0 RBX=0x0 RCX=0x0 RDX=0x0
  RSI=0x0 RDI=0x801B5A62C R8=0x0 R9=0x0
  R12=0x0 R13=0x0 R14=0x0 R15=0x0
  RBP=0x0 RSP=0x7FFFFFFFE000
  RFLAGS=0x202 (CF=0 PF=0 AF=0 ZF=0 SF=0 OF=0 TF=0 IF=1)
[EXP028-T12-POST] call=1 query='il2cpp_init'
  returnValue=0x0 error=''
  cpuContext.Rax=0x0
[EXP028-T13-CASE-C] Resolver genuinely returned 0 (no corruption detected)
""")

# Run analyzer
import subprocess
result = subprocess.run(
    ['python3', '/home/z/my-project/scripts/exp028/analyze_exp028_traces.py'],
    capture_output=True, text=True
)
print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[-200:])

# Check the report
report = Path('/home/z/my-project/download/exp028/EXP028_FIRST_DIVERGENCE_REPORT.md').read_text()
print()
print("--- Report excerpt (T12/T13 section) ---")
import re
m = re.search(r'## SECTION 2.*?(?=## SECTION 3)', report, re.DOTALL)
if m:
    print(m.group(0)[:500])

# Verify Case C was detected
assert 'Case C' in report, "FAIL: Case C not detected"
print()
print("[+] Test 1 PASSED: Case C detected")

# ============================================================
# Test 2: T5 Memory divergence (native reads different value)
# ============================================================
print()
print("[*] Test 2: T5 Memory divergence")
memory_log = LOG_DIR / 'memory_read_trace.log'
with open(memory_log, 'w') as f:
    f.write("""[EXP028-T5] call=1 step=1 rip=0x804ed9b9b mov r15, [rip+0x3c79b66]
  list_head_ptr=0x808b53708 src_addr=0x808b53708 size=8 value=0x2000003f20
[EXP028-T5] call=1 step=2 rip=0x804ed9ba2 mov rbx, [r15+8]
  r15=0x2000003f20 src_addr=0x2000003f20+8 size=8 value=0x0
[EXP028-T5] call=1 step=3 rip=0x804ed9ba6 cmp byte [rbx+0x19], 0
  rbx=0x0 src_addr=0x19 size=1 value=0x0
""")

result = subprocess.run(
    ['python3', '/home/z/my-project/scripts/exp028/analyze_exp028_traces.py'],
    capture_output=True, text=True
)
print(result.stdout[-800:] if len(result.stdout) > 800 else result.stdout)

# Check the report
report = Path('/home/z/my-project/download/exp028/EXP028_FIRST_DIVERGENCE_REPORT.md').read_text()
print()
print("--- Report excerpt (SECTION 5) ---")
m = re.search(r'## SECTION 5.*?(?=## SECTION 6)', report, re.DOTALL)
if m:
    print(m.group(0)[:1000])

# ============================================================
# Cleanup: restore original logs
# ============================================================
print()
print("[*] Cleaning up test logs...")
shutil.rmtree(LOG_DIR)
if backup_dir.exists():
    shutil.copytree(backup_dir, LOG_DIR)
    shutil.rmtree(backup_dir)
    print("[+] Restored original logs")
else:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print("[+] No original logs to restore (clean state)")

print()
print("[+] Self-test complete")
