// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.Diagnostics.Contracts;

namespace SharpEmu.Diagnostics;

/// <summary>
/// Minimal debug intelligence engine stub for CLI compatibility.
/// </summary>
public sealed class DebugIntelligenceEngine : IDiagnosticEventBus, IDisposable
{
    public string SessionDirectory { get; }
    public bool IsActive { get; private set; }
    public long TotalImports { get; }
    public long TotalEvents { get; }

    private DebugIntelligenceEngine(string gameName, string sessionDir)
    {
        SessionDirectory = sessionDir;
        IsActive = true;
    }

    public static DebugIntelligenceEngine CreateSession(string gameName, string sessionDir, object? profile = null)
    {
        Directory.CreateDirectory(sessionDir);
        return new DebugIntelligenceEngine(gameName, sessionDir);
    }

    public void GeneratePackage() { }
    public (int confidence, string summary, string details) AnalyzeRootCause()
    {
        return (0, "Diagnostics stub — no analysis available", "");
    }

    public void Publish(SharpEmu.Logging.DiagnosticEvent evt) { }
    public void Flush() { }

    public void Dispose()
    {
        IsActive = false;
    }
}
