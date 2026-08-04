#!/usr/bin/env python3
"""Scan Yatzi binaries for unresolved NIDs and figure out where they're imported from."""
import struct

NIDS = {
    "XAKDgxcra6k": "arch_init_gc",
    "J3edELK4FvM": "arch_raise_user",
    "1D0H2KNjshE": "powf",
    "hsi9drzHR2k": "log2f",
}

YATZI_DIR = "/tmp/exp125_games/yatzi"
FILES_TO_SCAN = ["eboot.bin", "Il2cppUserAssemblies.prx", "libc.prx", "libSceNpCppWebApi.prx", "PS5Util.prx", "lib_burst_generated.prx"]

import os

for fname in FILES_TO_SCAN:
    path = os.path.join(YATZI_DIR, fname)
    if not os.path.exists(path):
        continue
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        data = f.read()
    print(f"\n=== {fname} ({size/1024/1024:.1f}MB) ===")
    for nid, name in NIDS.items():
        nid_bytes = nid.encode("ascii")
        offset = 0
        count = 0
        while True:
            idx = data.find(nid_bytes, offset)
            if idx < 0:
                break
            count += 1
            offset = idx + 1
        if count > 0:
            print(f"  NID {nid} ({name}): {count} occurrences in binary strings")
