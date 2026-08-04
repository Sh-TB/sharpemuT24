#!/usr/bin/env python3
"""
EXP-026 Stage 3: Build the actual BST tree from BST-WALK log.
Saves tree as JSON for use by the synthetic CPU emulator.

Tree structure (from disassembly + BST-WALK):
  Node layout:
    [0x00] = right child ptr
    [0x08] = parent ptr
    [0x10] = left child ptr
    [0x18] = color (0=RED, 1=BLACK)
    [0x19] = matched flag (0=real node, 1=sentinel)
    [0x20] = symbol name ptr (-> C string)
    [0x28] = function impl ptr

List head struct (at 0x808B53708 → 0x200003c20 or similar):
    [+0x00] = ???
    [+0x08] = root node ptr

Resolver at 0x804ED9B90 reads:
    r15 = [0x808B53708]      ; struct ptr
    rbx = [r15 + 8]          ; root node

For the synthetic test, we just need:
  - list_head_struct addr (any unique addr, e.g. 0xDEAD0000)
  - root node addr (matches what's in tree)
  - each node: addr, name, left_addr, right_addr, flag_19, color, func_ptr
"""

import json
import re
import sys
from pathlib import Path

BST_WALK_LOG = '/home/z/my-project/download/evidence_final/test_d1_bst_walk.log'
OUTPUT_JSON = '/home/z/my-project/scripts/exp026_tree.json'

# Tree head struct address — we'll use the runtime struct addr we observed
LIST_HEAD_STRUCT_ADDR = 0x200003c20  # placeholder; real value read from log
LIST_HEAD_PTR_ADDR = 0x808B53708      # the global pointer that points to struct


def parse_bst_walk_log(path):
    """Parse BST-WALK log entries to build tree dict."""
    nodes = {}
    pattern = re.compile(
        r"BST-WALK\] Node #(\d+) @0x([0-9a-f]+): "
        r"name='([^']*)' "
        r"left=0x([0-9a-f]+) "
        r"right=0x([0-9a-f]+) "
        r"flag\[0x19\]=(\d+)"
    )

    with open(path) as f:
        for line in f:
            m = pattern.search(line)
            if m:
                idx, addr_hex, name, left_hex, right_hex, flag = m.groups()
                addr = int(addr_hex, 16)
                left = int(left_hex, 16)
                right = int(right_hex, 16)
                flag = int(flag)
                nodes[addr] = {
                    'addr': addr,
                    'idx': int(idx),
                    'name': name,
                    'left': left,    # [0x10]
                    'right': right,  # [0x00]
                    'flag_19': flag, # 1=sentinel, 0=real
                    # color and func_ptr unknown from this log; we'll synthesize
                    'color': 1 if flag == 1 else 0,  # sentinel=BLACK
                    'func_ptr': 0x804ed8770 if flag == 0 else 0,  # placeholder
                }

    # Find the root — it's the node referenced as "Root node" in the log
    root_addr = None
    root_pattern = re.compile(r"BST-WALK\] Root node: 0x([0-9a-f]+)")
    listhead_pattern = re.compile(r"BST-WALK\] List head struct: 0x([0-9a-f]+)")
    with open(path) as f:
        for line in f:
            m = root_pattern.search(line)
            if m:
                root_addr = int(m.group(1), 16)
                break

    list_head_struct = None
    with open(path) as f:
        for line in f:
            m = listhead_pattern.search(line)
            if m:
                list_head_struct = int(m.group(1), 16)
                break

    return nodes, root_addr, list_head_struct


def main():
    print(f"[*] Parsing BST-WALK log: {BST_WALK_LOG}")
    nodes, root_addr, list_head_struct = parse_bst_walk_log(BST_WALK_LOG)

    print(f"[*] Parsed {len(nodes)} nodes")
    print(f"[*] Root node addr: 0x{root_addr:x}")
    print(f"[*] List head struct addr: 0x{list_head_struct:x}" if list_head_struct else "[*] List head struct addr: not found")

    if root_addr is None or root_addr not in nodes:
        print("[!] ERROR: Root node not found in tree")
        sys.exit(1)

    # Use real list_head_struct if found, else fallback
    if list_head_struct is None:
        list_head_struct = LIST_HEAD_STRUCT_ADDR

    # Build the JSON output
    out = {
        'list_head_ptr_addr': LIST_HEAD_PTR_ADDR,  # global pointer
        'list_head_struct_addr': list_head_struct,  # struct that contains root at +8
        'root_node_addr': root_addr,
        'node_struct_size': 0x30,
        'node_field_offsets': {
            'right':       0x00,
            'parent':      0x08,
            'left':        0x10,
            'color':       0x18,
            'matched_flag':0x19,
            'symbol_name': 0x20,
            'func_impl':   0x28,
        },
        'nodes': {f"0x{a:x}": n for a, n in nodes.items()},
    }

    # Summary
    real = sum(1 for n in nodes.values() if n['flag_19'] == 0)
    sentinels = sum(1 for n in nodes.values() if n['flag_19'] == 1)
    print(f"[*] Real nodes: {real}")
    print(f"[*] Sentinel nodes: {sentinels}")

    # Sanity: verify the tree is connected from root
    visited = set()
    stack = [root_addr]
    while stack:
        a = stack.pop()
        if a == 0 or a in visited:
            continue
        visited.add(a)
        if a not in nodes:
            print(f"[!] WARN: Node 0x{a:x} referenced but not in tree")
            continue
        n = nodes[a]
        stack.append(n['left'])
        stack.append(n['right'])

    print(f"[*] Reachable from root: {len(visited)} nodes")
    unreached = set(nodes.keys()) - visited
    if unreached:
        print(f"[!] WARN: {len(unreached)} nodes NOT reachable from root")
        for a in list(unreached)[:5]:
            print(f"      0x{a:x} name='{nodes[a]['name']}'")

    Path(OUTPUT_JSON).write_text(json.dumps(out, indent=2))
    print(f"[+] Wrote tree to {OUTPUT_JSON}")

    # Print first 5 nodes for verification
    print("\n[*] First 5 nodes:")
    for i, (a, n) in enumerate(sorted(nodes.items(), key=lambda x: x[1]['idx'])[:5]):
        print(f"    #{n['idx']} @0x{a:x}: name='{n['name']}' left=0x{n['left']:x} right=0x{n['right']:x} flag={n['flag_19']}")


if __name__ == '__main__':
    main()
