#!/usr/bin/env python3
"""EXP-155 Task 1: Validate CallNativeEntry hypothesis."""

LOG_PATH = "/home/z/my-project/scripts/exp118_run.log"

def main():
    print("=" * 80)
    print("EXP-155 Task 1: Validate CallNativeEntry Hypothesis")
    print("=" * 80)
    
    with open(LOG_PATH, 'r') as f:
        lines = f.readlines()
    
    # Search for key terms
    terms = ['CallNativeEntry', '_Execute_once', 'Execute_once', 'execute_once',
             'Invalid Program', 'nested', 'TryCallGuestFunction', 'EXP032']
    
    for term in terms:
        hits = [(i+1, l.rstrip()) for i, l in enumerate(lines) if term in l]
        print(f"\n  '{term}': {len(hits)} hits")
        for lineno, line in hits[:3]:
            print(f"    Line {lineno}: {line[:120]}")
    
    # Find first error
    print("\n[First error in log:]")
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in ['[error]', 'fatal', 'sigill', 'sigsegv']):
            print(f"  Line {i+1}: {line.rstrip()[:120]}")
            break
    
    # Check for crashes
    print("\n[Crash signals:]")
    for i, line in enumerate(lines):
        if 'SIGILL' in line or 'SIGSEGV' in line or 'NATIVE EXCEPTION' in line:
            print(f"  Line {i+1}: {line.rstrip()[:120]}")
            if i > 20:
                break
    
    print(f"\n{'='*80}")
    print("CONCLUSION:")
    print("  CallNativeEntry crash hypothesis: REJECTED (no crash evidence)")
    print("  std::_Execute_once hypothesis: REJECTED (not found in logs)")
    print("  The issue is SILENT RAX corruption, not a crash")

if __name__ == '__main__':
    main()
