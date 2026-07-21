// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Collections.Concurrent;
using System.Text;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Contracts.Events;

namespace SharpEmu.Diagnostics.Plugins;

/// <summary>
/// Boot Timeline Plugin — records timestamps for each boot stage.
/// Enable with SHARPEMU_DIAG_BOOT=1
/// </summary>
public sealed class BootTimelinePlugin : IDiagnosticPlugin
{
    private readonly ConcurrentDictionary<double, string> _stages = new();
    private readonly System.Diagnostics.Stopwatch _sw = System.Diagnostics.Stopwatch.StartNew();
    private IDiagnosticContext? _context;

    public static PluginMetadata Meta => new()
    {
        Name = "BootTimeline",
        Version = "1.0",
        Description = "Records timestamps for each boot stage (ELF, TLS, CRT, Imports, GPU, etc.)",
        EnvVar = "SHARPEMU_DIAG_BOOT",
        EnabledByDefault = true
    };

    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context) => _context = context;

    public void OnEvent(IDiagnosticEvent e)
    {
        if (e is BootEvent be)
            _stages.TryAdd(_sw.Elapsed.TotalMilliseconds, $"{be.StageName} ({(be.Success ? "OK" : "FAIL")})");
    }

    public object? Shutdown()
    {
        if (_stages.IsEmpty) return null;
        var sb = new StringBuilder();
        sb.AppendLine("=== Boot Timeline ===");
        foreach (var (time, stage) in _stages.OrderBy(kvp => kvp.Key))
            sb.AppendLine($"  {time,10:F1} ms  {stage}");
        return sb.ToString();
    }
}
