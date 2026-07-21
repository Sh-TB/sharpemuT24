// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Text;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Contracts.Events;

namespace SharpEmu.Diagnostics.Plugins;

public sealed class FirstFailurePlugin : IDiagnosticPlugin
{
    private record Failure(string Type, string Nid, int Result, ulong Rip, double TimeMs);
    private Failure? _first;
    private readonly System.Diagnostics.Stopwatch _sw = System.Diagnostics.Stopwatch.StartNew();

    public static PluginMetadata Meta => new()
    {
        Name = "FirstFailure",
        Version = "1.0",
        Description = "Detects the first non-zero import result or crash",
        EnvVar = "SHARPEMU_DIAG_FAILURE",
        EnabledByDefault = true
    };
    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context) { }

    public void OnEvent(IDiagnosticEvent e)
    {
        if (_first != null) return;
        switch (e)
        {
            case ImportEvent ie when ie.Result != 0:
                _first = new Failure("ImportError", ie.Nid, ie.Result, 0, _sw.Elapsed.TotalMilliseconds);
                break;
            case CrashEvent ce:
                _first = new Failure("Crash", "", ce.Signal, ce.Rip, _sw.Elapsed.TotalMilliseconds);
                break;
        }
    }

    public object? Shutdown()
    {
        if (_first is null) return null;
        var f = _first;
        var sb = new StringBuilder();
        sb.AppendLine("=== First Failure ===");
        sb.AppendLine($"  Type:     {f.Type}");
        sb.AppendLine($"  NID:      {f.Nid}");
        sb.AppendLine($"  Result:   {f.Result}");
        sb.AppendLine($"  RIP:      0x{f.Rip:X16}");
        sb.AppendLine($"  Time:     {f.TimeMs:F1} ms after boot");
        return sb.ToString();
    }
}
