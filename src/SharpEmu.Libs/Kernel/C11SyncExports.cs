// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

/// <summary>
/// C11 / C++ stdlib synchronization primitives used by UE5 titles and other
/// games that link against the libc++ _Mtx_* / _Cnd_* shims. These map onto
/// the existing pthread_mutex_t / pthread_cond_t infrastructure so the guest
/// gets real cross-thread synchronization rather than a stub that returns
/// without locking — the previous behaviour caused races that crashed Arise
/// (PPSA06328) when its job scheduler wrote to a still-owned GPU memory
/// window at 0x1FE000000.
/// </summary>
public static class C11SyncExports
{
    [SysAbiExport(
        Nid = "YaHc3GS7y7g",
        ExportName = "_Mtx_init",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int MtxInit(CpuContext ctx)
    {
        var mutexAddress = ctx[CpuRegister.Rdi];
        var type = (int)ctx[CpuRegister.Rsi];
        var result = KernelPthreadCompatExports.PthreadMutexInitCore(
            ctx,
            mutexAddress,
            attrAddress: 0);
        if (result != 0)
        {
            return result;
        }

        // Patch the type slot if a non-default type was requested. The mutex
        // state layout is owned by KernelPthreadCompatExports; we mirror the
        // type encoding used by PthreadMutexattrSettypeCore.
        if (type != 0 && mutexAddress != 0)
        {
            const int MutexTypeOffset = 0x08;
            Span<byte> typeBytes = stackalloc byte[4];
            System.Buffers.Binary.BinaryPrimitives.WriteInt32LittleEndian(typeBytes, type);
            ctx.Memory.TryWrite(mutexAddress + MutexTypeOffset, typeBytes);
        }

        return ctx.SetReturn(0);
    }

    [SysAbiExport(
        Nid = "iS4aWbUonl0",
        ExportName = "_Mtx_lock",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int MtxLock(CpuContext ctx) =>
        KernelPthreadCompatExports.PthreadMutexLockCore(
            ctx,
            ctx[CpuRegister.Rdi],
            tryOnly: false);

    [SysAbiExport(
        Nid = "gTuXQwP9rrs",
        ExportName = "_Mtx_unlock",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int MtxUnlock(CpuContext ctx) =>
        KernelPthreadCompatExports.PthreadMutexUnlockCore(
            ctx,
            ctx[CpuRegister.Rdi],
            requireOwner: true);

    [SysAbiExport(
        Nid = "SreZybSRWpU",
        ExportName = "_Cnd_init",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int CndInit(CpuContext ctx) =>
        KernelPthreadCompatExports.PthreadCondInitCore(ctx, ctx[CpuRegister.Rdi]);

    [SysAbiExport(
        Nid = "pztV4AF18iI",
        ExportName = "sincosf",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libm")]
    public static int Sincosf(CpuContext ctx)
    {
        // void sincosf(float x, float* sin_x, float* cos_x)
        // RDI = x (passed as float in low 32 bits), RSI = sin*, RDX = cos*
        var xBits = (uint)ctx[CpuRegister.Rdi];
        var x = BitConverter.Int32BitsToSingle((int)xBits);
        var sinAddress = ctx[CpuRegister.Rsi];
        var cosAddress = ctx[CpuRegister.Rdx];
        Span<byte> sinBytes = stackalloc byte[4];
        Span<byte> cosBytes = stackalloc byte[4];
        System.Buffers.Binary.BinaryPrimitives.WriteSingleLittleEndian(sinBytes, MathF.Sin(x));
        System.Buffers.Binary.BinaryPrimitives.WriteSingleLittleEndian(cosBytes, MathF.Cos(x));
        if (sinAddress != 0)
        {
            ctx.Memory.TryWrite(sinAddress, sinBytes);
        }

        if (cosAddress != 0)
        {
            ctx.Memory.TryWrite(cosAddress, cosBytes);
        }

        return ctx.SetReturn(0);
    }

    [SysAbiExport(
        Nid = "VPbJwTCgME0",
        ExportName = "srand",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int Srand(CpuContext ctx)
    {
        var seed = (uint)ctx[CpuRegister.Rdi];
        lock (_randGate)
        {
            _rand = new System.Random(unchecked((int)seed));
        }

        return ctx.SetReturn(0);
    }

    [SysAbiExport(
        Nid = "bRujIheWlB0",
        ExportName = "_ZSt14_Throw_C_errori",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int ThrowCError(CpuContext ctx)
    {
        // libstdc++'s _ZSt14_Throw_C_errori is the C++ runtime helper invoked
        // when a pthread_* / sem_* call returns an unexpected errno. UE5 hits
        // this when mutex init fails silently. Returning 0 (no throw) lets
        // the caller fall through to its own error handling rather than
        // unwinding into a C++ exception that the HLE layer cannot deliver.
        var errno = (int)ctx[CpuRegister.Rdi];
        Console.Error.WriteLine(
            $"[LOADER][INFO] _ZSt14_Throw_C_errori errno={errno} (suppressed; returning 0)");
        return ctx.SetReturn(0);
    }

    private static readonly object _randGate = new();
    private static System.Random _rand = new();
}
