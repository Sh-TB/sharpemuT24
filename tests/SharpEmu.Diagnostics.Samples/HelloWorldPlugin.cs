// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
//
// MINIMAL PLUGIN SAMPLE — copy this file, change 3 lines, done.
//
// To use:
// 1. Place this in src/SharpEmu.Diagnostics/Plugins/
// 2. Register in DiagnosticManager.Start():
//    if (config.IsEnabled("HelloWorld")) _registry.Register<HelloWorldPlugin>();
// 3. Enable: export SHARPEMU_DIAG_HELLO=1

using System.Text;
using SharpEmu.Diagnostics.Contracts;

namespace SharpEmu.Diagnostics.Plugins;

public sealed class HelloWorldPlugin : IDiagnosticPlugin
{
    private int _eventCount;

    public static PluginMetadata Meta => new()
    {
        Name = "HelloWorld",
        Version = "1.0",
        Description = "Minimal sample plugin — counts events",
        EnvVar = "SHARPEMU_DIAG_HELLO",
        EnabledByDefault = false
    };

    public PluginMetadata Metadata => Meta;

    public void Initialize(IDiagnosticContext context)
    {
        // Called once at startup. Save context if you need to publish events.
    }

    public void OnEvent(IDiagnosticEvent e)
    {
        // Called for EVERY event. Be fast.
        _eventCount++;
    }

    public object? Shutdown()
    {
        // Return data for the exporter. Do NOT write files directly.
        return $"=== Hello World Plugin ===\n  Events seen: {_eventCount}";
    }
}
