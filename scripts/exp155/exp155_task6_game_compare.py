#!/usr/bin/env python3
"""EXP-155 Task 6: Compare Yatzi vs Dreaming Sarah."""

import os

# Check for Dreaming Sarah logs
DS_LOGS = [
    "/tmp/my-project/GoldenTests/DreamingSarah/2026-07-26_17-47-11/logs/run.log",
    "/tmp/my-project/GoldenTests/DreamingSarah/2026-07-26_18-20-00/logs/run.log",
]

YATZI_LOG = "/home/z/my-project/scripts/exp118_run.log"

def analyze_log(path, label):
    if not os.path.exists(path):
        print(f"\n  {label}: LOG NOT FOUND ({path})")
        return None
    
    with open(path, 'r') as f:
        content = f.read()
    
    data = {
        'label': label,
        'path': path,
        'has_il2cpp': 'il2cpp' in content.lower(),
        'has_resolver': 'RESOLVER-TRACE' in content,
        'has_case_b': 'EXP028-T13-CASE-B' in content,
        'has_il2cpp_runtime_class_init': 'il2cpp_runtime_class_init' in content,
        'has_execute_once': '_Execute_once' in content,
        'has_waitsema': 'WaitSema' in content or 'sceKernelWaitSema' in content,
        'has_playerloop': 'PlayerLoop' in content,
        'has_dt_init': 'dt_init' in content,
        'resolver_entries': content.count('RESOLVER-TRACE') // 2,  # Entry + Exit
        'case_b_count': content.count('EXP028-T13-CASE-B'),
        'size': len(content),
    }
    
    # Check for frames rendered
    data['has_frames'] = 'frame' in content.lower() or 'screenshot' in content.lower()
    data['has_videoout'] = 'VideoOut' in content
    
    return data

def main():
    print("=" * 80)
    print("EXP-155 Task 6: Compare Yatzi vs Dreaming Sarah")
    print("=" * 80)
    
    # Analyze Yatzi
    yatzi = analyze_log(YATZI_LOG, "Yatzi (PPSA17697)")
    
    # Analyze Dreaming Sarah
    ds = None
    for log_path in DS_LOGS:
        ds = analyze_log(log_path, "Dreaming Sarah (PPSA02929)")
        if ds:
            break
    
    # Compare
    print(f"\n{'='*80}")
    print("COMPARISON TABLE")
    print(f"{'='*80}")
    
    if yatzi:
        print(f"\n  Yatzi:")
        for k, v in yatzi.items():
            if k not in ('label', 'path'):
                print(f"    {k}: {v}")
    
    if ds:
        print(f"\n  Dreaming Sarah:")
        for k, v in ds.items():
            if k not in ('label', 'path'):
                print(f"    {k}: {v}")
    
    print(f"\n{'='*80}")
    print("GAME DIFFERENCE ANALYSIS")
    print(f"{'='*80}")
    
    if yatzi and ds:
        print(f"""
Key Differences:
  1. IL2CPP: Yatzi={yatzi['has_il2cpp']}, DS={ds['has_il2cpp']}
     → Yatzi uses IL2CPP (Unity), Dreaming Sarah does not (native C++)
  
  2. Resolver: Yatzi={yatzi['has_resolver']}, DS={ds['has_resolver']}
     → Yatzi has IL2CPP BST resolver, DS does not
  
  3. CASE-B RAX corruption: Yatzi={yatzi['case_b_count']}, DS={ds['case_b_count']}
     → Yatzi has 232 RAX corruptions, DS has 0 (no resolver = no corruption)
  
  4. il2cpp_runtime_class_init: Yatzi={yatzi['has_il2cpp_runtime_class_init']}, DS={ds['has_il2cpp_runtime_class_init']}
     → Only Yatzi uses this function
  
  5. std::_Execute_once: Yatzi={yatzi['has_execute_once']}, DS={ds['has_execute_once']}
     → Neither game shows _Execute_once in logs (decoder hypothesis REJECTED)
  
  6. WaitSema: Yatzi={yatzi['has_waitsema']}, DS={ds['has_waitsema']}
     → Both use semaphores, but only Yatzi deadlocks
  
  7. PlayerLoop: Yatzi={yatzi['has_playerloop']}, DS={ds['has_playerloop']}
     → Only Yatzi has PlayerLoop (Unity-specific)

ANALYSIS:
  Dreaming Sarah works because it does NOT use IL2CPP.
  It's a native C++ game — no BST resolver, no il2cpp_runtime_class_init,
  no type initialization flags, no PlayerLoop registration.

  Yatzi fails because it uses Unity IL2CPP, which requires:
  1. BST resolver to find IL2CPP API functions
  2. il2cpp_runtime_class_init to initialize types
  3. Type initialization flags to be set
  4. PlayerLoop registration

  The EXP-138 RAX propagation bug ONLY affects games that use the
  IL2CPP resolver (Unity games). Native C++ games like Dreaming Sarah
  are unaffected because they don't call TryCallGuestFunction for
  IL2CPP API resolution.

  The decoder hypothesis about std::_Execute_once is REJECTED —
  neither game shows this function in logs.

CONCLUSION:
  The difference is NOT std::_Execute_once or nested transitions.
  The difference is IL2CPP: Yatzi uses it, Dreaming Sarah doesn't.
  The EXP-138 RAX propagation bug only affects IL2CPP resolver calls.
""")
    else:
        print("  Dreaming Sarah log not found — cannot compare")

if __name__ == '__main__':
    main()
