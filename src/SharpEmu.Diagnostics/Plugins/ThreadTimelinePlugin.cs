// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Collections.Concurrent;
using System.Text;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Contracts.Events;

namespace SharpEmu.Diagnostics.Plugins;

public sealed class ThreadTimelinePlugin : IDiagnosticPlugin
{
    private readonly ConcurrentDictionary<ulong, string> _threadStates = new();
    private readonly ConcurrentBag<ThreadEv> _events = new();

    private readonly record struct ThreadEv(ulong Id, string Op, string Detail, long Ts);

    public static PluginMetadata Meta => new()
    {
        Name = "ThreadTimeline",
        Version = "1.0",
        Description = "Tracks thread lifecycle (create/sleep/wake/exit)",
        EnvVar = "SHARPEMU_DIAG_THREADS",
        EnabledByDefault = false
    };
    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context) { }

    public void OnEvent(IDiagnosticEvent e)
    {
        if (e is not ThreadEvent te) return;
        _threadStates[te.ThreadId] = te.Operation;
        _events.Add(new ThreadEv(te.ThreadId, te.Operation, te.Detail ?? "", te.Timestamp));
    }

    public object? Shutdown()
    {
        if (_events.IsEmpty) return null;
        var sb = new StringBuilder();
        sb.AppendLine($"=== Thread Timeline ({_threadStates.Count} threads, {_events.Count} events) ===");
        foreach (var ev in _events.OrderBy(e => e.Ts))
            sb.AppendLine($"  T={ev.Ts}  Thread=0x{ev.Id:X16}  {ev.Op,-10}  {ev.Detail}");
        return sb.ToString();
    }
}
