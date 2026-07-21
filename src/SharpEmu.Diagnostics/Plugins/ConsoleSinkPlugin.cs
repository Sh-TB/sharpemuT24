// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.Diagnostics.Contracts;

namespace SharpEmu.Diagnostics.Plugins;

/// <summary>
/// Console Sink Plugin — prints events live to stderr.
/// Enable with SHARPEMU_DIAG_CONSOLE=1
/// Filter with SHARPEMU_DIAG_CONSOLE_FILTER=cpu,crash
/// </summary>
public sealed class ConsoleSinkPlugin : IDiagnosticPlugin
{
    private readonly HashSet<string>? _filter;

    public static PluginMetadata Meta => new()
    {
        Name = "ConsoleSink",
        Version = "1.0",
        Description = "Prints events live to stderr",
        EnvVar = "SHARPEMU_DIAG_CONSOLE",
        EnabledByDefault = false
    };
    public PluginMetadata Metadata => Meta;

    public ConsoleSinkPlugin()
    {
        var f = Environment.GetEnvironmentVariable("SHARPEMU_DIAG_CONSOLE_FILTER");
        if (!string.IsNullOrWhiteSpace(f))
            _filter = new HashSet<string>(f.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries), StringComparer.OrdinalIgnoreCase);
    }

    public void Initialize(IDiagnosticContext context) { }

    public void OnEvent(IDiagnosticEvent e)
    {
        if (_filter != null && !_filter.Contains(e.Category)) return;
        var ts = Core.DiagnosticClock.ElapsedMs;
        Console.Error.WriteLine($"[DIAG {ts,10:F1}] {e.Category,-8} {e.Type,-12} {DescribeEvent(e)}");
    }

    public object? Shutdown() => null;

    private static string DescribeEvent(IDiagnosticEvent e) => e switch
    {
        Contracts.Events.BootEvent be => be.StageName,
        Contracts.Events.ImportEvent ie => $"{ie.Nid} result={ie.Result}",
        Contracts.Events.CpuEvent ce => $"RIP=0x{ce.Rip:X16}",
        Contracts.Events.MemoryEvent me => $"{me.Operation} 0x{me.Address:X16} size=0x{me.Size:X}",
        Contracts.Events.ThreadEvent te => $"thread=0x{te.ThreadId:X16} {te.Operation}",
        Contracts.Events.CrashEvent ce => $"RIP=0x{ce.Rip:X16} fault=0x{ce.FaultAddress:X16}",
        Contracts.Events.GpuEvent ge => $"{ge.Operation} {ge.Detail ?? ""}",
        _ => ""
    };
}
