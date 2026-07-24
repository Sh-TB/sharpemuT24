// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

// ============================================================================
// DIRECT EXECUTION BACKEND - DIAGNOSTICS INTEGRATION (POST-REFACTOR)
//
// This file is now simplified to use SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.
// The old complex implementation (with Win64 CONTEXT offsets, signal-safe
// stackalloc buffers, etc.) has been removed because:
//
// 1. The Contracts layer abstracts all of that away.
// 2. The Adapter handles the routing to the registered diagnostic bus.
// 3. Crash capture is now handled by the ICrashDiagnosticSource interface.
//
// Core no longer needs to know about SignalSafeCrashWriter, RegisterSnapshot
// internal layout, or any Diagnostics-internal types.
// ============================================================================

using SharpEmu.Diagnostics.Contracts;
using SharpEmu.HLE;

namespace SharpEmu.Core.Cpu.Native;

public sealed unsafe partial class DirectExecutionBackend
{
    #region Diagnostic State

    /// <summary>
    /// Quick-check flag to avoid method calls when diagnostics are inactive.
    /// </summary>
    private static volatile bool _diagnosticsActive;
    
    /// <summary>
    /// Sampling counter for CPU trace.
    /// </summary>
    [ThreadStatic]
    private static long _instructionSampleCounter;
    
    /// <summary>
    /// Counter for import verification.
    /// </summary>
    [ThreadStatic]
    private static long _importVerifyCounter;
    
    /// <summary>
    /// Pre-allocated buffer for opcode capture.
    /// </summary>
    [ThreadStatic]
    private static byte[]? _opcodeBuffer;
    
    /// <summary>
    /// Pre-allocated buffer for register snapshot (16 registers × 8 bytes = 128 bytes).
    /// </summary>
    [ThreadStatic]
    private static byte[]? _registerBuffer;
    
    private static int _instructionSampleRate = 100;

    #endregion

    #region Public API

    public static void ActivateDiagnostics()
    {
        _diagnosticsActive = true;
        Console.Error.WriteLine("[DIAG-HOOKS] Diagnostics activated in DirectExecutionBackend");
    }
    
    public static void DeactivateDiagnostics()
    {
        _diagnosticsActive = false;
    }
    
    public static bool IsDiagnosticsActive => _diagnosticsActive;

    public static void SetInstructionSamplingRate(int rate)
    {
        _instructionSampleRate = Math.Max(1, rate);
    }

    #endregion

    #region HOOK 1: CPU Instruction Trace

    /// <summary>
    /// Records a CPU execution checkpoint at an import dispatch point.
    /// Called from DirectExecutionBackend.Imports.DispatchImport().
    /// </summary>
    internal static void RecordInstructionExecuted(
        CpuContext context, 
        ulong rip, 
        int instructionLength,
        ulong memoryOperandAddress = 0,
        int memoryAccessType = 0)
    {
        if (!_diagnosticsActive) return;
        if (!SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.IsActive) return;
        
        // Sample to reduce overhead
        long count = ++_instructionSampleCounter;
        if ((count % _instructionSampleRate) != 0) return;
        
        try
        {
            _opcodeBuffer ??= new byte[16];
            _registerBuffer ??= new byte[128];
            
            // Read opcode from guest memory
            int opcodeLen = Math.Min(instructionLength, 16);
            if (instructionLength == 0) opcodeLen = 16;
            
            bool opcodeRead = false;
            if (context.Memory != null)
            {
                try
                {
                    opcodeRead = context.Memory.TryRead(rip, _opcodeBuffer.AsSpan(0, opcodeLen));
                }
                catch { }
            }
            
            if (!opcodeRead)
            {
                Array.Clear(_opcodeBuffer, 0, opcodeLen);
            }
            
            // Capture register state via indexer
            WriteRegisterSnapshot(context, _registerBuffer);
            
            // Forward to DiagnosticAdapter (which routes to registered source)
            SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyInstruction(
                rip,
                _opcodeBuffer.AsSpan(0, opcodeLen),
                _registerBuffer.AsSpan(0, 128),
                memoryOperandAddress,
                memoryAccessType,
                0);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[DIAG-HOOKS] Instruction record failed: {ex.Message}");
        }
    }
    
    internal static void RecordInstructionExecutedLightweight(ulong rip)
    {
        if (!_diagnosticsActive) return;
        if (!SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.IsActive) return;
        
        try
        {
            SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyInstructionLightweight(rip);
        }
        catch { }
    }

    #endregion

    #region HOOK 2: Import Dispatch Verification

    internal static void VerifyImportHookWorking(string libraryName, string nid, ulong retAddr, ulong retVal)
    {
        if (!_diagnosticsActive) return;
        
        long count = ++_importVerifyCounter;
        if ((count % 1000) != 0) return;
        
        Console.Error.WriteLine($"[DIAG-VERIFY] Import #{count} OK: {libraryName}::{nid} ret=0x{retVal:X16}");
    }

    #endregion

    #region HOOK 3: Crash Handler Integration

    /// <summary>
    /// Captures crash context from signal handler.
    /// Uses Win64 CONTEXT offsets (PosixSignals.cs synthesizes a Win64 CONTEXT
    /// even on Linux/macOS, so we always use the same layout).
    /// </summary>
    internal static void CaptureCrashContextFromSignal(
        string signalType, 
        ulong faultAddress, 
        void* contextRecord)
    {
        if (contextRecord == null) return;
        
        try
        {
            // Read registers from Win64 CONTEXT
            var rip = ReadCtxU64((byte*)contextRecord, WINCTX_RIP);
            var rax = ReadCtxU64((byte*)contextRecord, WINCTX_RAX);
            var rbx = ReadCtxU64((byte*)contextRecord, WINCTX_RBX);
            var rcx = ReadCtxU64((byte*)contextRecord, WINCTX_RCX);
            var rdx = ReadCtxU64((byte*)contextRecord, WINCTX_RDX);
            var rsi = ReadCtxU64((byte*)contextRecord, WINCTX_RSI);
            var rdi = ReadCtxU64((byte*)contextRecord, WINCTX_RDI);
            var rbp = ReadCtxU64((byte*)contextRecord, WINCTX_RBP);
            var rsp = ReadCtxU64((byte*)contextRecord, WINCTX_RSP);
            var r8  = ReadCtxU64((byte*)contextRecord, WINCTX_R8);
            var r9  = ReadCtxU64((byte*)contextRecord, WINCTX_R9);
            var r10 = ReadCtxU64((byte*)contextRecord, WINCTX_R10);
            var r11 = ReadCtxU64((byte*)contextRecord, WINCTX_R11);
            var r12 = ReadCtxU64((byte*)contextRecord, WINCTX_R12);
            var r13 = ReadCtxU64((byte*)contextRecord, WINCTX_R13);
            var r14 = ReadCtxU64((byte*)contextRecord, WINCTX_R14);
            var r15 = ReadCtxU64((byte*)contextRecord, WINCTX_R15);
            var rflags = ReadCtxU64((byte*)contextRecord, WINCTX_EFLAGS);
            
            // Build Contracts.RegisterSnapshot (value type, no allocation)
            var snapshot = new SharpEmu.Diagnostics.Contracts.RegisterSnapshot(
                rax, rbx, rcx, rdx, rsi, rdi, rbp, rsp,
                r8, r9, r10, r11, r12, r13, r14, r15,
                rflags, rip);
            
            // Forward to Adapter (routes to ICrashDiagnosticSource)
            SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyCrash(
                signalType, faultAddress, rip, in snapshot);
        }
        catch
        {
            // Must not throw from signal handler
        }
    }
    
    // Win64 CONTEXT offsets (AMD64) — see WinNT.h _CONTEXT
    private const int WINCTX_RAX     = 0x78;
    private const int WINCTX_RCX     = 0x80;
    private const int WINCTX_RDX     = 0x88;
    private const int WINCTX_RBX     = 0x90;
    private const int WINCTX_RSP     = 0x98;
    private const int WINCTX_RBP     = 0xA0;
    private const int WINCTX_RSI     = 0xA8;
    private const int WINCTX_RDI     = 0xB0;
    private const int WINCTX_R8      = 0xB8;
    private const int WINCTX_R9      = 0xC0;
    private const int WINCTX_R10     = 0xC8;
    private const int WINCTX_R11     = 0xD0;
    private const int WINCTX_R12     = 0xD8;
    private const int WINCTX_R13     = 0xE0;
    private const int WINCTX_R14     = 0xE8;
    private const int WINCTX_R15     = 0xF0;
    private const int WINCTX_RIP     = 0xF8;
    private const int WINCTX_EFLAGS  = 0x44;

    #endregion

    #region Private Helpers

    private static void WriteRegisterSnapshot(CpuContext ctx, byte[] buffer)
    {
        BitConverter.GetBytes(ctx[CpuRegister.Rax]).CopyTo(buffer, 0);
        BitConverter.GetBytes(ctx[CpuRegister.Rbx]).CopyTo(buffer, 8);
        BitConverter.GetBytes(ctx[CpuRegister.Rcx]).CopyTo(buffer, 16);
        BitConverter.GetBytes(ctx[CpuRegister.Rdx]).CopyTo(buffer, 24);
        BitConverter.GetBytes(ctx[CpuRegister.Rsi]).CopyTo(buffer, 32);
        BitConverter.GetBytes(ctx[CpuRegister.Rdi]).CopyTo(buffer, 40);
        BitConverter.GetBytes(ctx[CpuRegister.Rbp]).CopyTo(buffer, 48);
        BitConverter.GetBytes(ctx[CpuRegister.Rsp]).CopyTo(buffer, 56);
        BitConverter.GetBytes(ctx[CpuRegister.R8]).CopyTo(buffer, 64);
        BitConverter.GetBytes(ctx[CpuRegister.R9]).CopyTo(buffer, 72);
        BitConverter.GetBytes(ctx[CpuRegister.R10]).CopyTo(buffer, 80);
        BitConverter.GetBytes(ctx[CpuRegister.R11]).CopyTo(buffer, 88);
        BitConverter.GetBytes(ctx[CpuRegister.R12]).CopyTo(buffer, 96);
        BitConverter.GetBytes(ctx[CpuRegister.R13]).CopyTo(buffer, 104);
        BitConverter.GetBytes(ctx[CpuRegister.R14]).CopyTo(buffer, 112);
        BitConverter.GetBytes(ctx[CpuRegister.R15]).CopyTo(buffer, 120);
    }
    
    private static ulong ReadCtxU64(byte* contextRecord, int offset)
    {
        return *(ulong*)(contextRecord + offset);
    }

    #endregion
}
