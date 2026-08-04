#!/usr/bin/env python3
"""Compute PS5 NID for a given symbol name — matches SharpEmu's Ps5Nid.Compute exactly.

Algorithm (verified against the SharpEmu source):
1. SHA1(name_utf8_bytes + 16-byte salt)
2. Take first 8 bytes, reverse byte order
3. Base64 encode (standard alphabet)
4. Strip "=" padding
5. Replace "/" with "-"
"""
import hashlib
import base64

SALT = bytes([
    0x51, 0x8D, 0x64, 0xA6, 0x35, 0xDE, 0xD8, 0xC1,
    0xE6, 0xB0, 0x39, 0xB1, 0xC3, 0xE5, 0x52, 0x30,
])

def compute_nid(name: str) -> str:
    h = hashlib.sha1(name.encode("utf-8") + SALT).digest()
    reversed_bytes = h[:8][::-1]
    b64 = base64.b64encode(reversed_bytes).decode("ascii")
    b64 = b64.rstrip("=")
    return b64.replace("/", "-")

if __name__ == "__main__":
    # Verify against known NIDs
    test_known = {
        "sceKernelWaitSema": "Zxa0VhQVTsk",
        "sceKernelCreateSema": "188x57JYp0g",
        "sceKernelAllocateDirectMemory": "rTXw65xmLIA",
    }
    print("Verifying NID algorithm against known NIDs:")
    algorithm_correct = True
    for name, expected in test_known.items():
        actual = compute_nid(name)
        ok = actual == expected
        print(f"  {name}: expected={expected} actual={actual} {('OK' if ok else 'MISMATCH')}")
        if not ok:
            algorithm_correct = False
    print()

    if not algorithm_correct:
        print("Algorithm incorrect — aborting.")
        exit(1)

    print("Algorithm verified. Now searching for unresolved NIDs:")
    print()

    target_nids = {
        "XAKDgxcra6k": None,
        "J3edELK4FvM": None,
        "1D0H2KNjshE": None,
        "hsi9drzHR2k": None,
    }

    found = {}
    target_count = len(target_nids)
    with open("/tmp/my-project/work/sharpemuT24/scripts/ps5_names.txt") as f:
        for line_num, line in enumerate(f):
            name = line.strip()
            if not name:
                continue
            nid = compute_nid(name)
            if nid in target_nids:
                found[nid] = name
                print(f"  FOUND: {nid} = {name!r}")
                target_nids.pop(nid)
                if not target_nids:
                    break
    print()
    print("Unresolved NIDs (not found in database):")
    for nid in target_nids:
        print(f"  {nid} = NOT IN DATABASE")
