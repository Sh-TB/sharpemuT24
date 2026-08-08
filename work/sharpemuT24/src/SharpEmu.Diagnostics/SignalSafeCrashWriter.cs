// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.Diagnostics.Contracts;

namespace SharpEmu.Diagnostics;

/// <summary>
/// Minimal crash writer stub for CLI compatibility.
/// </summary>
public sealed class SignalSafeCrashWriter : ICrashDiagnosticSource
{
    public static SignalSafeCrashWriter Instance { get; } = new();

    public void QueueCrash(string signalType, ulong faultAddress, ulong rip, in RegisterSnapshot registers) { }
    public void Initialize() { }
}
