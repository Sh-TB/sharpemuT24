// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Text;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Contracts.Events;

namespace SharpEmu.Diagnostics.Plugins;

public sealed class CrashPackagePlugin : IDiagnosticPlugin
{
    private CrashEvent? _crash;

    public static PluginMetadata Meta => new()
    {
        Name = "CrashPackage",
        Version = "1.0",
        Description = "Collects crash data (RIP, fault, registers, signal)",
        EnvVar = "SHARPEMU_DIAG_CRASH",
        EnabledByDefault = true
    };
    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context) { }

    public void OnEvent(IDiagnosticEvent e)
    {
        if (e is CrashEvent ce && _crash == null)
            _crash = ce;
    }

    public object? Shutdown()
    {
        if (_crash is null) return null;
        var c = _crash;
        var sb = new StringBuilder();
        sb.AppendLine("=== Crash Report ===");
        sb.AppendLine($"  Type:   {c.CrashType}");
        sb.AppendLine($"  Signal: {c.Signal}");
        sb.AppendLine($"  RIP:    0x{c.Rip:X16}");
        sb.AppendLine($"  Fault:  0x{c.FaultAddress:X16}");
        if (c.Registers != null)
        {
            sb.AppendLine("  Registers:");
            foreach (var (name, value) in c.Registers)
                sb.AppendLine($"    {name,-4} = 0x{value:X16}");
        }
        return sb.ToString();
    }
}
