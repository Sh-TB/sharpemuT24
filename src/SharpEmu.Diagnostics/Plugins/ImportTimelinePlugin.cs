// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Collections.Concurrent;
using System.Text;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Contracts.Events;

namespace SharpEmu.Diagnostics.Plugins;

public sealed class ImportTimelinePlugin : IDiagnosticPlugin
{
    private readonly ConcurrentDictionary<string, long> _frequency = new();
    private readonly ConcurrentBag<(string Nid, int Result, long Duration)> _errors = new();
    private long _totalCalls;

    public static PluginMetadata Meta => new()
    {
        Name = "ImportTimeline",
        Version = "1.0",
        Description = "Tracks every import call with NID, result, duration",
        EnvVar = "SHARPEMU_DIAG_IMPORTS",
        EnabledByDefault = true
    };
    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context) { }

    public void OnEvent(IDiagnosticEvent e)
    {
        if (e is not ImportEvent ie) return;
        Interlocked.Increment(ref _totalCalls);
        _frequency.AddOrUpdate(ie.Nid, 1, (_, c) => c + 1);
        if (ie.Result != 0)
            _errors.Add((ie.Nid, ie.Result, ie.DurationMicros));
    }

    public object? Shutdown()
    {
        if (_totalCalls == 0) return null;
        var sb = new StringBuilder();
        sb.AppendLine($"=== Import Timeline ({_totalCalls} calls, {_frequency.Count} unique NIDs) ===");
        sb.AppendLine("\nTop 20 most called:");
        foreach (var (nid, count) in _frequency.OrderByDescending(kvp => kvp.Value).Take(20))
            sb.AppendLine($"  {nid,-24} {count,10} calls");
        if (!_errors.IsEmpty)
        {
            sb.AppendLine($"\nError-returning imports ({_errors.Count}):");
            foreach (var (nid, result, duration) in _errors.Take(20))
                sb.AppendLine($"  {nid,-24} result={result,-10} duration={duration}us");
        }
        return sb.ToString();
    }
}
