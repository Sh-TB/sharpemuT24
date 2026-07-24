// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

/// <summary>
/// Game-specific compatibility shims for private NIDs not in the public Aerolib catalog.
/// </summary>
public static class GameCompatExports
{
    [SysAbiExport(Nid = "zlqfTyrQSPk", ExportName = "sceKernelWaitOnAddressInternal", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libKernel")]
    public static int WaitOnAddressInternal(CpuContext ctx) { Thread.Sleep(1); return ctx.SetReturn(0); }

    [SysAbiExport(Nid = "dZGYu5wObJs", ExportName = "il2cpp_metadata_register_pool", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libil2cpp")]
    public static int Il2cppMetadataRegisterPool(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "35NoyMOtYpE", ExportName = "SetDataFolder", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libSceAppContent")]
    public static int SetDataFolder(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "M4YYbSFfJ8g", ExportName = "setenv", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int Setenv(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "-pnj3-7a6QA", ExportName = "unity_mono_set_user_malloc_mutex", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libunity")]
    public static int UnityMonoSetUserMallocMutex(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "cJ2Y4E-t258", ExportName = "il2cpp_api_register_symbols", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libil2cpp")]
    public static int Il2cppApiRegisterSymbols(CpuContext ctx) => ctx.SetReturn(0);

    // Arise NIDs — called in tight loop during rendering setup
    [SysAbiExport(Nid = "McaImWKXong", ExportName = "sceKernelMprotectInternal", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libKernel")]
    public static int KernelMprotectInternal(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "bRujIheWlB0", ExportName = "sceKernelLogWrite", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libKernel")]
    public static int KernelLogWrite(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "Cj+Fw5q1tUo", ExportName = "Cj_Fw5q1tUo_stub", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libKernel")]
    public static int KernelQueryMemoryProtection(CpuContext ctx) => ctx.SetReturn(0);

    // Harvest Days NIDs — now in MessengerCompatExports.cs with proper implementations
    // Kept only stubs not covered by MessengerCompatExports

    // Harvest Days: called 100K+ times in a tight loop — likely memchr/strchr/memcmp
    [SysAbiExport(Nid = "1D0H2KNjshE", ExportName = "1D0H2KNjshE_stub", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int HarvestMemOp1(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "hsi9drzHR2k", ExportName = "hsi9drzHR2k_stub", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int HarvestMemOp2(CpuContext ctx) => ctx.SetReturn(0);

    // Harvest Days: unresolved NIDs causing crashes
    [SysAbiExport(Nid = "AcslpN1jHR8", ExportName = "AcslpN1jHR8_stub", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libScePad")]
    public static int PadDeviceClassGetExtendedInfo(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "5TjaJwkLWxE", ExportName = "5TjaJwkLWxE_stub", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libScePad")]
    public static int HarvestStub5Tja(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "3BytPOQgVKc", ExportName = "3BytPOQgVKc_stub", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libKernel")]
    public static int HarvestStub3Byt(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "pztV4AF18iI", ExportName = "pztV4AF18iI_stub", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libKernel")]
    public static int HarvestStubPztV(CpuContext ctx) => ctx.SetReturn(0);

    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string, string> _envVars = new();
    [SysAbiExport(Nid = "VkqLPArfFdc", ExportName = "VkqLPArfFdc", Target = Generation.Gen5, LibraryName = "libKernel")]
    public static int VkqLPArfFdcStub(CpuContext ctx)
    {
        ctx[CpuRegister.Rax] = 0x0000000602000000ul;
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }
    [SysAbiExport(Nid = "GrQ9s4IrNaQ", ExportName = "sceAudioOutGetPortState", Target = Generation.Gen5, LibraryName = "libSceAudioOut")]
    public static int AudioOutGetPortStateStub(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "MM4IZSEYytQ", ExportName = "sceAgcDriverSetHsOffchipParam", Target = Generation.Gen5, LibraryName = "libSceAgcDriver")]
    public static int AgcDriverSetHsOffchipParamStub(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "XlNp7jzGiPo", ExportName = "sceAgcDriverSetTFRing", Target = Generation.Gen5, LibraryName = "libSceAgcDriver")]
    public static int AgcDriverSetTFRingStub(CpuContext ctx) => ctx.SetReturn(0);
}
