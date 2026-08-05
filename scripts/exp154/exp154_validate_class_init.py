#!/usr/bin/env python3
"""EXP-154 Task 1: Validate il2cpp_runtime_class_init from runtime log."""

import re

LOG_PATH = "/home/z/my-project/scripts/exp118_run.log"

def main():
    print("=" * 80)
    print("EXP-154 Task 1: Validate il2cpp_runtime_class_init")
    print("=" * 80)
    
    with open(LOG_PATH, 'r') as f:
        lines = f.readlines()
    
    # Find Entry #170 context
    print("\n[1] Full context around il2cpp_runtime_class_init (Entry #170):")
    print("-" * 80)
    
    for i, line in enumerate(lines):
        if 'Entry #170' in line and 'il2cpp_runtime_class_init' in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 30)
            for j in range(start, end):
                print(f"  Line {j+1}: {lines[j].rstrip()[:140]}")
            break
    
    # Extract key values
    print("\n[2] Key values extracted:")
    print("-" * 80)
    
    func_impl = None
    resolver_return = None
    cpu_context_rax = None
    got_value = None
    got_slot = None
    inner_rax = None
    native_return = None
    
    for i, line in enumerate(lines):
        if 'il2cpp_runtime_class_init' in line or (i > 0 and 'il2cpp_runtime_class_init' in lines[i-1]):
            # func_impl from EXP028-T6
            if 'EXP028-T6' in line and 'func_impl' in line:
                m = re.search(r'func_impl=0x([0-9a-fA-F]+)', line)
                if m:
                    func_impl = '0x' + m.group(1).upper()
            
            # returnValue and GOT from EXP029
            if 'EXP029' in line:
                m = re.search(r'returnValue=0x([0-9a-fA-F]+)', line)
                if m:
                    resolver_return = '0x' + m.group(1).upper()
                m = re.search(r'GOT_value=0x([0-9a-fA-F]+)', line)
                if m:
                    got_value = '0x' + m.group(1).upper()
                m = re.search(r'strcmp_GOT_slot=0x([0-9a-fA-F]+)', line)
                if m:
                    got_slot = '0x' + m.group(1).upper()
    
    # Search for EXP028-T13 CASE-B specifically for call=170
    print("\n[3] EXP028-T13 Return Corruption evidence:")
    print("-" * 80)
    
    for i, line in enumerate(lines):
        if 'EXP028-T13' in line and '170' in line:
            start = max(0, i)
            end = min(len(lines), i + 6)
            for j in range(start, end):
                print(f"  Line {j+1}: {lines[j].rstrip()[:140]}")
            print()
    
    # Search for RESOLVER-TRACE Exit #170
    print("\n[4] RESOLVER-TRACE Exit #170:")
    print("-" * 80)
    
    for i, line in enumerate(lines):
        if 'RESOLVER-TRACE' in line and 'Exit' in line and '#170' in line:
            print(f"  Line {i+1}: {line.rstrip()[:140]}")
            m = re.search(r'RAX=0x([0-9a-fA-F]+)', line)
            if m:
                resolver_return = '0x' + m.group(1).upper()
    
    # Search for EXP032 entries near Entry #170
    print("\n[5] EXP032 ABI traces near Entry #170:")
    print("-" * 80)
    
    in_entry_170 = False
    for i, line in enumerate(lines):
        if 'Entry #170' in line and 'il2cpp_runtime_class_init' in line:
            in_entry_170 = True
        elif 'Entry #171' in line:
            in_entry_170 = False
        
        if in_entry_170 and 'EXP032' in line:
            print(f"  Line {i+1}: {line.rstrip()[:140]}")
            if 'nativeReturn' in line:
                m = re.search(r'nativeReturn=0x([0-9a-fA-F]+)', line)
                if m:
                    native_return = '0x' + m.group(1).upper()
            if 'innerRax' in line:
                m = re.search(r'innerRax=0x([0-9a-fA-F]+)', line)
                if m:
                    inner_rax = '0x' + m.group(1).upper()
    
    # Search for EXP028-T12-POST returnValue
    print("\n[6] EXP028-T12-POST returnValue:")
    print("-" * 80)
    
    in_post_170 = False
    for i, line in enumerate(lines):
        if 'EXP028-T12-POST' in line and '170' in line:
            in_post_170 = True
            print(f"  Line {i+1}: {line.rstrip()[:140]}")
            continue
        if in_post_170:
            if 'returnValue' in line or 'cpuContext.Rax' in line:
                print(f"  Line {i+1}: {line.rstrip()[:140]}")
                m = re.search(r'cpuContext\.Rax=0x([0-9a-fA-F]+)', line)
                if m:
                    cpu_context_rax = '0x' + m.group(1).upper()
            if 'RESOLVER-TRACE' in line or 'Entry #' in line:
                in_post_170 = False
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY OF EVIDENCE")
    print(f"{'='*80}")
    print(f"""
  Function: il2cpp_runtime_class_init
  
  1. Resolved address (func_impl from BST):  {func_impl}
  2. Resolver return value (Exit RAX):       {resolver_return}
  3. innerRax (from EXP032):                 {inner_rax}
  4. nativeReturn (from EXP032):             {native_return}
  5. cpuContext.Rax (after call):            {cpu_context_rax}
  6. GOT slot address:                       {got_slot}
  7. GOT value stored:                       {got_value}
""")
    
    if resolver_return and cpu_context_rax:
        if resolver_return.lower() != cpu_context_rax.lower():
            print(f"  *** MISMATCH CONFIRMED ***")
            print(f"  Resolver returned: {resolver_return}")
            print(f"  cpuContext.Rax:    {cpu_context_rax}")
            print(f"  These should be identical but differ!")
            print(f"  This IS the EXP-138 RAX propagation bug.")
            print(f"  The GOT slot will receive the WRONG value.")
        else:
            print(f"  Values match — no RAX propagation issue")
    else:
        print(f"  Some values not found — check log manually")

if __name__ == '__main__':
    main()
