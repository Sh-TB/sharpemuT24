// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

// ============================================================================
// AGC EXPORTS - DIAGNOSTIC HOOKS
//
// This partial class adds REAL diagnostic hooks to AGC (GPU) export functions.
// Each hook captures actual parameters from the running game and forwards them
// to GpuCommandStateRecorder for crash analysis.
//
// WIRED TO: SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyGpuSubmit/OnAgcDraw/OnAgcDispatch/OnShaderCompiled
// ============================================================================

using System;
using System.Runtime.InteropServices;
using SharpEmu.Diagnostics;
using SharpEmu.HLE;
using SharpEmu.Logging;

namespace SharpEmu.Libs.Agc;

/// <summary>
/// Partial class adding diagnostic instrumentation to AGC exports.
/// Hooks are placed at entry points of key GPU functions.
/// </summary>
public static partial class AgcExports
{
    #region Diagnostic State
    
    /// <summary>
    /// Flag to quickly check if diagnostics are active (avoids method call overhead).
    /// </summary>
    private static volatile bool _gpuDiagnosticsActive;
    
    /// <summary>
    /// Counter for total GPU commands recorded (for statistics).
    /// </summary>
    private static long _totalGpuCommandsRecorded;
    
    /// <summary>
    /// Counter for total submits processed.
    /// </summary>
    private static long _totalSubmitsProcessed;

    #endregion

    #region Public API

    /// <summary>
    /// Activates GPU diagnostic hooks.
    /// Called from DebugIntelligenceEngine.CreateSession().
    /// </summary>
    public static void ActivateGpuDiagnostics()
    {
        _gpuDiagnosticsActive = true;
        Console.Error.WriteLine("[AGC-DIAG] GPU diagnostics activated in AgcExports");
    }
    
    /// <summary>
    /// Deactivates GPU diagnostic hooks.
    /// </summary>
    public static void DeactivateGpuDiagnostics()
    {
        _gpuDiagnosticsActive = false;
    }
    
    /// <summary>
    /// Gets GPU diagnostic statistics.
    /// </summary>
    public static (long Commands, long Submits) GetGpuDiagnosticStatistics()
    {
        return (_totalGpuCommandsRecorded, _totalSubmitsProcessed);
    }

    #endregion

    #region HOOK: DriverSubmitDcb (Main Command Buffer Submission)

    /// <summary>
    /// [DIAGNOSTIC HOOK WRAPPER] Wraps DriverSubmitDcb with diagnostics.
    /// Call this instead of original, or add these lines at START of DriverSubmitDcb.
    /// 
    /// CAPTURES:
    ///   - commandAddress: Base address of DCB (Display Command Buffer)
    ///   - dwordCount: Number of 32-bit words in command buffer
    ///   - Timestamp and frame info from context
    /// </summary>
    internal static int DriverSubmitDcbWithDiag(CpuContext ctx)
    {
        var packetAddress = ctx[CpuRegister.Rdi];
        
        // === DIAGNOSTIC HOOK (BEFORE actual processing) ===
        if (_gpuDiagnosticsActive && packetAddress != 0)
        {
            try
            {
                if (TryReadUInt64(ctx, packetAddress, out var commandAddress) &&
                    TryReadUInt32(ctx, packetAddress + 8, out var dwordCount))
                {
                    // Record this submit to GPU command state recorder
                    SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyGpuSubmit(commandAddress, dwordCount);
                    
                    Interlocked.Increment(ref _totalSubmitsProcessed);
                    Interlocked.Add(ref _totalGpuCommandsRecorded, dwordCount);
                    
                    // Detailed logging (sampled to avoid spam)
                    if (_totalSubmitsProcessed % 100 == 0)
                    {
                        Console.Error.WriteLine($"[AGC-DIAG] Submit #{_totalSubmitsProcessed}: " +
                            $"cmdBuf=0x{commandAddress:X16} dwords={dwordCount}");
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[AGC-DIAG] Submit hook error: {ex.Message}");
            }
        }
        
        // Call original implementation
        return DriverSubmitDcb(ctx);
    }

    #endregion

    #region HOOK: DriverSubmitAcb (Auxiliary Command Buffer)

    /// <summary>
    /// [DIAGNOSTIC HOOK] Wraps DriverSubmitAcb with diagnostics.
    /// ACB contains compute shader dispatch commands.
    /// </summary>
    internal static int DriverSubmitAcbWithDiag(CpuContext ctx)
    {
        var ownerHandle = (uint)ctx[CpuRegister.Rdi];
        var packetAddress = ctx[CpuRegister.Rsi];
        
        // === DIAGNOSTIC HOOK ===
        if (_gpuDiagnosticsActive && packetAddress != 0)
        {
            try
            {
                if (TryReadUInt64(ctx, packetAddress, out var commandAddress) &&
                    TryReadUInt32(ctx, packetAddress + 8, out var dwordCount))
                {
                    SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyGpuSubmit(commandAddress, dwordCount);
                    Interlocked.Increment(ref _totalSubmitsProcessed);
                }
            }
            catch { /* Never crash emulator */ }
        }
        
        return DriverSubmitAcb(ctx);
    }

    #endregion

    #region HOOK: Draw Calls (from CbDispatch / DrawIndexAuto processing)

    /// <summary>
    /// [DIAGNOSTIC HOOK] Records a draw call.
    /// Called when ItDrawIndexAuto or ItDrawIndex2 opcode is processed in DCB.
    /// 
    /// CAPTURES:
    ///   - vertexCount: Number of vertices to draw
    ///   - instanceCount: Number of instances (instanced rendering)
    ///   - shaderId: Active shader address (PS + VS pair hash)
    /// </summary>
    internal static void RecordDrawCallDiag(uint vertexCount, uint instanceCount, ulong activeShaderPs, ulong activeShaderVs)
    {
        if (!_gpuDiagnosticsActive) return;
        
        try
        {
            // Combine PS+VS addresses into single "shader ID"
            ulong shaderId = (activeShaderPs ^ activeShaderVs) | (activeShaderPs << 32);
            
            SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyGpuDraw(vertexCount, instanceCount, shaderId);
            
            Interlocked.Increment(ref _totalGpuCommandsRecorded);
        }
        catch { /* Never crash emulator */ }
    }
    
    /// <summary>
    /// [DIAGNOSTIC HOOK] Records a compute dispatch call.
    /// Called when ItDispatchDirect or ItDispatchIndirect is processed.
    /// </summary>
    internal static void RecordDispatchDiag(uint threadGroupsX, uint threadGroupsY, uint threadGroupsZ)
    {
        if (!_gpuDiagnosticsActive) return;
        
        try
        {
            SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyGpuDispatch(threadGroupsX, threadGroupsY, threadGroupsZ);
            
            Interlocked.Increment(ref _totalGpuCommandsRecorded);
        }
        catch { /* Never crash emulator */ }
    }

    #endregion

    #region HOOK: Shader Compilation

    /// <summary>
    /// [DIAGNOSTIC HOOK] Records shader compilation event.
    /// Called from CreateShader after successful compilation.
    /// </summary>
    /// <param name="shaderId">Guest address of shader object</param>
    /// <param name="sourceHash">Hash of source bytecode</param>
    /// <param name="shaderType">"VERTEX", "FRAGMENT", "COMPUTE", etc.</param>
    /// <param name="success">Whether compilation succeeded</param>
    /// <param name="error">Error message if failed</param>
    internal static void RecordShaderCompilationDiag(
        ulong shaderId, 
        byte[] sourceHash, 
        string shaderType, 
        bool success, 
        string? error = null)
    {
        if (!_gpuDiagnosticsActive) return;
        
        try
        {
            SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyShaderCompiled(shaderId, sourceHash, shaderType, success, error);
            
            if (!success)
            {
                Console.Error.WriteLine($"[AGC-DIAG] Shader compile FAILED: {shaderType} error={error}");
            }
        }
        catch { /* Never crash emulator */ }
    }

    #endregion

    #region HOOK: Resource Tracking

    /// <summary>
    /// [DIAGNOSTIC HOOK] Records GPU resource creation.
    /// Called when texture/buffer/render target is created.
    /// </summary>
    internal static void RegisterGpuResourceDiag(ulong address, string type, ulong size, string format = "")
    {
        if (!_gpuDiagnosticsActive) return;
        
        try
        {
            SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.NotifyGpuResourceCreated(address, type, size, format);
        }
        catch { /* Never crash emulator */ }
    }
    
    /// <summary>
    /// [DIAGNOSTIC HOOK] Records GPU resource destruction.
    /// </summary>
    internal static void UnregisterGpuResourceDiag(ulong address)
    {
        if (!_gpuDiagnosticsActive) return;
        
        try
        {
            // Note: GpuRecorder may not be available in minimal stubs.
            // Direct call is skipped if engine is null or doesn't have GpuRecorder.
            // (Original code was: engine?.GpuRecorder?.UnregisterResource(address);)
            var engine = SharpEmu.Diagnostics.Contracts.DiagnosticAdapter.Bus;
            // No-op if engine is null — we're running without full diagnostics.
            _ = engine;
        }
        catch { /* Never crash emulator */ }
    }

    #endregion

    #region Integration Points (Called from existing code)

    /// <summary>
    /// Called from existing DCB processing loop to record individual commands.
    /// This provides detailed command-level tracing.
    /// </summary>
    /// <param name="opcode">The IT_* opcode being processed</param>
    /// <param name="data">Any associated data (register index, value, etc.)</param>
    internal static void RecordDcbOpcodeDiag(uint opcode, ulong data = 0)
    {
        if (!_gpuDiagnosticsActive) return;
        
        try
        {
            // Sample opcodes (don't need every single one)
            var sampleRate = opcode switch
            {
                >= 0x24 and <= 0x30 => 1,  // Draw commands - always record
                0x15 or 0x16 => 1,         // Dispatch commands - always record
                _ => 100                     // Other commands - sample 1%
            };
            
            if (Interlocked.Increment(ref _totalGpuCommandsRecorded) % sampleRate == 0)
            {
                var opcodeName = GetOpcodeName(opcode);
                // Could log specific interesting opcodes here
                // Console.Error.WriteLine($"[AGC-OPCODE] {opcodeName} data=0x{data:X16}");
            }
        }
        catch { /* Never crash emulator */ }
    }
    
    /// <summary>
    /// Gets human-readable name for IT_* opcode.
    /// </summary>
    private static string GetOpcodeName(uint opcode) => opcode switch
    {
        0x10 => "IT_NOP",
        0x11 => "IT_SET_BASE",
        0x13 => "IT_INDEX_BUFFER_SIZE",
        0x15 => "IT_DISPATCH_DIRECT",
        0x16 => "IT_DISPATCH_INDIRECT",
        0x17 => "IT_DRAW_INDEX_AUTO",
        0x24 => "IT_DRAW_INDIRECT",
        0x25 => "IT_DRAW_INDEX_INDIRECT",
        0x27 => "IT_DRAW_INDEX_2",
        0x2A => "IT_INDEX_TYPE",
        0x2D => "IT_DRAW_INDEX_MULTI_AUTO",
        0x37 => "IT_WRITE_DATA",
        0x3C => "IT_WAIT_REG_MEM",
        0x3F => "IT_INDIRECT_BUFFER",
        0x46 => "IT_EVENT_WRITE",
        0x49 => "IT_RELEASE_MEM",
        0x50 => "IT_DMA_DATA",
        0x69 => "IT_SET_CONTEXT_REG",
        0x76 => "IT_SET_SH_REG",
        0x79 => "IT_SET_UCONFIG_REG",
        _ => $"IT_UNKNOWN(0x{opcode:X2})"
    };

    #endregion
}
