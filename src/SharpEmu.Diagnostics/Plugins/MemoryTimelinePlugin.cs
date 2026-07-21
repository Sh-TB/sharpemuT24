// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Collections.Concurrent;
using System.Text;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Contracts.Events;

namespace SharpEmu.Diagnostics.Plugins;

public sealed class MemoryTimelinePlugin : IDiagnosticPlugin
{
    private readonly ConcurrentDictionary<ulong, (ulong Size, string Op)> _active = new();
    private readonly ConcurrentBag<MemEv> _events = new();

    private readonly record struct MemEv(string Op, ulong Addr, ulong Size, long Ts);

    public static PluginMetadata Meta => new()
    {
        Name = "MemoryTimeline",
        Version = "1.0",
        Description = "Tracks memory allocations and mappings",
        EnvVar = "SHARPEMU_DIAG_MEMORY",
        EnabledByDefault = false
    };
    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context) { }

    public void OnEvent(IDiagnosticEvent e)
    {
        if (e is not MemoryEvent me) return;
        _events.Add(new MemEv(me.Operation, me.Address, me.Size, me.Timestamp));
        if (me.Operation is "Allocate" or "Map")
            _active[me.Address] = (me.Size, me.Operation);
        else if (me.Operation is "Free" or "Unmap")
            _active.TryRemove(me.Address, out _);
    }

    public object? Shutdown()
    {
        if (_events.IsEmpty) return null;
        var totalBytes = _active.Values.Sum(v => (long)v.Size);
        var sb = new StringBuilder();
        sb.AppendLine($"=== Memory Timeline ({_active.Count} active, {_events.Count} events) ===");
        sb.AppendLine($"Total active: {totalBytes / 1024 / 1024} MB");
        foreach (var ev in _events.OrderBy(e => e.Ts))
            sb.AppendLine($"  T={ev.Ts}  {ev.Op,-10}  Addr=0x{ev.Addr:X16}  Size=0x{ev.Size:X}");
        return sb.ToString();
    }
}
