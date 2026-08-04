#!/usr/bin/env python3
"""
EXP-061: Artifact Identity Audit.
Extracts game identity from old and new eboot.bin files.
"""
import struct
import os
import hashlib

OLD_EBOOT = "/tmp/my-project/upload/PPSA02929/PPSA02929-app0/eboot.bin"
NEW_EBOOT = "/tmp/games/yatzi/eboot.bin"
PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
METADATA = "/tmp/games/yatzi/global-metadata.dat"
OLD_LIBC = "/tmp/my-project/upload/PPSA02929/PPSA02929-app0/sce_module/libc.prx"
NEW_LIBC = "/tmp/games/yatzi/sce_module/libc.prx"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def extract_strings(data, min_len=5, max_len=100):
    strings = []
    current = []
    for b in data:
        if 32 <= b < 127:
            current.append(chr(b))
        else:
            if len(current) >= min_len:
                strings.append("".join(current[:max_len]))
            current = []
    if len(current) >= min_len:
        strings.append("".join(current[:max_len]))
    return strings

def find_patterns(strings):
    pats = {"title_ids": [], "content_ids": [], "unity": [], "product": [], "il2cpp": [], "game": []}
    for s in strings:
        su = s.upper()
        if len(s) >= 5 and su[:4] in ("PPSA", "CUSA", "PCAS", "PCSA"):
            pats["title_ids"].append(s[:20])
        if "HP" in s and ("PPSA" in s or "CUSA" in s):
            pats["content_ids"].append(s[:60])
        if "unity" in s.lower() and "20" in s and "." in s:
            pats["unity"].append(s[:50])
        if "ProductName" in s or "Application.identifier" in s:
            pats["product"].append(s[:80])
        if "il2cpp" in s.lower() or "global-metadata" in s:
            pats["il2cpp"].append(s[:80])
        if any(kw in s.lower() for kw in ["yatzi", "yatzy", "yahtzee", "dreaming", "sarah", "harvest"]):
            pats["game"].append(s[:60])
    return pats

def analyze(path, label):
    print(f"\n{'='*78}")
    print(f"ANALYZING: {label}")
    print(f"Path: {path}")
    print(f"{'='*78}")
    if not os.path.exists(path):
        print("  FILE NOT FOUND")
        return None
    fsize = os.path.getsize(path)
    fhash = sha256(path)
    print(f"Size: {fsize:,} bytes")
    print(f"SHA256: {fhash}")
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] == b"\x7fELF":
        e_entry = struct.unpack_from("<Q", data, 0x18)[0]
        e_phnum = struct.unpack_from("<H", data, 0x38)[0]
        print(f"ELF: 64-bit LE, e_entry=0x{e_entry:X}, e_phnum={e_phnum}")
    if len(data) >= 4:
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic == 0xFAB11BAF:
            ver = struct.unpack_from("<i", data, 4)[0]
            print(f"IL2CPP Metadata: magic=0xFAB11BAF, version={ver}")
    search = data[:2*1024*1024] + data[-2*1024*1024:] if len(data) > 4*1024*1024 else data
    strings = extract_strings(search)
    pats = find_patterns(strings)
    print(f"Title IDs: {pats['title_ids'][:10]}")
    print(f"Content IDs: {pats['content_ids'][:5]}")
    print(f"Unity versions: {pats['unity'][:5]}")
    print(f"Product names: {pats['product'][:5]}")
    print(f"IL2CPP strings: {pats['il2cpp'][:5]}")
    print(f"Game strings: {pats['game'][:10]}")
    return {"size": fsize, "sha256": fhash, "pats": pats}

print("=" * 78)
print("EXP-061: Artifact Identity Audit")
print("=" * 78)

r = {}
r["old_eboot"] = analyze(OLD_EBOOT, "OLD eboot.bin (7.7MB)")
r["new_eboot"] = analyze(NEW_EBOOT, "NEW eboot.bin (32.7MB)")
r["prx"] = analyze(PRX, "Il2cppUserAssemblies.prx")
r["metadata"] = analyze(METADATA, "global-metadata.dat")
r["old_libc"] = analyze(OLD_LIBC, "OLD libc.prx")
r["new_libc"] = analyze(NEW_LIBC, "NEW libc.prx")

print(f"\n{'='*78}")
print("SHA256 COMPARISON")
print(f"{'='*78}")
old_h = r["old_eboot"]["sha256"] if r["old_eboot"] else "N/A"
new_h = r["new_eboot"]["sha256"] if r["new_eboot"] else "N/A"
print(f"Old eboot: {old_h}")
print(f"New eboot: {new_h}")
print(f"Match: {old_h == new_h}")
old_lc = r["old_libc"]["sha256"] if r["old_libc"] else "N/A"
new_lc = r["new_libc"]["sha256"] if r["new_libc"] else "N/A"
print(f"Old libc: {old_lc}")
print(f"New libc: {new_lc}")
print(f"Match: {old_lc == new_lc}")

print(f"\n{'='*78}")
print("IDENTITY COMPARISON")
print(f"{'='*78}")
ot = r["old_eboot"]["pats"]["title_ids"] if r["old_eboot"] else []
nt = r["new_eboot"]["pats"]["title_ids"] if r["new_eboot"] else []
print(f"Old eboot Title IDs: {ot}")
print(f"New eboot Title IDs: {nt}")
og = r["old_eboot"]["pats"]["game"] if r["old_eboot"] else []
ng = r["new_eboot"]["pats"]["game"] if r["new_eboot"] else []
print(f"Old eboot game strings: {og}")
print(f"New eboot game strings: {ng}")

# Check the dreaming-sarah directory
print(f"\n{'='*78}")
print("CHECK: /tmp/games/dreaming-sarah/ (was this the OLD eboot?)")
print(f"{'='*78}")
ds_eboot = "/tmp/games/dreaming-sarah/PPSA02929-app0/eboot.bin"
if os.path.exists(ds_eboot):
    ds_hash = sha256(ds_eboot)
    print(f"dreaming-sarah eboot.bin SHA256: {ds_hash}")
    print(f"Old upload eboot SHA256:         {old_h}")
    print(f"Same file: {ds_hash == old_h}")
    with open(ds_eboot, "rb") as f:
        ds_data = f.read()
    ds_strings = extract_strings(ds_data[:2*1024*1024])
    ds_pats = find_patterns(ds_strings)
    print(f"dreaming-sarah Title IDs: {ds_pats['title_ids'][:10]}")
    print(f"dreaming-sarah game strings: {ds_pats['game'][:10]}")

print(f"\n{'='*78}")
print("FINAL VERDICT")
print(f"{'='*78}")
if old_h == new_h:
    print("IDENTICAL FILES")
elif set(ot) & set(nt):
    print(f"SAME GAME (shared Title ID: {set(ot) & set(nt)})")
else:
    print("DIFFERENT FILES - checking if same game...")
    if og or ng:
        if set(og) & set(ng):
            print(f"SAME GAME (shared game strings: {set(og) & set(ng)})")
        else:
            print(f"POSSIBLY DIFFERENT GAMES")
            print(f"  Old game strings: {og}")
            print(f"  New game strings: {ng}")
