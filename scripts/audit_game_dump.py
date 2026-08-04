#!/usr/bin/env python3
"""
SharpEmu game dump completeness auditor.

Checks a game directory for all files required to boot an IL2CPP Unity PS5 game
in SharpEmu. Catches the class of bug where extraction tools silently drop
PRX files or metadata files (the root cause of EXP-035..058).

Usage:
    python3 audit_game_dump.py /path/to/game/root

The game root is the directory containing eboot.bin (typically PPSA02929-app0/).
"""
import os
import sys
import struct
from pathlib import Path

# IL2CPP metadata magic (global-metadata.dat header)
IL2CPP_METADATA_MAGIC = 0xFAB11BAF

# Required files for IL2CPP Unity PS5 boot
REQUIRED_FILES = [
    ("eboot.bin", "Main executable", True),
    ("sce_module/libc.prx", "C runtime", True),
]

# IL2CPP-specific files (required for IL2CPP games)
IL2CPP_FILES = [
    ("Media/Modules/Il2cppUserAssemblies.prx", "IL2CPP compiled game code", True),
]

# Optional but common IL2CPP files
OPTIONAL_FILES = [
    ("Media/Modules/PS5Util.prx", "PS5 utility module", False),
    ("Media/Plugins/PSNCore.prx", "PSN plugin", False),
    ("Media/Plugins/PSNCommon.prx", "PSN plugin", False),
    ("global-metadata.dat", "IL2CPP metadata (if separate file)", False),
    ("Media/Modules/global-metadata.dat", "IL2CPP metadata (alternate location)", False),
]

def find_metadata_magic(root, max_file_size=200 * 1024 * 1024):
    """Search all files in root for IL2CPP metadata magic 0xFAB11BAF."""
    magic_bytes = struct.pack("<I", IL2CPP_METADATA_MAGIC)
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                fsize = os.path.getsize(fpath)
                if fsize > max_file_size:
                    continue
                with open(fpath, "rb") as f:
                    # Read first 4KB (metadata magic is always at file start)
                    header = f.read(4096)
                    if magic_bytes in header:
                        relpath = os.path.relpath(fpath, root)
                        results.append((relpath, fsize))
            except (IOError, OSError):
                continue
    return results

def check_file(root, relpath):
    """Check if a file exists and return its size."""
    fpath = os.path.join(root, relpath)
    if os.path.isfile(fpath):
        return os.path.getsize(fpath)
    return None

def audit(root):
    root = os.path.abspath(root)
    print(f"SharpEmu Game Dump Completeness Audit")
    print(f"Root: {root}")
    print(f"=" * 60)

    # Check required files
    print(f"\n--- Required Files ---")
    all_required_present = True
    for relpath, desc, required in REQUIRED_FILES:
        size = check_file(root, relpath)
        if size is not None:
            print(f"  [OK]   {relpath} ({size:,} bytes) — {desc}")
        else:
            print(f"  [MISS] {relpath} — {desc}")
            if required:
                all_required_present = False

    # Check IL2CPP files
    print(f"\n--- IL2CPP Files ---")
    il2cpp_present = True
    for relpath, desc, required in IL2CPP_FILES:
        size = check_file(root, relpath)
        if size is not None:
            print(f"  [OK]   {relpath} ({size:,} bytes) — {desc}")
        else:
            print(f"  [MISS] {relpath} — {desc}")
            if required:
                il2cpp_present = False

    # Check optional files
    print(f"\n--- Optional Files ---")
    for relpath, desc, required in OPTIONAL_FILES:
        size = check_file(root, relpath)
        if size is not None:
            print(f"  [OK]   {relpath} ({size:,} bytes) — {desc}")
        else:
            print(f"  [----] {relpath} (not found) — {desc}")

    # Search for IL2CPP metadata magic
    print(f"\n--- IL2CPP Metadata Magic (0xFAB11BAF) Search ---")
    magic_hits = find_metadata_magic(root)
    if magic_hits:
        print(f"  Found metadata magic in {len(magic_hits)} file(s):")
        for relpath, fsize in magic_hits:
            print(f"    {relpath} ({fsize:,} bytes)")
    else:
        print(f"  [NOT FOUND] IL2CPP metadata magic not found in any file!")
        print(f"  This means global-metadata.dat is missing or embedded")
        print(f"  in a file that's absent from the dump.")

    # List all .prx files found
    print(f"\n--- All PRX Files Found ---")
    prx_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            if fname.lower().endswith(".prx"):
                fpath = os.path.join(dirpath, fname)
                relpath = os.path.relpath(fpath, root)
                fsize = os.path.getsize(fpath)
                print(f"  {relpath} ({fsize:,} bytes)")
                prx_count += 1
    if prx_count == 0:
        print(f"  [NONE] No .prx files found!")

    # List all .dat files found
    print(f"\n--- All .dat Files Found ---")
    dat_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            if fname.lower().endswith(".dat"):
                fpath = os.path.join(dirpath, fname)
                relpath = os.path.relpath(fpath, root)
                fsize = os.path.getsize(fpath)
                print(f"  {relpath} ({fsize:,} bytes)")
                dat_count += 1
    if dat_count == 0:
        print(f"  [NONE] No .dat files found!")

    # Verdict
    print(f"\n{'=' * 60}")
    print(f"VERDICT")
    print(f"{'=' * 60}")
    if not all_required_present:
        print(f"  FAIL: Required files missing. Game cannot boot.")
    elif not il2cpp_present:
        print(f"  FAIL: IL2CPP PRX missing (Il2cppUserAssemblies.prx).")
        print(f"        This is the root cause of EXP-035..058 crash chain.")
        print(f"        The extraction tool likely dropped Media/Modules/ directory.")
        print(f"        Re-extract the game with ALL files, including .prx files.")
    elif not magic_hits:
        print(f"  WARN: IL2CPP PRX present but metadata magic not found.")
        print(f"        Metadata may be embedded in the PRX (check with hex dump)")
        print(f"        or in a file with a non-standard name.")
    else:
        print(f"  PASS: All required files present, metadata magic found.")
        print(f"        Ready for SharpEmu boot testing.")

    return all_required_present and il2cpp_present and bool(magic_hits)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/game/root")
        sys.exit(1)
    success = audit(sys.argv[1])
    sys.exit(0 if success else 1)
