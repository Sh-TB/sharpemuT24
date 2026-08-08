// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

/// <summary>
/// C11 synchronization primitives (_Mtx_*, _Cnd_*) and related exports.
/// </summary>
public static class C11SyncExports
{
    [SysAbiExport(Nid = "YaHc3GS7y7g", ExportName = "_Mtx_init", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int MtxInit(CpuContext ctx) => KernelPthreadCompatExports.PthreadMutexInitCore(ctx, ctx[CpuRegister.Rdi], attrAddress: 0);

    [SysAbiExport(Nid = "iS4aWbUonl0", ExportName = "_Mtx_lock", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int MtxLock(CpuContext ctx) => KernelPthreadCompatExports.PthreadMutexLockCore(ctx, ctx[CpuRegister.Rdi], tryOnly: false);

    [SysAbiExport(Nid = "gTuXQwP9rrs", ExportName = "_Mtx_unlock", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int MtxUnlock(CpuContext ctx) => KernelPthreadCompatExports.PthreadMutexUnlockCore(ctx, ctx[CpuRegister.Rdi], requireOwner: true);

    [SysAbiExport(Nid = "SreZybSRWpU", ExportName = "_Cnd_init", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int CndInit(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "VPbJwTCgME0", ExportName = "srand", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int Srand(CpuContext ctx) => ctx.SetReturn(0);
}
