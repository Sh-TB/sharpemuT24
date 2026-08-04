# Dump Integrity Verification Report

## Date: 2026-07-31
## Status: PASS — Complete dump verified, all required files present

---

## Three Questions Before Debugging (Rule 027)

### 1. Do we have all required files? **YES**
### 2. Do we understand the data structures? **YES** (EXP-059 ground truth)
### 3. Are we tracing the real execution path? **PENDING** (resume from checklist)

---

## 1. File Inventory

### Total files: 26
### Total size: 153 MB

### File count by type:
| Extension | Count |
|-----------|-------|
| .prx | 8 |
| .bin | 1 |
| .dat | 5 |
| .sprx | 1 |
| .dds | 4 |
| .png | 2 |
| .ucp | 2 |
| .json | 1 |
| .esbak | 1 |
| other | 1 |

### Directory structure:
```
/tmp/games/yatzi/
├── eboot.bin (32.7 MB)
├── global-metadata.dat (10.7 MB) ← IL2CPP metadata, magic 0xFAB11BAF confirmed
├── sce_module/
│   ├── libc.prx (1.3 MB)
│   └── libSceNpCppWebApi.prx (8.0 MB)
├── Media/
│   ├── Modules/
│   │   ├── Il2cppUserAssemblies.prx (74.7 MB) ← THE MISSING FILE FROM EXP-035..058
│   │   └── PS5Util.prx (68 KB)
│   └── Plugins/
│       ├── PSNCore.prx (512 KB)
│       ├── PSNCommon.prx (73 KB)
│       ├── SaveData.prx (83 KB)
│       └── lib_burst_generated.prx (105 KB)
└── sce_sys/
    ├── about/right.sprx
    ├── ext_info.dat
    ├── icon0.dds, icon0.png
    ├── keystone
    ├── nptitle.dat
    ├── param.json
    ├── pic0.dds, pic0.png, pic1.dds, pic2.dds
    ├── trophy2/npbind.dat, trophy00.ucp
    └── uds/npbind.dat, uds00.ucp
```

---

## 2. SHA256 Hashes

| File | Size | SHA256 |
|------|------|--------|
| eboot.bin | 32,697,964 | d17fba4abc7858495c6f6e207b5c38961eec0c4639b04369f0c7b06866d80b6c |
| global-metadata.dat | 10,669,264 | 4c85fdec4efdb59534ab20af49615a36cbeef549f2f8de0431d78dbc5f21d918 |
| sce_module/libc.prx | 1,334,282 | 0848522a4532aca6e64f6208483f678633dac7bb65f08910f29716a7da5090d6 |
| sce_module/libSceNpCppWebApi.prx | 7,954,839 | 7fc1741678b0a0f1bb102163e6a92523e6d62dc3ff7de1955240c76899465cdb |
| Media/Modules/Il2cppUserAssemblies.prx | 74,726,132 | d73b3fc7236fb2ee68e979bc96f169ac5a3c26df4036dfdb9424f28643b9598d |
| Media/Modules/PS5Util.prx | 67,668 | 2f824c2a233c540d7220a4b1bc3b9c76e1a314267e47fe31740db5b93f582a3f |
| Media/Plugins/PSNCore.prx | 511,508 | 1abb460672700a3b2d565c7b71fb7daf1d2675e385cafb0da0184c1cb7e999a9 |
| Media/Plugins/PSNCommon.prx | 73,444 | 251a3acb31c9da810b1c182cc6ba8dcdb253aa103536fb578606c3feae32bd5f |
| Media/Plugins/SaveData.prx | 82,960 | e3d0da45dac18072b3beeaa3e44d1f47abb08b22168c5d98e69617dcbe543f77 |
| Media/Plugins/lib_burst_generated.prx | 104,736 | 9b2f6278e952e0cd2f9c0a89f3e7a0594221710194377f01f9947d4e414c8eb2 |

---

## 3. Comparison Against Previous Upload

| File | Previous Upload | Current Upload | Status |
|------|----------------|----------------|--------|
| eboot.bin | 7,778,142 bytes | 32,697,964 bytes | **DIFFERENT** (old was partial/truncated) |
| libc.prx | 1,284,392 bytes | 1,334,282 bytes | **DIFFERENT** (old was different version) |
| Il2cppUserAssemblies.prx | MISSING | 74,726,132 bytes | **NOW PRESENT** |
| global-metadata.dat | MISSING | 10,669,264 bytes | **NOW PRESENT** |
| PS5Util.prx | MISSING | 67,668 bytes | **NOW PRESENT** |
| PSNCore.prx | MISSING | 511,508 bytes | **NOW PRESENT** |
| PSNCommon.prx | MISSING | 73,444 bytes | **NOW PRESENT** |
| SaveData.prx | MISSING | 82,960 bytes | **NOW PRESENT** |
| lib_burst_generated.prx | MISSING | 104,736 bytes | **NOW PRESENT** |
| libSceNpCppWebApi.prx | MISSING | 7,954,839 bytes | **NOW PRESENT** |

**IMPORTANT CAVEAT**: The eboot.bin in this dump (32.7 MB) is DIFFERENT from the previous upload (7.7 MB). All address-based findings from EXP-035..058 were derived from the OLD eboot.bin and may not apply. The resume checklist must re-verify all key addresses against the new eboot.bin before proceeding.

---

## 4. IL2CPP-Specific Verification

### Il2cppUserAssemblies.prx
- **Path**: `/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx`
- **Size**: 74,726,132 bytes (74.7 MB)
- **SHA256**: d73b3fc7236fb2ee68e979bc96f169ac5a3c26df4036dfdb9424f28643b9598d
- **Status**: PRESENT ✓

### global-metadata.dat
- **Path**: `/tmp/games/yatzi/global-metadata.dat`
- **Size**: 10,669,264 bytes (10.7 MB)
- **SHA256**: 4c85fdec4efdb59534ab20af49615a36cbeef549f2f8de0431d78dbc5f21d918
- **Magic**: 0xFAB11BAF ✓ (confirmed at byte offset 0)
- **Version**: 29 (IL2CPP metadata format version)
- **Status**: PRESENT ✓

### Metadata magic search across all files
- **Found in**: `global-metadata.dat` (10,669,264 bytes)
- **Magic bytes**: AF 1B B1 FA (little-endian 0xFAB11BAF)
- **Confirmed at**: file offset 0

---

## 5. Verdict

**Do I actually have the complete dump?**

**YES.** The dump is now complete:

- **26 files** total, **153 MB** total size
- **8 .prx files** found (was 1 in previous upload)
- **Il2cppUserAssemblies.prx** present (74.7 MB) — was missing
- **global-metadata.dat** present (10.7 MB) — was missing
- **IL2CPP metadata magic 0xFAB11BAF** confirmed in global-metadata.dat
- **All required directories** present (sce_module/, Media/Modules/, Media/Plugins/)

**Evidence:**
- File count: 26 (was 10 in previous incomplete upload)
- Total size: 153 MB (was ~9 MB)
- SHA256 hashes generated for all 10 important files
- IL2CPP metadata magic confirmed at byte offset 0 of global-metadata.dat
- Metadata version 29 (Unity 2022.3.x compatible)

---

## Audit Script Result

```
VERDICT: PASS
All required files present, metadata magic found.
Ready for SharpEmu boot testing.
```

---

## Next Steps (per Resume Investigation Checklist)

1. ✅ Audit dump — PASS
2. ⬜ Build SharpEmu with current code (EXP-058 tracers still active)
3. ⬜ Run baseline boot test with new eboot.bin
4. ⬜ Verify metadata loader `0x804F04750` now succeeds (addresses may differ!)
5. ⬜ Check if call #7 loop body `0x804F238F0` fires (metadata loaded)
6. ⬜ Verify hash table population
7. ⬜ If boot progresses, target BOOT_STAGE_5
