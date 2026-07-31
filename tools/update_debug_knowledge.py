#!/usr/bin/env python3
"""Scan docs/diagnostics/*.md for EXP reports and update the index.

Usage:
    python tools/update_debug_knowledge.py

Outputs:
    - List of found EXP reports
    - List of missing EXP numbers
    - Updates YATZI_EXP_INDEX.md if --update flag is passed
"""

import os
import re
import sys
from pathlib import Path

DIAGNOSTICS_DIR = Path(__file__).parent.parent / "docs" / "diagnostics"

def scan_exp_files():
    """Scan all .md files in diagnostics dir for EXP numbers."""
    exp_files = {}  # exp_num -> (filename, title)
    
    if not DIAGNOSTICS_DIR.exists():
        print(f"ERROR: {DIAGNOSTICS_DIR} does not exist")
        return exp_files
    
    for md_file in sorted(DIAGNOSTICS_DIR.glob("*.md")):
        content = md_file.read_text(errors='replace')
        
        # Look for EXP-NNN in filename or content
        # Check filename first
        fname_match = re.match(r'EXP-(\d+)', md_file.name)
        if fname_match:
            exp_num = int(fname_match.group(1))
            # Extract title from first heading
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else md_file.name
            exp_files[exp_num] = (md_file.name, title)
            continue
        
        # Check content for EXP-NNN pattern in first few lines
        for line in content.split('\n')[:10]:
            content_match = re.search(r'EXP-(\d+)', line)
            if content_match:
                exp_num = int(content_match.group(1))
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else md_file.name
                if exp_num not in exp_files:
                    exp_files[exp_num] = (md_file.name, title)
                break
    
    return exp_files

def find_missing(exp_files):
    """Find missing EXP numbers in the sequence."""
    if not exp_files:
        return []
    
    min_exp = min(exp_files.keys())
    max_exp = max(exp_files.keys())
    
    missing = []
    for i in range(min_exp, max_exp + 1):
        if i not in exp_files:
            missing.append(i)
    
    return missing

def main():
    print("=" * 60)
    print("SharpEmuT24 Debug Knowledge Scanner")
    print("=" * 60)
    print()
    
    exp_files = scan_exp_files()
    
    print(f"Found {len(exp_files)} EXP reports:")
    print()
    
    for exp_num in sorted(exp_files.keys()):
        filename, title = exp_files[exp_num]
        print(f"  EXP-{exp_num:03d}  {filename:40s}  {title[:60]}")
    
    print()
    
    missing = find_missing(exp_files)
    if missing:
        print(f"Missing {len(missing)} EXP reports:")
        # Group consecutive ranges
        ranges = []
        start = missing[0]
        end = missing[0]
        for m in missing[1:]:
            if m == end + 1:
                end = m
            else:
                ranges.append((start, end))
                start = m
                end = m
        ranges.append((start, end))
        
        for s, e in ranges:
            if s == e:
                print(f"  EXP-{s:03d}")
            else:
                print(f"  EXP-{s:03d}..EXP-{e:03d}")
    else:
        print("No missing EXP reports in range.")
    
    print()
    print("=" * 60)
    
    # Check for master files
    master_files = [
        "YATZI_MASTER_DEBUG_STATE.md",
        "YATZI_COMPLETE_DIAGNOSTIC_HISTORY.md",
        "YATZI_KNOWLEDGE_BASE.md",
        "YATZI_EXP_INDEX.md",
    ]
    
    print("Knowledge base files:")
    for mf in master_files:
        path = DIAGNOSTICS_DIR / mf
        if path.exists():
            lines = len(path.read_text().split('\n'))
            print(f"  ✓ {mf:50s} ({lines} lines)")
        else:
            print(f"  ✗ {mf:50s} MISSING")
    
    print()
    print("=" * 60)
    
    # Also scan for non-EXP diagnostic files
    print("Other diagnostic files:")
    for md_file in sorted(DIAGNOSTICS_DIR.glob("*.md")):
        if not re.match(r'EXP-\d+', md_file.name) and md_file.name not in master_files:
            print(f"  {md_file.name}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
