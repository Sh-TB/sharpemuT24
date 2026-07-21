// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
using SharpEmu.HLE;
namespace SharpEmu.Libs.Kernel;
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
}
