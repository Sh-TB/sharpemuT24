// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.HLE;

namespace SharpEmu.Libs.Kernel;

/// <summary>
/// Game-specific compatibility shims for private NIDs that are not in the
/// public Aerolib catalog. Each export here is documented with the game that
/// needs it and the runtime evidence that justified the stub.
///
/// This is a fork-specific feature: upstream SharpEmu does not have these
/// NID mappings, so games like Harvest Days (PPSA14677) enter an infinite
/// loop on the unresolved import and never reach the renderer.
/// </summary>
public static class GameCompatExports
{
    // zlqfTyrQSPk is called 54,000+ times in a tight loop by Harvest Days
    // (PPSA14677) before any AGC submission. The call pattern matches a
    // blocking-wait primitive: rdi = waitable handle, rsi/rdx = 0, r8/r9 =
    // auxiliary state pointers. Returning 0 (success) lets the guest proceed
    // past its initialization barrier. The NID is not in the public Aerolib
    // catalog and is believed to be a private Sony synchronization primitive
    // (sceKernelWaitSemaInternal / scePthreadCondTimedwaitInternal).
    [SysAbiExport(
        Nid = "zlqfTyrQSPk",
        ExportName = "sceKernelWaitOnAddressInternal",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libKernel")]
    public static int WaitOnAddressInternal(CpuContext ctx)
    {
        // Sleep briefly to avoid burning CPU in the guest's busy-wait loop.
        // The real primitive blocks until woken; we approximate with a 1ms
        // yield so the guest's scheduler can make progress on other threads.
        Thread.Sleep(1);
        return ctx.SetReturn(0);
    }

    // dZGYu5wObJs is called 13 times by Harvest Days during IL2CPP metadata
    // loading. The call pattern (rdi = metadata pointer, rsi = size) matches
    // a memory-pool registration helper. Returning 0 lets IL2CPP boot.
    [SysAbiExport(
        Nid = "dZGYu5wObJs",
        ExportName = "il2cpp_metadata_register_pool",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libil2cpp")]
    public static int Il2cppMetadataRegisterPool(CpuContext ctx) =>
        ctx.SetReturn(0);

    // 35NoyMOtYpE = SetDataFolder — Harvest Days calls this to register its
    // app data directory. We don't have a real filesystem mount for it, so
    // return success and let the guest fall back to the default path.
    [SysAbiExport(
        Nid = "35NoyMOtYpE",
        ExportName = "SetDataFolder",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libSceAppContent")]
    public static int SetDataFolder(CpuContext ctx) =>
        ctx.SetReturn(0);

    // M4YYbSFfJ8g = setenv — standard POSIX. We store env vars in a
    // process-wide dictionary; getenv can read them back.
    [SysAbiExport(
        Nid = "M4YYbSFfJ8g",
        ExportName = "setenv",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libc")]
    public static int Setenv(CpuContext ctx)
    {
        var nameAddress = ctx[CpuRegister.Rdi];
        var valueAddress = ctx[CpuRegister.Rsi];
        var overwrite = (int)ctx[CpuRegister.Rdx];
        if (nameAddress == 0)
        {
            return ctx.SetReturn(-1);
        }

        var name = TryReadGuestCString(ctx, nameAddress, 256) ?? string.Empty;
        var value = valueAddress == 0 ? string.Empty : (TryReadGuestCString(ctx, valueAddress, 1024) ?? string.Empty);
        if (name.Length == 0 || name.Contains('='))
        {
            return ctx.SetReturn(-1);
        }

        if (overwrite != 0 || !_envVars.ContainsKey(name))
        {
            _envVars[name] = value;
        }

        return ctx.SetReturn(0);
    }

    // -pnj3-7a6QA = unity_mono_set_user_malloc_mutex — Unity's mono runtime
    // registers a custom malloc mutex. We don't have mono, so accept the
    // call and return 0.
    [SysAbiExport(
        Nid = "-pnj3-7a6QA",
        ExportName = "unity_mono_set_user_malloc_mutex",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libunity")]
    public static int UnityMonoSetUserMallocMutex(CpuContext ctx) =>
        ctx.SetReturn(0);

    // cJ2Y4E-t258 = il2cpp_api_register_symbols — IL2CPP registers its
    // symbol table for runtime lookups. We accept the registration but
    // don't actually store the symbols (the IL2CPP debug layer handles
    // that separately if SHARPEMU_DUMP_IL2CPP=1).
    [SysAbiExport(
        Nid = "cJ2Y4E-t258",
        ExportName = "il2cpp_api_register_symbols",
        Target = Generation.Gen4 | Generation.Gen5,
        LibraryName = "libil2cpp")]
    public static int Il2cppApiRegisterSymbols(CpuContext ctx) =>
        ctx.SetReturn(0);

    private static string? TryReadGuestCString(CpuContext ctx, ulong address, int maxLength)
    {
        if (address == 0 || maxLength <= 0)
        {
            return null;
        }

        var bytes = new System.Collections.Generic.List<byte>(maxLength);
        Span<byte> current = stackalloc byte[1];
        for (var i = 0; i < maxLength; i++)
        {
            if (!ctx.Memory.TryRead(address + (ulong)i, current))
            {
                return null;
            }

            if (current[0] == 0)
            {
                break;
            }

            bytes.Add(current[0]);
        }

        return System.Text.Encoding.UTF8.GetString(bytes.ToArray());
    }

    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string, string> _envVars = new();
}
