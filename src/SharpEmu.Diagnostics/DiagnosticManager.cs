// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using System.Text.Json;
using SharpEmu.Diagnostics.Contracts;
using SharpEmu.Diagnostics.Core;
using SharpEmu.Diagnostics.Export;
using SharpEmu.Diagnostics.Plugins;

namespace SharpEmu.Diagnostics;

/// <summary>
/// Top-level diagnostic manager. Minimal API surface:
///   Start()    — initialize plugins
///   Publish()  — send event to all plugins
///   Flush()    — collect data from plugins and export to disk
///   Stop()     — shutdown
///
/// Plugins are auto-registered based on environment variables or
/// a diagnostics.json config file.
/// </summary>
public sealed class DiagnosticManager : IDisposable
{
    private EventBus? _bus;
    private EventFilter? _filter;
    private DiagnosticContext? _context;
    private PluginRegistry? _registry;
    private readonly string _gameId;
    private readonly string _sessionDir;
    private bool _active;

    public bool IsActive => _active;

    public DiagnosticManager(string gameId, string sessionDirectory)
    {
        _gameId = gameId;
        _sessionDir = sessionDirectory;
    }

    /// <summary>Initialize the bus, registry, and auto-register plugins based on config.</summary>
    public void Start()
    {
        var config = DiagnosticConfig.Load();
        _active = config.IsAnyEnabled;
        if (!_active) return;

        Directory.CreateDirectory(_sessionDir);
        _bus = new EventBus();
        _filter = new EventFilter();
        _context = new DiagnosticContext(_gameId, _sessionDir, _bus);
        _registry = new PluginRegistry(_bus, _context);

        if (config.IsEnabled("BootTimeline")) _registry.Register<BootTimelinePlugin>();
        if (config.IsEnabled("ImportTimeline")) _registry.Register<ImportTimelinePlugin>();
        if (config.IsEnabled("FirstFailure")) _registry.Register<FirstFailurePlugin>();
        if (config.IsEnabled("CpuTrace")) _registry.Register<CpuTracePlugin>();
        if (config.IsEnabled("CrashPackage")) _registry.Register<CrashPackagePlugin>();
        if (config.IsEnabled("ThreadTimeline")) _registry.Register<ThreadTimelinePlugin>();
        if (config.IsEnabled("MemoryTimeline")) _registry.Register<MemoryTimelinePlugin>();
        if (config.IsEnabled("Statistics")) _registry.Register<StatisticsPlugin>();
        if (config.IsEnabled("ConsoleSink")) _registry.Register<ConsoleSinkPlugin>();
    }

    /// <summary>Publish an event to all registered plugins.</summary>
    public void Publish(IDiagnosticEvent e)
    {
        if (_active && _bus != null && (_filter?.Allows(e) ?? true)) _bus.Publish(e);
    }

    /// <summary>Collect data from all plugins and write to disk.</summary>
    public void Flush()
    {
        if (!_active || _bus == null) return;
        var data = _bus.FlushAll();
        DiagnosticExporter.ExportJson(_sessionDir, data);
        DiagnosticExporter.ExportText(_sessionDir, data);
        DiagnosticExporter.ExportMarkdown(_sessionDir, _gameId, data);
    }

    /// <summary>Shutdown all plugins and release resources.</summary>
    public void Stop()
    {
        Flush();
        _active = false;
    }

    public void Dispose() => Stop();

    /// <summary>List all available plugins and their metadata.</summary>
    public static List<PluginMetadata> ListPlugins() =>
        new()
        {
            BootTimelinePlugin.Meta,
            ImportTimelinePlugin.Meta,
            FirstFailurePlugin.Meta,
            CpuTracePlugin.Meta,
            CrashPackagePlugin.Meta,
            ThreadTimelinePlugin.Meta,
            MemoryTimelinePlugin.Meta,
            StatisticsPlugin.Meta,
            ConsoleSinkPlugin.Meta,
        };
}
