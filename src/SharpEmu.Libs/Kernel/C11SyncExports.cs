// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
using SharpEmu.HLE;
namespace SharpEmu.Libs.Kernel;
public static class C11SyncExports
{
    [SysAbiExport(Nid = "YaHc3GS7y7g", ExportName = "_Mtx_init", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int MtxInit(CpuContext ctx) { var a = ctx[CpuRegister.Rdi]; var t = (int)ctx[CpuRegister.Rsi]; var r = KernelPthreadCompatExports.PthreadMutexInitCore(ctx, a, 0); return r != 0 ? r : ctx.SetReturn(0); }
    [SysAbiExport(Nid = "iS4aWbUonl0", ExportName = "_Mtx_lock", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int MtxLock(CpuContext ctx) => KernelPthreadCompatExports.PthreadMutexLockCore(ctx, ctx[CpuRegister.Rdi], tryOnly: false);
    [SysAbiExport(Nid = "gTuXQwP9rrs", ExportName = "_Mtx_unlock", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int MtxUnlock(CpuContext ctx) => KernelPthreadCompatExports.PthreadMutexUnlockCore(ctx, ctx[CpuRegister.Rdi], requireOwner: true);
    [SysAbiExport(Nid = "SreZybSRWpU", ExportName = "_Cnd_init", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int CndInit(CpuContext ctx) => KernelPthreadCompatExports.PthreadCondInitCore(ctx, ctx[CpuRegister.Rdi]);
    [SysAbiExport(Nid = "pztV4AF18iI", ExportName = "sincosf", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libm")]
    public static int Sincosf(CpuContext ctx) { var x = BitConverter.Int32BitsToSingle((int)ctx[CpuRegister.Rdi]); var s = ctx[CpuRegister.Rsi]; var c = ctx[CpuRegister.Rdx]; Span<byte> sb = stackalloc byte[4]; Span<byte> cb = stackalloc byte[4]; System.Buffers.Binary.BinaryPrimitives.WriteSingleLittleEndian(sb, MathF.Sin(x)); System.Buffers.Binary.BinaryPrimitives.WriteSingleLittleEndian(cb, MathF.Cos(x)); if (s != 0) ctx.Memory.TryWrite(s, sb); if (c != 0) ctx.Memory.TryWrite(c, cb); return ctx.SetReturn(0); }
    [SysAbiExport(Nid = "VPbJwTCgME0", ExportName = "srand", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int Srand(CpuContext ctx) { lock(_g) { _r = new System.Random(unchecked((int)(uint)ctx[CpuRegister.Rdi])); } return ctx.SetReturn(0); }
    [SysAbiExport(Nid = "bRujIheWlB0", ExportName = "_ZSt14_Throw_C_errori", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int ThrowCError(CpuContext ctx) { Console.Error.WriteLine($"[LOADER][INFO] _ZSt14_Throw_C_errori errno={(int)ctx[CpuRegister.Rdi]} (suppressed)"); return ctx.SetReturn(0); }
    private static readonly object _g = new(); private static System.Random _r = new();
}
