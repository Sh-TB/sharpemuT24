// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Text;
using SharpEmu.Diagnostics.Contracts;

namespace SharpEmu.Diagnostics.Plugins;

/// <summary>
/// Statistics Plugin — lightweight counters without trace data.
/// Enable with SHARPEMU_DIAG_STATS=1
/// </summary>
public sealed class StatisticsPlugin : IDiagnosticPlugin
{
    private long _importCount, _errorCount, _threadCount, _memoryAllocs, _memoryBytes, _gpuSubmits, _gpuDraws, _crashCount;

    public static PluginMetadata Meta => new()
    {
        Name = "Statistics",
        Version = "1.0",
        Description = "Lightweight counters (no trace data, just totals)",
        EnvVar = "SHARPEMU_DIAG_STATS",
        EnabledByDefault = true
    };
    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context) { }

    public void OnEvent(IDiagnosticEvent e)
    {
        switch (e)
        {
            case Contracts.Events.ImportEvent ie:
                Interlocked.Increment(ref _importCount);
                if (ie.Result != 0) Interlocked.Increment(ref _errorCount);
                break;
            case Contracts.Events.ThreadEvent te when te.Operation == "Create":
                Interlocked.Increment(ref _threadCount);
                break;
            case Contracts.Events.MemoryEvent me when me.Operation == "Allocate":
                Interlocked.Increment(ref _memoryAllocs);
                Interlocked.Add(ref _memoryBytes, (long)me.Size);
                break;
            case Contracts.Events.GpuEvent ge:
                if (ge.Operation == "Submit") Interlocked.Increment(ref _gpuSubmits);
                if (ge.Operation == "Draw") Interlocked.Increment(ref _gpuDraws);
                break;
            case Contracts.Events.CrashEvent:
                Interlocked.Increment(ref _crashCount);
                break;
        }
    }

    public object? Shutdown()
    {
        var sb = new StringBuilder();
        sb.AppendLine("=== Statistics ===");
        sb.AppendLine($"  Imports:       {_importCount:N0}");
        sb.AppendLine($"  Import errors: {_errorCount:N0}");
        sb.AppendLine($"  Threads:       {_threadCount:N0}");
        sb.AppendLine($"  Memory allocs: {_memoryAllocs:N0} ({_memoryBytes / 1024 / 1024} MB)");
        sb.AppendLine($"  GPU submits:   {_gpuSubmits:N0}");
        sb.AppendLine($"  GPU draws:     {_gpuDraws:N0}");
        sb.AppendLine($"  Crashes:       {_crashCount:N0}");
        return sb.ToString();
    }
}
