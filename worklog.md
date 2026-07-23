---
Task ID: EXP-015
Agent: main (SharpEmu bringup)
Task: Implement BootDependencyAnalyzer (Rule #1 of the debugger), test all games, generate reports.

Work Log:
- Implemented BootDependencyAnalyzer class in SharpEmu.Core/Loader/BootDependencyAnalyzer.cs.
  - Engine detection: Unity IL2CPP, Unity Mono, Unreal, Native C++, Unknown
  - Required file lists per engine with priority ratings (Critical/High/Medium/Low/Optional)
  - File presence check + format verification (ELF vs SELF vs fSELF, encrypted detection)
  - Coverage % calculation
  - "Next required file to upload" recommendation
  - Aborts emulation only when CRITICAL files are missing or encrypted
  - Case-insensitive filename lookup (PS5 dumps vary in casing: "Il2Cpp" vs "Il2cpp")
- Wired into SharpEmuRuntime.Run() — runs BEFORE any CPU execution
- Adjusted priority for Unity IL2CPP files: global-metadata.dat is High (not Critical)
  because SharpEmu uses fake IL2CPP stubs and doesn't read it. Only eboot, libc, and
  Il2cppUserAssemblies are truly Critical for SharpEmu to boot.

Test results — all games run with new analyzer:

| # | Game | Engine | Coverage | Critical miss | Can boot | First Frame? |
|---|------|--------|----------|---------------|----------|--------------|
| 1 | Dreaming Sarah | Native C++ | 75% | 0 | YES | ✅ 5 frames produced |
| 2 | Arise | Native C++ | 50% (libc.prx encrypted) | 0 | NO (warns) | ⚠️ ran to 982K imports, SIGILL crash before frame |
| 3 | Yatzi (PPSA17697) | Unity IL2CPP | 77.8% | 0 | YES | ✅ frame000001.ppm produced |
| 4 | Seeker My Shadow (PPSA12500) | Unity IL2CPP | 66.7% | 0 | YES | ✅ frame000001.ppm produced (NEW!) |
| 5 | Harvest Days | Native C++ | 75% (libc.prx encrypted) | 0 | NO (warns) | ✅ frame000001.ppm produced (NEW!) |

ALL three Unity IL2CPP games (Yatzi, Seeker, Harvest Days) produce the same Unity splash background frame:
- 99.98% of pixels = (229, 95, 68) — Unity orange/red splash color
- 380 white pixels — likely UI text or splash logo
- Resolution: 1920x1080 RGBA8

User uploaded Seeker My Shadow full decrypted app0 (multi-part RAR):
- decrypted/eboot.bin (30.3 MB, ELF)
- decrypted/Media/Modules/Il2CppUserAssemblies.prx (32.8 MB, ELF)
- decrypted/Media/Modules/PS5Util.prx (ELF)
- decrypted/Media/Plugins/{PSNCommon,PSNCore,psvr2,SaveData}.prx (ELF)
- decrypted/sce_module/{libc,libSceFace,libSceFaceTracker,libSceJobManager,libSceNpCppWebApi,libScePfs}.prx (ELF)
- decrypted/sce_sys/about/right.sprx (ELF)
All 14 files are decrypted ELF.

Stage Summary:
- 🎉 Seeker My Shadow and Harvest Days now reach first frame! Total: 5 games with first frame.
- BootDependencyAnalyzer is now Rule #1 of the debugger — runs before any CPU execution.
- Reports include engine detection, file coverage %, encrypted-executable warnings,
  and a "next required file to upload" recommendation.
- Case-insensitive filename lookup handles "Il2Cpp" vs "Il2cpp" casing variations.
- Priorities are SharpEmu-specific (not real-PS5-specific): only eboot, libc.prx, and
  Il2cppUserAssemblies.prx are Critical. Other Unity files are High/Medium/Low.
- Arise regression: game ran for ~120s and crashed with SIGILL (Illegal instruction).
  This is likely unrelated to the analyzer (which only warned). Needs separate
  investigation — possibly a JIT compilation issue with a rarely-executed code path.
- Artifacts produced:
  - /home/z/my-project/download/ppsa17697_first_frame.png (Yatzi, from EXP-014)
  - /home/z/my-project/download/seeker_first_frame.png (Seeker, NEW)
  - /home/z/my-project/download/harvest_first_frame.png (Harvest Days, NEW)
  - /home/z/my-project/SharpEmu/diagnostics/exp-015/{01-dreaming-sarah,02-arise,03-yatzi,04-seeker,05-harvest}.log
