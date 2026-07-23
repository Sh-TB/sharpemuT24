// ---------------------------------------------------------------------------------------------
// Copyright (c) SharpEmu Contributors. Licensed under the GPL-2.0-or-later or MIT license.
// ---------------------------------------------------------------------------------------------

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace SharpEmu.Libs.VideoOut;

/// <summary>
/// Frame Analyzer — classifies a headless RGBA8 frame dump and reports what kind
/// of content the game actually produced.
///
/// The user's goal: stop celebrating "first frame produced" when the frame is just
/// a single solid color (Unity splash background). This class inspects the frame
/// and classifies it as:
///
///   • Uniform Splash Frame (one color covers >95% of pixels)
///   • Multi-color Content Frame (real scene/menu/UI is rendering)
///   • Black Frame (GPU produced nothing)
///   • White Frame (likely a clear-color frame, no rendering)
///   • Unknown
///
/// Then prints a "Framebuffer Analysis" report that explains what this means for
/// debugging: e.g. "GPU OK, VideoOut OK, but Scene not yet rendered".
/// </summary>
public static class FrameAnalyzer
{
    public enum FrameClassification
    {
        UniformSplashFrame,    // >95% of pixels are the same color
        BlackFrame,            // >95% black
        WhiteFrame,            // >95% white
        MultiColorContent,     // many distinct colors — real rendering
        PartialContent,        // 50-95% one color, rest varied
        Empty,                 // frame too small
        Unknown
    }

    public record FrameAnalysis(
        string FrameFile,
        int Width,
        int Height,
        string Format,
        long PixelCount,
        (byte R, byte G, byte B, byte A) DominantColor,
        double DominantCoverage,
        int DistinctColorCount,
        FrameClassification Classification,
        string ClassificationLabel,
        List<ColorSample> TopColors,
        string Conclusion,
        List<string> NextSteps)
    {
        public bool IsRealContent => Classification == FrameClassification.MultiColorContent;
    }

    /// <summary>
    /// A sampled color and how many times it appeared in the sampled subset.
    /// </summary>
    public record ColorSample(byte R, byte G, byte B, byte A, long Count);

    // --------------------------------------------------------------------------------------------
    // Analyze a PPM frame file
    // --------------------------------------------------------------------------------------------

    /// <summary>
    /// Analyze a PPM frame file and produce a FrameAnalysis. Returns null if the
    /// file cannot be parsed.
    /// </summary>
    public static FrameAnalysis? AnalyzePpm(string ppmPath)
    {
        if (!File.Exists(ppmPath)) return null;

        byte[] data;
        try { data = File.ReadAllBytes(ppmPath); }
        catch { return null; }

        if (data.Length < 16) return null;

        // Parse PPM header. Format is "P6\n#comment\nWIDTH HEIGHT\nMAXVAL\nRAWDATA".
        // The SharpEmu headless presenter puts a "draws=" comment in the dims line.
        int pos = 0;
        if (data[0] != (byte)'P' || data[1] != (byte)'6') return null;
        pos = 2;

        int width = 0, height = 0;
        // Skip whitespace/comments, read 3 integers (width, height, maxval).
        int[] values = new int[3];
        int vi = 0;
        while (vi < 3 && pos < data.Length)
        {
            // Skip whitespace
            while (pos < data.Length && (data[pos] == (byte)' ' || data[pos] == (byte)'\n' ||
                                          data[pos] == (byte)'\r' || data[pos] == (byte)'\t'))
                pos++;
            // Skip comment line
            if (pos < data.Length && data[pos] == (byte)'#')
            {
                while (pos < data.Length && data[pos] != (byte)'\n') pos++;
                continue;
            }
            // Read integer
            int val = 0;
            bool any = false;
            while (pos < data.Length && data[pos] >= (byte)'0' && data[pos] <= (byte)'9')
            {
                val = val * 10 + (data[pos] - (byte)'0');
                pos++;
                any = true;
            }
            if (any) values[vi++] = val;
            else break;
        }

        // Skip single whitespace byte after maxval (per PPM spec).
        if (pos < data.Length) pos++;

        width = values[0];
        height = values[1];
        if (width <= 0 || height <= 0) return null;

        // SharpEmu's headless presenter writes RGBA8 (4 bytes per pixel) but labels
        // the PPM as P6 (RGB). The pixel data length tells us the truth.
        int bytesPerPixel = 3;
        long expectedRgb = (long)width * height * 3;
        long expectedRgba = (long)width * height * 4;
        long remaining = data.Length - pos;
        if (remaining >= expectedRgba - 4 && remaining <= expectedRgba + 16)
            bytesPerPixel = 4;
        else if (remaining < expectedRgb - 16)
            return null;  // not enough data

        // Sample pixels (every Nth pixel) to compute color statistics.
        // Sampling is good enough for splash detection and much faster than
        // walking every pixel.
        long totalPixels = (long)width * height;
        int sampleStride = (int)Math.Max(1, totalPixels / 50000);  // ~50k samples
        var colorCounts = new Dictionary<uint, long>();
        long sampled = 0;
        for (long i = 0; i < totalPixels; i += sampleStride)
        {
            long offset = pos + i * bytesPerPixel;
            if (offset + bytesPerPixel > data.Length) break;
            byte r = data[offset], g = data[offset + 1], b = data[offset + 2];
            byte a = bytesPerPixel == 4 ? data[offset + 3] : (byte)255;
            // Quantize slightly to merge near-identical colors (anti-JPEG, anti-dithering).
            r = (byte)((r >> 3) << 3);
            g = (byte)((g >> 3) << 3);
            b = (byte)((b >> 3) << 3);
            a = (byte)((a >> 4) << 4);
            uint key = ((uint)r << 24) | ((uint)g << 16) | ((uint)b << 8) | a;
            colorCounts[key] = colorCounts.GetValueOrDefault(key) + 1;
            sampled++;
        }

        var topColors = colorCounts
            .OrderByDescending(c => c.Value)
            .Take(5)
            .Select(c => new ColorSample(
                R: (byte)((c.Key >> 24) & 0xFF),
                G: (byte)((c.Key >> 16) & 0xFF),
                B: (byte)((c.Key >> 8) & 0xFF),
                A: (byte)(c.Key & 0xFF),
                Count: c.Value))
            .ToList();

        var dominant = topColors[0];
        double dominantCoverage = sampled > 0 ? (double)dominant.Count / sampled : 0;

        // Classify the frame.
        var classification = Classify(dominant, dominantCoverage, colorCounts.Count);
        var (label, conclusion, nextSteps) = InterpretClassification(classification, dominant);

        return new FrameAnalysis(
            FrameFile: Path.GetFileName(ppmPath),
            Width: width,
            Height: height,
            Format: bytesPerPixel == 4 ? "RGBA8" : "RGB8",
            PixelCount: totalPixels,
            DominantColor: (dominant.R, dominant.G, dominant.B, dominant.A),
            DominantCoverage: dominantCoverage,
            DistinctColorCount: colorCounts.Count,
            Classification: classification,
            ClassificationLabel: label,
            TopColors: topColors,
            Conclusion: conclusion,
            NextSteps: nextSteps);
    }

    private static FrameClassification Classify(
        ColorSample dominant,
        double dominantCoverage,
        int distinctColors)
    {
        if (distinctColors <= 1) return FrameClassification.Empty;

        // Check for solid black / white first.
        if (dominant.R == 0 && dominant.G == 0 && dominant.B == 0 && dominantCoverage > 0.95)
            return FrameClassification.BlackFrame;
        if (dominant.R >= 250 && dominant.G >= 250 && dominant.B >= 250 && dominantCoverage > 0.95)
            return FrameClassification.WhiteFrame;

        if (dominantCoverage > 0.95)
            return FrameClassification.UniformSplashFrame;
        if (dominantCoverage > 0.50)
            return FrameClassification.PartialContent;
        if (distinctColors > 100)
            return FrameClassification.MultiColorContent;
        return FrameClassification.Unknown;
    }

    private static (string label, string conclusion, List<string> nextSteps) InterpretClassification(
        FrameClassification cls,
        ColorSample dominant)
    {
        return cls switch
        {
            FrameClassification.UniformSplashFrame => (
                "Unity Splash Frame",
                $"GPU OK, VideoOut OK, but Scene NOT loaded. Frame is single-color ({dominant.R},{dominant.G},{dominant.B}).",
                new List<string> {
                    "Upload Media/level0 (main scene file)",
                    "Upload Media/globalgamemanagers + .assets (Unity scene/manger definitions)",
                    "Upload Media/resources.assets (Resources folder assets)",
                    "Upload Media/sharedassets0.assets (shared scene assets)",
                    "Upload Media/Metadata/global-metadata.dat (IL2CPP class registry)",
                    "Investigate: is Camera clear color set to the splash color?",
                    "Check: are Unity scenes being loaded by the IL2CPP runtime?",
                    "Check: are AssetBundle references being resolved?"
                }),
            FrameClassification.BlackFrame => (
                "Black Frame",
                "GPU produced nothing visible. Possibly VideoOut was initialized but no draw calls were submitted.",
                new List<string> {
                    "Verify GPU pipeline is being initialized",
                    "Check: is the swapchain being flipped correctly?",
                    "Verify: are draw calls being submitted?",
                    "Investigate: is the renderer stuck in initialization?"
                }),
            FrameClassification.WhiteFrame => (
                "White Frame",
                "Frame is white. Likely a Camera with white clear color, or framebuffer not cleared.",
                new List<string> {
                    "Check: is the Camera's clear color set to white?",
                    "Verify: is the framebuffer being cleared each frame?",
                    "Investigate: is the renderer submitting any draws?"
                }),
            FrameClassification.PartialContent => (
                "Partial Content Frame",
                "Some content is rendering but the frame is mostly a single color. The scene may be partially loaded.",
                new List<string> {
                    "Examine what the non-dominant pixels are (UI text? logo? loading bar?)",
                    "Check: is the scene loading in the background?",
                    "Verify: are materials/textures being uploaded to GPU?",
                    "Investigate: shader compilation may be incomplete"
                }),
            FrameClassification.MultiColorContent => (
                "Multi-Color Content Frame",
                "🎉 Real game content is rendering! Scene is loaded and rendering.",
                new List<string> {
                    "Save this frame as a milestone",
                    "Compare next frames to ensure the game continues to progress",
                    "Begin investigating: is input being handled correctly?",
                    "Check: does the game accept controller input?"
                }),
            FrameClassification.Empty => (
                "Empty Frame",
                "Frame data is too small to analyze.",
                new List<string> { "Verify the frame was written correctly" }),
            _ => (
                "Unknown Frame Type",
                "Frame does not match any known pattern.",
                new List<string> { "Inspect frame manually" })
        };
    }

    // --------------------------------------------------------------------------------------------
    // Report printing
    // --------------------------------------------------------------------------------------------

    public static void PrintReport(FrameAnalysis analysis)
    {
        Console.Error.WriteLine();
        Console.Error.WriteLine("========== Framebuffer Analysis ==========");
        Console.Error.WriteLine($"Frame file        : {analysis.FrameFile}");
        Console.Error.WriteLine($"Resolution        : {analysis.Width}x{analysis.Height}");
        Console.Error.WriteLine($"Format            : {analysis.Format}");
        Console.Error.WriteLine($"Pixel count       : {analysis.PixelCount:N0}");
        Console.Error.WriteLine($"Distinct colors   : {analysis.DistinctColorCount}");
        Console.Error.WriteLine($"Dominant color    : RGB({analysis.DominantColor.R},{analysis.DominantColor.G},{analysis.DominantColor.B}) α={analysis.DominantColor.A}");
        Console.Error.WriteLine($"Dominant coverage : {analysis.DominantCoverage * 100:F2}%");
        Console.Error.WriteLine($"Classification    : {analysis.ClassificationLabel}");
        Console.Error.WriteLine();
        Console.Error.WriteLine("Top colors:");
        foreach (var c in analysis.TopColors)
        {
            var pct = analysis.PixelCount > 0 ? (double)c.Count / (analysis.PixelCount / Math.Max(1, analysis.PixelCount / 50000)) * 100 : 0;
            // Recompute pct properly: TopColors counts are from the sampled subset.
            var sampled = analysis.TopColors.Sum(x => x.Count);
            var truePct = sampled > 0 ? (double)c.Count / sampled * 100 : 0;
            Console.Error.WriteLine($"  RGB({c.R,3},{c.G,3},{c.B,3}) α={c.A,3}  {truePct,6:F2}%  ({c.Count:N0} samples)");
        }
        Console.Error.WriteLine();
        Console.Error.WriteLine($"Conclusion        : {analysis.Conclusion}");
        Console.Error.WriteLine();
        Console.Error.WriteLine("Next steps:");
        foreach (var s in analysis.NextSteps)
            Console.Error.WriteLine($"  • {s}");
        Console.Error.WriteLine("==========================================");
        Console.Error.WriteLine();
    }
}
