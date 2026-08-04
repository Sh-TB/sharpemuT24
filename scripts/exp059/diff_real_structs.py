#!/usr/bin/env python3
"""
EXP-059: Diff our struct guesses against REAL Unity 2022.3.5f1 header definitions.

This is the ground-truth comparison that should have been done 20 EXPs ago.
"""
import struct

PRX = "/tmp/games/yatzi/Media/Modules/Il2cppUserAssemblies.prx"
PRX_BASE = 0x804CD5000

# Real struct definitions from Unity 2022.3.5f1 header
# (nneonneo/Il2CppVersions/headers/2022.3.5f1.h)

REAL_IL2CPP_CODE_GEN_MODULE = [
    ("moduleName", "const char*", 8),
    ("methodPointerCount", "const uint32_t", 4),  # note: padded to 8 in 64-bit
    ("methodPointers", "const Il2CppMethodPointer*", 8),
    ("adjustorThunkCount", "const uint32_t", 4),
    ("adjustorThunks", "const Il2CppTokenAdjustorThunkPair*", 8),
    ("invokerIndices", "const int32_t*", 8),
    ("reversePInvokeWrapperCount", "const uint32_t", 4),
    ("reversePInvokeWrapperIndices", "const Il2CppTokenIndexMethodTuple*", 8),
    ("rgctxRangesCount", "const uint32_t", 4),
    ("rgctxRanges", "const Il2CppTokenRangePair*", 8),
    ("rgctxsCount", "const uint32_t", 4),
    ("rgctxs", "const Il2CppRGCTXDefinition*", 8),
    ("debuggerMetadata", "const Il2CppDebuggerMetadataRegistration*", 8),
    ("moduleInitializer", "const Il2CppMethodPointer*", 8),
    ("staticConstructorTypeIndices", "TypeDefinitionIndex*", 8),
    ("metadataRegistration", "const Il2CppMetadataRegistration*", 8),
    ("codeRegistaration", "const Il2CppCodeRegistration*", 8),  # note: typo in Unity source!
]

REAL_IL2CPP_CODE_REGISTRATION = [
    ("reversePInvokeWrapperCount", "uint32_t", 4),
    ("reversePInvokeWrappers", "const Il2CppMethodPointer*", 8),
    ("genericMethodPointersCount", "uint32_t", 4),
    ("genericMethodPointers", "const Il2CppMethodPointer*", 8),
    ("genericAdjustorThunks", "const Il2CppMethodPointer*", 8),
    ("invokerPointersCount", "uint32_t", 4),
    ("invokerPointers", "const InvokerMethod*", 8),
    ("unresolvedIndirectCallCount", "uint32_t", 4),
    ("unresolvedVirtualCallPointers", "const Il2CppMethodPointer*", 8),
    ("unresolvedInstanceCallPointers", "const Il2CppMethodPointer*", 8),
    ("unresolvedStaticCallPointers", "const Il2CppMethodPointer*", 8),
    ("interopDataCount", "uint32_t", 4),
    ("interopData", "Il2CppInteropData*", 8),
    ("windowsRuntimeFactoryCount", "uint32_t", 4),
    ("windowsRuntimeFactoryTable", "Il2CppWindowsRuntimeFactoryTableEntry*", 8),
    ("codeGenModulesCount", "uint32_t", 4),
    ("codeGenModules", "const Il2CppCodeGenModule**", 8),
]

REAL_IL2CPP_METADATA_REGISTRATION = [
    ("genericClassesCount", "int32_t", 4),
    ("genericClasses", "Il2CppGenericClass* const*", 8),
    ("genericInstsCount", "int32_t", 4),
    ("genericInsts", "const Il2CppGenericInst* const*", 8),
    ("genericMethodTableCount", "int32_t", 4),
    ("genericMethodTable", "const Il2CppGenericMethodFunctionsDefinitions*", 8),
    ("typesCount", "int32_t", 4),
    ("types", "const Il2CppType* const*", 8),
    ("methodSpecsCount", "int32_t", 4),
    ("methodSpecs", "const Il2CppMethodSpec*", 8),
    ("fieldOffsetsCount", "FieldIndex", 4),
    ("fieldOffsets", "const int32_t**", 8),
    ("typeDefinitionsSizesCount", "TypeDefinitionIndex", 4),
    ("typeDefinitionsSizes", "const Il2.dimensions**", 8),
    ("metadataUsagesCount", "const size_t", 8),
    ("metadataUsages", "void** const*", 8),
]

def compute_offsets(fields):
    """Compute byte offsets for each field, accounting for alignment."""
    offset = 0
    result = []
    for name, typ, size in fields:
        # Align to field size (8-byte fields align to 8, 4-byte to 4)
        if size == 8:
            offset = (offset + 7) & ~7
        elif size == 4:
            offset = (offset + 3) & ~3
        result.append((name, typ, size, offset))
        offset += size
    return result, offset

print("=" * 78)
print("REAL Unity 2022.3.5f1 struct definitions (ground truth)")
print("=" * 78)

print("\n--- Il2CppCodeGenModule ---")
fields, total = compute_offsets(REAL_IL2CPP_CODE_GEN_MODULE)
for name, typ, size, off in fields:
    print(f"  +0x{off:02X} ({size}B) {name}: {typ}")
print(f"  Total size: {total} bytes (0x{total:X})")

print("\n--- Il2CppCodeRegistration ---")
fields, total = compute_offsets(REAL_IL2CPP_CODE_REGISTRATION)
for name, typ, size, off in fields:
    print(f"  +0x{off:02X} ({size}B) {name}: {typ}")
print(f"  Total size: {total} bytes (0x{total:X})")

print("\n--- Il2CppMetadataRegistration ---")
fields, total = compute_offsets(REAL_IL2CPP_METADATA_REGISTRATION)
for name, typ, size, off in fields:
    print(f"  +0x{off:02X} ({size}B) {name}: {typ}")
print(f"  Total size: {total} bytes (0x{total:X})")

# Now compare with our runtime findings
print("\n" + "=" * 78)
print("DIFF: Our struct at 0x8086E9000 vs real Il2CppCodeRegistration")
print("=" * 78)

# Our findings from EXP-056:
our_codereg = {
    0x08: ("rodata ptr -> '22Il2CppExceptionWrapper'", 8),
    0x10: ("count=17", 4),
    0x18: ("data1 ptr", 8),
    0x20: ("count=103561", 4),
    0x28: ("data1 ptr (methodPointers?)", 8),
    0x30: ("data1 ptr (mixed array)", 8),
    0x38: ("count=18708", 4),
    0x40: ("data1 ptr", 8),
    0x48: ("count=3787", 4),
    0x50: ("data1 ptr", 8),
    0x58: ("data1 ptr", 8),
    0x60: ("data1 ptr", 8),
    0x68: ("count=889", 4),
    0x70: ("data2 ptr", 8),
    0x88: ("count=104", 4),
    0x90: ("data2 ptr", 8),
    0xA0: ("code ptr (inline methodPointers)", 8),
}

real_codereg_offsets = compute_offsets(REAL_IL2CPP_CODE_REGISTRATION)[0]
print("\n  Real CodeRegistration expects:")
for name, typ, size, off in real_codereg_offsets:
    print(f"    +0x{off:02X}: {name} ({typ})")

print("\n  Our struct at 0x8086E9000 has:")
for off, (desc, size) in sorted(our_codereg.items()):
    print(f"    +0x{off:02X}: {desc}")

print("\n  ANALYSIS:")
print("  - Real CodeRegistration starts with a uint32_t count at +0x00")
print("  - Our struct starts with a rodata ptr at +0x08 (type name string)")
print("  - MISMATCH: Our struct is NOT Il2CppCodeRegistration!")
print("  - Our struct matches Il2CppCodeGenModule better:")
print("    +0x00: moduleName (const char*) -> our +0x08 has rodata string ptr")
print("    Wait, the offsets don't match either...")

print("\n" + "=" * 78)
print("DIFF: Il2CppCodeGenModule vs our struct")
print("=" * 78)
real_codegen_offsets = compute_offsets(REAL_IL2CPP_CODE_GEN_MODULE)[0]
print("\n  Real Il2CppCodeGenModule expects:")
for name, typ, size, off in real_codegen_offsets:
    print(f"    +0x{off:02X}: {name} ({typ})")

print("\n  Our struct at 0x8086E9000:")
print("    +0x00: 0x0 (reserved?)")
print("    +0x08: rodata ptr -> '22Il2CppExceptionWrapper' (type name)")
print("    +0x10: count=17")
print("    +0x18: data1 ptr")
print("    +0x20: count=103561")
print("    +0x28: data1 ptr")
print("    +0x30: data1 ptr (mixed)")

print("\n  ANALYSIS:")
print("  Il2CppCodeGenModule+0x00 = moduleName (const char*)")
print("  Our struct +0x08 = rodata string ptr (type name)")
print("  If our struct starts at +0x08, then moduleName is at +0x08!")
print("  That means our struct starts 8 bytes BEFORE 0x8086E9000,")
print("  OR there's an 8-byte header before the CodeGenModule.")
print()
print("  Let me check: Il2CppCodeGenModule field order:")
print("    +0x00: moduleName")
print("    +0x08: methodPointerCount (uint32, padded to 8)")
print("    +0x10: methodPointers")
print("    +0x18: adjustorThunkCount")
print("    +0x20: adjustorThunks")
print("    +0x28: invokerIndices")
print("    +0x30: reversePInvokeWrapperCount")
print("    +0x38: reversePInvokeWrapperIndices")
print("    +0x40: rgctxRangesCount")
print("    +0x48: rgctxRanges")
print("    +0x50: rgctxsCount")
print("    +0x58: rgctxs")
print("    +0x60: debuggerMetadata")
print("    +0x68: moduleInitializer")
print("    +0x70: staticConstructorTypeIndices")
print("    +0x78: metadataRegistration <- MetaReg pointer!")
print("    +0x80: codeRegistaration <- CodeReg pointer!")
print()
print("  CRITICAL: If our struct at 0x8086E9000 is Il2CppCodeGenModule,")
print("  then +0x78 should be MetaReg and +0x80 should be CodeReg!")
print("  But our struct at +0x78 has count=12,981 and +0x80 has types[] ptr.")
print("  This doesn't match Il2CppCodeGenModule either.")
print()
print("  CONCLUSION: Our struct at 0x8086E9000 is NEITHER Il2CppCodeRegistration")
print("  NOR Il2CppCodeGenModule. It might be a Unity 2022 PS5-specific variant")
print("  or a completely different struct. The type name at +0x08 ('22Il2CppExceptionWrapper')")
print("  suggests it's a type/metadata-related struct but not the registration struct.")
