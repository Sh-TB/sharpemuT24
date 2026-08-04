# Resume Investigation Checklist — Run When Complete Game Dump Arrives

## Prerequisites (verify BEFORE touching SharpEmu)

```bash
# 1. Run the audit script on the new dump
python3 scripts/audit_game_dump.py /path/to/new/game/root

# Expected: PASS (all required files present, metadata magic found)
# If FAIL: stop here, the dump is still incomplete.
```

## Ground-Truth Struct Layouts (from EXP-059, Unity 2022.3.5f1 header)

Use these instead of inferring from relocation patterns:

### Il2CppCodeGenModule (at 0x8086E9000 in Yatzi)
```
+0x00: moduleName (const char*)
+0x08: methodPointerCount (uint32_t, padded to 8)
+0x10: methodPointers (const Il2CppMethodPointer*)
+0x18: adjustorThunkCount (uint32_t)
+0x20: adjustorThunks (ptr)
+0x28: invokerIndices (ptr)
+0x30: reversePInvokeWrapperCount (uint32_t)
+0x38: reversePInvokeWrapperIndices (ptr)
+0x40: rgctxRangesCount (uint32_t)
+0x48: rgctxRanges (ptr)
+0x50: rgctxsCount (uint32_t)
+0x58: rgctxs (ptr)
+0x60: debuggerMetadata (ptr)
+0x68: moduleInitializer (ptr)
+0x70: staticConstructorTypeIndices (ptr)
+0x78: metadataRegistration (const Il2CppMetadataRegistration*)  ← MetaReg ptr
+0x80: codeRegistaration (const Il2CppCodeRegistration*)         ← CodeReg ptr (Unity's typo)
Total: 0x88 bytes
```

### Il2CppMetadataRegistration (PS5 variant at 0x80885C580)
PS5 adds 3 code pointers at the start, then standard layout:
```
+0x00: code ptr (reverse P/Invoke wrapper)
+0x08: code ptr (reverse P/Invoke wrapper)
+0x10: code ptr (reverse P/Invoke wrapper)
--- standard Il2CppMetadataRegistration starts here (+0x18) ---
+0x18: genericClassesCount (int32_t) = 12,270
+0x20: genericClasses (ptr)
+0x28: genericInstsCount (int32_t) = 8,019
+0x30: genericInsts (ptr)
+0x38: genericMethodTableCount (int32_t) = 103,581
+0x40: genericMethodTable (ptr)
+0x48: typesCount (int32_t) = 40,310  ← NOTE: this matches metadataUsagesCount
+0x50: types (ptr)                     ← should point to types[] array
+0x58: methodSpecsCount (int32_t) = 122,482
+0x60: methodSpecs (ptr)
+0x68: fieldOffsetsCount (int32_t) = 12,981
+0x70: fieldOffsets (ptr)
+0x78: typeDefinitionsSizesCount (int32_t) = 12,981
+0x80: typeDefinitionsSizes (ptr)      ← we found types[] here, needs re-verification
+0x88: metadataUsagesCount (size_t)
+0x90: metadataUsages (ptr)
```

### Il2CppCodeRegistration (location TBD — check Il2CodeGenModule+0x80)
```
+0x00: reversePInvokeWrapperCount (uint32_t)
+0x08: reversePInvokeWrappers (ptr)
+0x10: genericMethodPointersCount (uint32_t)
+0x18: genericMethodPointers (ptr)
...
+0x78: codeGenModulesCount (uint32_t)
+0x80: codeGenModules (const Il2CppCodeGenModule**)  ← array of module ptrs
Total: 0x88 bytes
```

## Step-by-Step Resume Plan

### Step 1: Verify PRX loads correctly
```bash
# Copy complete game dump to /tmp/games/yatzi/
# Ensure Media/Modules/Il2cppUserAssemblies.prx is present
# Run SharpEmu with baseline (no stub):
SHARPEMU_SEMA_FAST_PATH=0 ./scripts/run-sharpemu.sh \
  dotnet artifacts/bin/Debug/net10.0/linux-x64/SharpEmu.dll \
  --cpu-engine=native /tmp/games/yatzi/eboot.bin
```

### Step 2: Check if metadata loader now succeeds
Watch for these in the log:
- `[EXP058-CALL7-ENTER]` — call #7 entered (should still fire)
- `[EXP058-LOOP-ITER]` — loop body hit (should NOW fire if metadata loads)
- `[EXP058-ARRAYPROC-ENTER]` — array processor hit (should NOW fire)
- Hash table populated count > 0 after call #7

If loop body fires: metadata loaded successfully → proceed to Step 3.
If loop body still 0 hits: metadata loader still failing → trace 0x804F04750
to find exact file path being probed (using INT3 at its entry).

### Step 3: Verify hash table population
After call #7 completes, check:
- `[0x801EF7610]` hash table has populated entries (>0)
- `[0x801E51240]` metadata global is non-NULL
- Wrapper `0x800805AE0` was called (EXP053 tracer should show hits)

### Step 4: Verify crash chain clears
If hash table is populated:
- The init function's lookups at 0x8013EEFE7 should return non-NULL
- The callback at 0x80134FA00 should find valid metadata
- The crash function 0x80135DDD0 should read valid data at [rax+0x98]
- SIGSEGV cascade should not occur

### Step 5: If boot progresses past il2cpp_init
- Remove EXP-048 callback stub (set SHARPEMU_EXP048_STUB=0)
- Check for BOOT_STAGE_5
- Document any new crash (use ground-truth structs, don't re-infer)

### Step 6: If metadata loader still fails (Step 2 negative)
The metadata might be at a non-standard path. Trace the loader:
1. INT3 at `0x804F04750` — log rdi/rsi, read the "Metadata" string context
2. INT3 at `0x804F86250` — log the path it builds (path resolution)
3. INT3 at `0x804ECC2F0` — log the file I/O call and its return value
4. Check SharpEmu's file I/O HLE logs for the exact path being probed
5. If path is wrong: fix SharpEmu's path mapping
6. If path is right but file not found: check PFS/filesystem HLE

## Key Addresses (Yatzi, may shift with different PRX load address)

| Address | What | Notes |
|---------|------|-------|
| 0x8086E9000 | Il2CppCodeGenModule | Was misidentified as CodeReg in EXP-054..058 |
| 0x8086E9078 | Il2CodeGenModule.metadataRegistration | Should point to MetaReg |
| 0x8086E9080 | Il2CodeGenModule.codeRegistaration | Should point to real CodeReg |
| 0x80885C580 | Il2CppMetadataRegistration (PS5 variant) | 3 extra code ptrs at start |
| 0x801EF7610 | Hash table pointer (eboot BSS) | Allocated by 0x8007F90A0 |
| 0x801E51240 | Metadata global (eboot BSS) | NULL when hash table empty |
| 0x804F04750 | Metadata loader (PRX code) | Fails when file missing |
| 0x804F713A0 | Guard function (PRX code) | Returns 0 when loader fails |
| 0x804F23320 | Call #7 / consumer (PRX code) | Skips loops when guard returns 0 |
| 0x804ED85D0 | il2cpp_init (PRX code) | 44-byte thunk to real_init |
| 0x804F04BA0 | real_init (PRX code) | Actual init logic |

## What NOT to repeat
- Do NOT re-infer struct layouts from relocations — use the layouts above
- Do NOT search for CodeReg/MetaReg co-occurrence via LEA — they're linked via Il2CodeGenModule struct fields
- Do NOT patch individual NULL crashes — they're symptoms of the missing metadata
- Do NOT NOP conditional jumps — they're correct safeguards
- Do NOT fake metadata buffers — changes control flow and exposes more NULLs
