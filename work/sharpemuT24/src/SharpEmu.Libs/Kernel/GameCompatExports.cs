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
    public static int UnityMonoSetUserMallocMutex(CpuContext ctx)
    {
        ResolverTraceInstrumentation.ComparePostWrapper(ctx);
        FlagWatchInstrumentation.DumpResolverNodes(ctx, "post-wrapper (Import#2084)");
        IndependentBSTWalker.DumpFullBST(ctx, "post-wrapper (Import#2084)");
        return ctx.SetReturn(0);
    }

    // REMOVED HLE stub for cJ2Y4E-t258 (il2cpp_api_register_symbols)
    // The real PRX function at 0x804ED3AE0 will be direct-bridged instead.
    // This allows the 239 IL2CPP symbol nodes to be registered in the resolver list.
    // See evidence_v3/report/verified_facts.md for details.
    /*
    [SysAbiExport(Nid = "cJ2Y4E-t258", ExportName = "il2cpp_api_register_symbols", Target = Generation.Gen4 | Generation.Gen5, LibraryName = "libil2cpp")]
    public static int Il2cppApiRegisterSymbols(CpuContext ctx)
    {
        FlagWatchInstrumentation.DumpResolverNodes(ctx, "pre-wrapper (Import#2083)");
        ResolverTraceInstrumentation.TakePreWrapperSnapshot(ctx);
        return ctx.SetReturn(0);
    }
    */

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
    //
    // TWO EXPERIMENTAL KNOBS (set either or both via env var):
    //   SHARPEMU_NID_RETURN_NONZERO=1
    //       → stubs return R8 value (or 1 if R8==0) instead of 0.
    //         Cheap test to determine if "loop exit" depends on non-zero return.
    //   SHARPEMU_NID_CALLER_MAP=1
    //       → log "[NID-CALLER]" line with module+offset for the actual return
    //         address (read from [RSP]). Off by default to reduce noise.
    //
    // Logging is rate-limited to 1 line per 200ms per NID to keep the log
    // readable while the main thread is in its busy-wait loop.
    private static long _nextLog1D0;
    private static long _nextLogHsi9;
    private static long _nextLog1D0_R8;
    private static long _nextLogHsi9_R8;
    private const long LogIntervalTicks = 200 * TimeSpan.TicksPerMillisecond;
    private const long R8ChangeLogIntervalTicks = 50 * TimeSpan.TicksPerMillisecond;

    // Counter snapshot every 1 second for both NIDs — lets us observe if the
    // busy-wait loop is broken (call rate drops to 0).
    private static long _calls1D0;
    private static long _callsHsi9;
    private static long _nextCounterDump;
    private const long CounterDumpIntervalTicks = 1000 * TimeSpan.TicksPerMillisecond;

    // Background timer that dumps counters every 2s regardless of NID activity,
    // so we can see "NID calls have stopped" even if no NID fires.
    private static readonly System.Threading.Timer _counterDumpTimer = new(_ =>
    {
        var now = DateTime.UtcNow.Ticks;
        if (now < _nextCounterDump)
        {
            return;
        }
        _nextCounterDump = now + CounterDumpIntervalTicks;
        Console.Error.WriteLine(
            $"[NID-COUNTS] 1D0H2KNjshE={Interlocked.Read(ref _calls1D0)} " +
            $"hsi9drzHR2k={Interlocked.Read(ref _callsHsi9)}");
    }, null, dueTime: TimeSpan.FromSeconds(2), period: TimeSpan.FromSeconds(2));

    private static bool ReturnNonZeroEnabled =>
        Environment.GetEnvironmentVariable("SHARPEMU_NID_RETURN_NONZERO") == "1";
    private static bool CallerMapEnabled =>
        Environment.GetEnvironmentVariable("SHARPEMU_NID_CALLER_MAP") == "1";

    private static void MaybeDumpCounters(long now)
    {
        if (now < _nextCounterDump)
        {
            return;
        }
        _nextCounterDump = now + CounterDumpIntervalTicks;
        Console.Error.WriteLine(
            $"[NID-COUNTS] 1D0H2KNjshE={Interlocked.Read(ref _calls1D0)} " +
            $"hsi9drzHR2k={Interlocked.Read(ref _callsHsi9)}");
    }

    private static string DescribeCaller(CpuContext ctx)
    {
        if (!CallerMapEnabled)
        {
            return string.Empty;
        }

        var rsp = ctx[CpuRegister.Rsp];
        if (!ctx.TryReadUInt64(rsp, out var retAddr) || retAddr == 0)
        {
            return $" caller=invalid_rsp[0x{rsp:X16}]";
        }

        if (KernelModuleRegistry.TryGetModuleByAddress(retAddr, out var module))
        {
            var offset = retAddr - module.BaseAddress;
            return $" caller={module.Name}+0x{offset:X} (addr=0x{retAddr:X16})";
        }

        return $" caller=unknown@0x{retAddr:X16}";
    }

    [SysAbiExport(Nid = "1D0H2KNjshE", ExportName = "1D0H2KNjshE_traced", Target = Generation.Gen5, LibraryName = "libc")]
    public static int NidTrace_1D0H2KNjshE(CpuContext ctx)
    {
        Interlocked.Increment(ref _calls1D0);
        var now = DateTime.UtcNow.Ticks;
        if (now >= _nextLog1D0)
        {
            _nextLog1D0 = now + LogIntervalTicks;
            Console.Error.WriteLine(
                $"[NID-TRACE] 1D0H2KNjshE rdi=0x{ctx[CpuRegister.Rdi]:X16} rsi=0x{ctx[CpuRegister.Rsi]:X16} " +
                $"rdx=0x{ctx[CpuRegister.Rdx]:X16} rcx=0x{ctx[CpuRegister.Rcx]:X16} " +
                $"r8=0x{ctx[CpuRegister.R8]:X16} r9=0x{ctx[CpuRegister.R9]:X16} " +
                $"thread=0x{GuestThreadExecution.CurrentGuestThreadHandle:X16}{DescribeCaller(ctx)}");
        }
        MaybeDumpCounters(now);

        if (ReturnNonZeroEnabled)
        {
            var r8 = ctx[CpuRegister.R8];
            ctx[CpuRegister.Rax] = r8 != 0 ? r8 : 1ul;
            return unchecked((int)ctx[CpuRegister.Rax]);
        }
        return ctx.SetReturn(0);
    }

    [SysAbiExport(Nid = "hsi9drzHR2k", ExportName = "hsi9drzHR2k_traced", Target = Generation.Gen5, LibraryName = "libc")]
    public static int NidTrace_hsi9drzHR2k(CpuContext ctx)
    {
        Interlocked.Increment(ref _callsHsi9);
        var now = DateTime.UtcNow.Ticks;
        if (now >= _nextLogHsi9)
        {
            _nextLogHsi9 = now + LogIntervalTicks;
            Console.Error.WriteLine(
                $"[NID-TRACE] hsi9drzHR2k rdi=0x{ctx[CpuRegister.Rdi]:X16} rsi=0x{ctx[CpuRegister.Rsi]:X16} " +
                $"rdx=0x{ctx[CpuRegister.Rdx]:X16} rcx=0x{ctx[CpuRegister.Rcx]:X16} " +
                $"r8=0x{ctx[CpuRegister.R8]:X16} r9=0x{ctx[CpuRegister.R9]:X16} " +
                $"thread=0x{GuestThreadExecution.CurrentGuestThreadHandle:X16}{DescribeCaller(ctx)}");
        }
        MaybeDumpCounters(now);

        if (ReturnNonZeroEnabled)
        {
            var r8 = ctx[CpuRegister.R8];
            ctx[CpuRegister.Rax] = r8 != 0 ? r8 : 1ul;
            return unchecked((int)ctx[CpuRegister.Rax]);
        }
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
