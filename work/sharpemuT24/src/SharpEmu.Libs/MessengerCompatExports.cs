// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.HLE;
using SharpEmu.Libs.LibcStdio;

namespace SharpEmu.Libs.Messenger;

/// <summary>Unity/libc compatibility shims from upstream PR #542 (The Messenger).</summary>
public static class MessengerCompatExports
{
    [SysAbiExport(Nid = "wLlFkwG9UcQ", ExportName = "time", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int Time(CpuContext ctx)
    {
        var seconds = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var output = ctx[CpuRegister.Rdi];
        if (output != 0 && !ctx.TryWriteUInt64(output, unchecked((ulong)seconds)))
        {
            ctx[CpuRegister.Rax] = 0;
            return (int)OrbisGen2Result.ORBIS_GEN2_ERROR_MEMORY_FAULT;
        }
        ctx[CpuRegister.Rax] = unchecked((ulong)seconds);
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }

    [SysAbiExport(Nid = "-P6FNMzk2Kc", ExportName = "cosf", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int Cosf(CpuContext ctx)
    {
        var value = BitConverter.Int32BitsToSingle(unchecked((int)ctx[CpuRegister.Rdi]));
        ctx[CpuRegister.Rax] = unchecked((ulong)BitConverter.SingleToInt32Bits(MathF.Cos(value)));
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }

    [SysAbiExport(Nid = "YQ0navp+YIc", ExportName = "puts", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int Puts(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "KuOuD58hqn4", ExportName = "malloc_stats_fast", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int MallocStatsFast(CpuContext ctx) => ctx.SetReturn(0);

    [SysAbiExport(Nid = "1uJgoVq3bQU", ExportName = "_Getptolower", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int GetPtolower(CpuContext ctx)
    {
        // Return a pointer to a static lowercase conversion table
        ctx[CpuRegister.Rax] = unchecked((ulong)LibcStdioExports.EnsureCtypeLowerTable());
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }

    [SysAbiExport(Nid = "rcQCUr0EaRU", ExportName = "_Getptoupper", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int GetPtoupper(CpuContext ctx)
    {
        ctx[CpuRegister.Rax] = unchecked((ulong)LibcStdioExports.EnsureCtypeUpperTable());
        return (int)OrbisGen2Result.ORBIS_GEN2_OK;
    }

    [SysAbiExport(Nid = "PsrRUg671K0", ExportName = "__cxa_increment_exception_refcount", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libc")]
    public static int CxaIncrementExceptionRefcount(CpuContext ctx) => ctx.SetReturn(0);
}
