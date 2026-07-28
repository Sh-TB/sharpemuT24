// Copyright (C) 2026 SharpEmu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

using SharpEmu.Logging;
using System.Text.Json;
using System.Threading;
using System.IO;

namespace SharpEmu.Libs.VideoOut;

/// <summary>
/// Video Out Manager - Handles both Real and Headless rendering modes.
/// 
/// Architecture:
/// PS5 Game → sceVideoOut → VideoOutManager → [VulkanPresenter | HeadlessPresenter]
/// 
/// This is the SINGLE decision point for GPU backend selection.
/// No other component should directly instantiate Vulkan or Headless presenters.
/// </summary>
public static class VideoOutManager
{
    private static readonly SharpEmuLogger Log = SharpEmuLog.For("SharpEmu.VideoOutManager");
    
    private static HeadlessVideoPresenter? _headlessPresenter;
    private static bool _useHeadlessMode;
    private static bool _initialized;
    private static uint _width = 1920;
    private static uint _height = 1080;
    private static string _backendReason = "Not initialized";
    
    // Fake display state for headless mode
    private static int _fakeDisplayHandle = 1000; // Start from 1000 to avoid conflicts
    private static ulong _flipCount;
    private static int _currentBuffer;
    private static DateTime _openTime;

    /// <summary>
    /// Gets whether we're running in headless mode.
    /// </summary>
    public static bool IsHeadlessMode => _useHeadlessMode;

    /// <summary>
    /// Gets the headless presenter if active.
    /// </summary>
    public static HeadlessVideoPresenter? HeadlessPresenter => _headlessPresenter;
    
    /// <summary>
    /// Gets the reason for backend selection (for diagnostics).
    /// </summary>
    public static string BackendReason => _backendReason;
    
    /// <summary>
    /// Gets current flip count (for fake display status).
    /// </summary>
    public static ulong FlipCount => _flipCount;
    
    /// <summary>
    /// Gets current buffer index (for fake display status).
    /// </summary>
    public static int CurrentBuffer => _currentBuffer;

    /// <summary>
    /// Initializes the video out system with automatic GPU detection.
    /// Falls back to headless mode if no GPU is available.
    /// 
/// This is the ONLY place where backend selection happens.
    /// Call this BEFORE any sceVideoOut operations.
    /// </summary>
    public static bool Initialize(uint width = 1920, uint height = 1080)
    {
        if (_initialized) 
        {
            Log.Info("VideoOutManager already initialized");
            return true;
        }
        
        _width = width;
        _height = height;
        
        PrintBackendSelectionHeader();
        
        // STAGE 1: Check if user explicitly requested headless mode
        var forceHeadless = Environment.GetEnvironmentVariable("SHARPEMU_HEADLESS");
        var gpuAvailable = HasGpuSupport();
        var forcedHeadless = string.Equals(forceHeadless, "1", StringComparison.OrdinalIgnoreCase) ||
                             string.Equals(forceHeadless, "true", StringComparison.OrdinalIgnoreCase);
        
        Console.Error.WriteLine($"[VIDEOOUT]     GPU Available: {gpuAvailable}");
        Console.Error.WriteLine($"[VIDEOOUT]     Forced Headless: {forcedHeadless}");
        
        if (forcedHeadless)
        {
            _backendReason = "Forced by SHARPEMU_HEADLESS=1";
            Console.Error.WriteLine($"[VIDEOOUT]     Reason: {_backendReason}");
            PrintBackendSelectionResult("HeadlessVideoPresenter");
            return InitializeHeadless();
        }
        
        // STAGE 2: Try to detect GPU availability
        if (!gpuAvailable)
        {
            _backendReason = "No physical GPU detected";
            Console.Error.WriteLine($"[VIDEOOUT]     Reason: {_backendReason}");
            PrintBackendSelectionResult("HeadlessVideoPresenter");
            return InitializeHeadless();
        }
        
        // STAGE 3: Use real Vulkan presenter (existing behavior)
        _backendReason = "GPU detected, using Vulkan";
        Console.Error.WriteLine($"[VIDEOOUT]     Reason: {_backendReason}");
        PrintBackendSelectionResult("VulkanVideoPresenter (default)");
        _useHeadlessMode = false;
        _initialized = true;
        return true;
    }
    
    /// <summary>
    /// Prints the backend selection header.
    /// </summary>
    private static void PrintBackendSelectionHeader()
    {
        Console.Error.WriteLine("");
        Console.Error.WriteLine("[VIDEOOUT] ============================================");
        Console.Error.WriteLine("[VIDEOOUT] Backend Selection:");
        Console.Error.WriteLine("[VIDEOOUT] ============================================");
    }
    
    /// <summary>
    /// Prints the final backend selection result.
    /// </summary>
    private static void PrintBackendSelectionResult(string backend)
    {
        Console.Error.WriteLine("");
        Console.Error.WriteLine("[VIDEOOUT] Using:");
        Console.Error.WriteLine($"[VIDEOOUT]   {backend}");
        Console.Error.WriteLine("[VIDEOOUT] ============================================");
        Console.Error.WriteLine("");
        
        Log.Info($"Backend selected: {backend} (reason: {_backendReason})");
    }

    /// <summary>
    /// Initializes headless mode directly.
    /// Creates Virtual Vulkan Device and Frame Buffer.
    /// </summary>
    public static bool InitializeHeadless()
    {
        try
        {
            var outputDir = Environment.GetEnvironmentVariable("SHARPEMU_HEADLESS_OUTPUT_DIR") ??
                              Path.Combine(Directory.GetCurrentDirectory(), "SharpEmu", "headless_frames");
            
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Initializing Headless Presenter...");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Resolution: {_width}x{_height}");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] Output Directory: {outputDir}");
            
            _headlessPresenter = new HeadlessVideoPresenter(_width, _height, outputDir);
            _useHeadlessMode = true;
            _initialized = true;
            _openTime = DateTime.UtcNow;
            
            // Create virtual device (always succeeds)
            _headlessPresenter.CreateDevice();
            
            Log.Info($"VideoOutManager initialized in HEADLESS mode: {_width}x{_height}");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] ✓ Headless Presenter initialized successfully");
            return true;
        }
        catch (Exception ex)
        {
            Log.Error($"Failed to initialize headless presenter: {ex.Message}");
            Console.Error.WriteLine($"[VIDEOOUT][HEADLESS] ✗ Failed: {ex.Message}");
            return false;
        }
    }

    /// <summary>
    /// Runs the video out system (either real or headless).
    /// </summary>
    public static void Run()
    {
        if (!_initialized)
        {
            Initialize();
        }
        
        if (_useHeadlessMode && _headlessPresenter is not null)
        {
            // In headless mode, we don't run a window loop
            // Instead, frames are captured on demand via Flip()
            Console.Error.WriteLine("[VIDEOOUT][MANAGER] Running in headless mode - no window loop");
            Log.Info("Running in headless mode");
        }
        else
        {
            // Run the real Vulkan presenter (existing behavior)
            // Note: VulkanVideoPresenter.Run() is internal, called from its own static method
            // We just need to let the existing pipeline handle it
            Console.Error.WriteLine("[VIDEOOUT][MANAGER] Using default video out mode (Vulkan)");
        }
    }

    /// <summary>
    /// Handles a flip operation from the game.
    /// Updates fake display state in headless mode.
    /// </summary>
    public static void Flip(int handle, int bufferIndex, ulong address, uint width, uint height, uint pitchInPixels, byte[]? frameData = null)
    {
        if (_useHeadlessMode && _headlessPresenter is not null)
        {
            // Update fake display state
            Interlocked.Increment(ref unchecked(_flipCount));
            _currentBuffer = bufferIndex;
            
            // Delegate to headless presenter for frame capture
            _headlessPresenter.Flip(handle, bufferIndex, address, width, height, pitchInPixels, frameData);
            
            Log.Debug($"Flip processed: handle={handle} buf={bufferIndex} frame=#{_flipCount}");
        }
        // For real Vulkan mode, the existing pipeline handles this
    }
    
    #region Fake Display API
    
    /// <summary>
    /// Allocates a fake display handle for headless mode.
    /// Games expect a valid handle from sceVideoOutOpen.
    /// </summary>
    public static int AllocateDisplayHandle()
    {
        if (!_useHeadlessMode) return -1; // Only in headless mode
        
        var handle = Interlocked.Increment(ref _fakeDisplayHandle);
        _openTime = DateTime.UtcNow;
        
        Console.Error.WriteLine($"[VIDEOOUT][FAKE] Display handle allocated: {handle}");
        Log.Info($"Fake display handle allocated: {handle}");
        
        return handle;
    }
    
    /// <summary>
    /// Gets fake display status for sceVideoOutGetFlipStatus.
    /// Games use this to check if flip completed.
    /// </summary>
    public static object GetFakeDisplayStatus(int handle)
    {
        if (!_useHeadlessMode) return null!;
        
        var elapsed = DateTime.UtcNow - _openTime;
        
        return new
        {
            display = handle,
            width = _width,
            height = _height,
            frame = _flipCount,
            flip_status = "completed",
            current_buffer = _currentBuffer,
            uptime_seconds = elapsed.TotalSeconds
        };
    }
    
    /// <summary>
    /// Checks if a display handle is valid (fake or real).
    /// </summary>
    public static bool IsValidHandle(int handle)
    {
        if (_useHeadlessMode)
        {
            // In headless mode, accept handles >= 1000 (our fake range)
            return handle >= 1000;
        }
        
        // In real mode, let the existing validation handle it
        return true;
    }
    
    #endregion

    /// <summary>
    /// Records AGC initialization for diagnostics.
    /// </summary>
    public static void OnAgcInit()
    {
        _headlessPresenter?.AgcInit();
    }

    /// <summary>
    /// Records AGC context creation for diagnostics.
    /// </summary>
    public static void OnAgcCreateContext(ulong contextAddress)
    {
        _headlessPresenter?.AgcCreateContext(contextAddress);
    }

    /// <summary>
    /// Generates and saves diagnostic report.
    /// </summary>
    public static void SaveDiagnostics()
    {
        _headlessPresenter?.SaveReport();
    }

    /// <summary>
    /// Cleans up resources.
    /// </summary>
    public static void Dispose()
    {
        _headlessPresenter?.Dispose();
        _headlessPresenter = null;
        _initialized = false;
    }

    /// <summary>
    /// Detects if GPU/Vulkan support is available.
    /// </summary>
    private static bool HasGpuSupport()
    {
        // Check environment variables first
        var noGpu = Environment.GetEnvironmentVariable("SHARPEMU_NO_GPU");
        if (string.Equals(noGpu, "1", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }
        
        // Try to detect Vulkan/GPU availability
        try
        {
            // Check for common indicators of GPU support
            if (OperatingSystem.IsLinux())
            {
                // Check for DRM/render devices
                return Directory.Exists("/dev/dri") || 
                       Directory.Exists("/sys/class/drm") ||
                       File.Exists("/proc/driver/nvidia/version");
            }
            else if (OperatingSystem.IsWindows())
            {
                // Windows usually has some form of GPU support
                // unless running in minimal environments
                return true;
            }
            else if (OperatingSystem.IsMacOS())
            {
                // macOS has Metal/MoltenVK
                return true;
            }
        }
        catch (Exception ex)
        {
            Log.Debug($"GPU detection failed: {ex.Message}");
        }
        
        // Default to assuming GPU might be available
        // Let the actual Vulkan init fail if it's not
        return true;
    }
}
