// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

/// <summary>
/// Game-specific compatibility shims for private NIDs not in the public Aerolib catalog.
///
/// IMPORTANT: Do NOT add NID stubs without verifying they are actually called by the
/// target game. The Windows upstream log for Yatzi (PPSA17697-20260721-152128.log)
/// confirmed that 1D0H2KNjshE and hsi9drzHR2k are Harvest Days only — they had 0
/// calls on Yatzi Windows but 59+21 calls on our fork due to false stubs, which
/// corrupted the IL2CPP runtime state and caused the bootstrap deadlock.
///
/// Rule: If upstream doesn't resolve an NID and the game runs better without it,
/// do NOT stub it. Unresolved NIDs returning NULL is safer than fake success.
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

    // REMOVED: AcslpN1jHR8, 5TjaJwkLWxE, 3BytPOQgVKc, pztV4AF18iI
    // These were Harvest Days-specific stubs.

    // 1D0H2KNjshE and hsi9drzHR2k — IL2CPP bootstrap investigation.
    // These NIDs are NOT in any HLE export or Aerolib catalog.
    // Without these exports, they resolve to native return-zero stubs that
    // bypass managed dispatch entirely (ImportDispatchGatewayManaged never fires).
    // We add them here as HLE exports WITH logging so we can capture their
    // arguments and return address to classify their semantic role.
    [SysAbiExport(Nid = "1D0H2KNjshE", ExportName = "1D0H2KNjshE_traced", Target = Generation.Gen5, LibraryName = "libc")]
    public static int NidTrace_1D0H2KNjshE(CpuContext ctx)
    {
        Console.Error.WriteLine(
            $"[NID-TRACE] 1D0H2KNjshE rdi=0x{ctx[CpuRegister.Rdi]:X16} rsi=0x{ctx[CpuRegister.Rsi]:X16} " +
            $"rdx=0x{ctx[CpuRegister.Rdx]:X16} rcx=0x{ctx[CpuRegister.Rcx]:X16} " +
            $"r8=0x{ctx[CpuRegister.R8]:X16} r9=0x{ctx[CpuRegister.R9]:X16} " +
            $"ret=0x{ctx[CpuRegister.Rsp]:X16} thread=0x{GuestThreadExecution.CurrentGuestThreadHandle:X16}");
        return ctx.SetReturn(0);
    }

    [SysAbiExport(Nid = "hsi9drzHR2k", ExportName = "hsi9drzHR2k_traced", Target = Generation.Gen5, LibraryName = "libc")]
    public static int NidTrace_hsi9drzHR2k(CpuContext ctx)
    {
        Console.Error.WriteLine(
            $"[NID-TRACE] hsi9drzHR2k rdi=0x{ctx[CpuRegister.Rdi]:X16} rsi=0x{ctx[CpuRegister.Rsi]:X16} " +
            $"rdx=0x{ctx[CpuRegister.Rdx]:X16} rcx=0x{ctx[CpuRegister.Rcx]:X16} " +
            $"r8=0x{ctx[CpuRegister.R8]:X16} r9=0x{ctx[CpuRegister.R9]:X16} " +
            $"ret=0x{ctx[CpuRegister.Rsp]:X16} thread=0x{GuestThreadExecution.CurrentGuestThreadHandle:X16}");
        return ctx.SetReturn(0);
    }

    // VkqLPArfFdc — 0 calls on Windows upstream. Kept as harmless stub.
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





    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string, string> _envVars = new();
}
