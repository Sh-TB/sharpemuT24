// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Text;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Contracts.Events;
using SharpEmu.Diagnostics.Util;

namespace SharpEmu.Diagnostics.Plugins;

public sealed class CpuTracePlugin : IDiagnosticPlugin
{
    private RingBuffer<CpuRecord>? _buffer;
    private long _total;
    private int _sampleRate = 1;

    private readonly record struct CpuRecord(ulong Rip, byte[] Opcode);

    public static PluginMetadata Meta => new()
    {
        Name = "CpuTrace",
        Version = "1.0",
        Description = "Ring buffer of last N instruction checkpoints",
        EnvVar = "SHARPEMU_DIAG_CPU",
        EnabledByDefault = false
    };
    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context)
    {
        var size = int.TryParse(Environment.GetEnvironmentVariable("SHARPEMU_DIAG_CPU_BUFFER"), out var s) ? s : 5000;
        _buffer = new RingBuffer<CpuRecord>(size);
        _sampleRate = int.TryParse(Environment.GetEnvironmentVariable("SHARPEMU_DIAG_CPU_SAMPLE"), out var sr) ? sr : 1;
    }

    public void OnEvent(IDiagnosticEvent e)
    {
        if (e is not CpuEvent ce || _buffer == null) return;
        if (Interlocked.Increment(ref _total) % _sampleRate != 0) return;
        _buffer.Add(new CpuRecord(ce.Rip, ce.Opcode));
    }

    public object? Shutdown()
    {
        if (_buffer == null || _total == 0) return null;
        var records = _buffer.GetRecent(5000);
        var sb = new StringBuilder();
        sb.AppendLine($"=== CPU Trace ({_total} instructions, buffer={_buffer.Capacity}, sample=1/{_sampleRate}) ===");
        foreach (var rec in records)
            sb.AppendLine($"  RIP=0x{rec.Rip:X16}  OP={Convert.ToHexString(rec.Opcode)}");
        return sb.ToString();
    }
}
