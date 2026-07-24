// ---------------------------------------------------------------------------------------------
// Copyright (c) SharpEmu Contributors. Licensed under the GPL-2.0-or-later or MIT license.
// ---------------------------------------------------------------------------------------------

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace SharpEmu.Core.Loader;

/// <summary>
/// Boot Dependency Analyzer — Rule #1 of the SharpEmu debugger.
///
/// Before any CPU instruction is executed, this class inspects the game's app0
/// directory and produces a "Boot Dependency Report" that tells the user (and
/// the rest of the debugger) whether the game package is complete enough to
/// boot. This was added after a multi-day debugging session on PPSA17697
/// (Yatzi) where the real cause of the crash turned out to be missing PRX
/// modules — not an emulator bug.
///
/// The analyzer:
///   1. Detects the game engine (Unity IL2CPP / Unity Mono / Unreal / Native C++).
///   2. Enumerates the required files for that engine.
///   3. Verifies each file's format (ELF vs SELF vs fSELF).
///   4. Reports missing files with priority ratings (★★★★★ to ★☆☆☆☆).
///   5. Computes a coverage percentage.
///   6. Recommends the next file the user should upload.
///   7. Aborts emulation (returns false from Analyze) when a CRITICAL file
///      is missing, so the rest of the debugger doesn't waste time analysing
///      a crash that's purely caused by missing data.
/// </summary>
public static class BootDependencyAnalyzer
{
    public enum Engine
    {
        UnityIl2cpp,   // Unity with IL2CPP backend (most common on PS5)
        UnityMono,     // Unity with Mono backend (rare on PS5)
        Unreal,        // Unreal Engine 4/5
        NativeCpp,     // Native C/C++ game (Dreaming Sarah, Arise, etc.)
        Unknown
    }

    public enum FilePriority
    {
        Critical,    // ★★★★★ — game cannot boot without this
        High,        // ★★★★☆ — game will boot but crash early
        Medium,      // ★★★☆☆ — game will boot but be missing major content
        Low,         // ★★☆☆☆ — game will boot but be missing optional content
        Optional     // ★☆☆☆☆ — DLC / extra languages / etc.
    }

    public record RequiredFile(
        string RelativePath,
        string Description,
        FilePriority Priority,
        bool IsDirectory = false);

    public record FileCheckResult(
        RequiredFile Spec,
        bool Present,
        long? SizeBytes,
        ExecutableFormatDetector.ExecutableFormat? Format,
        bool? IsExecutable,
        bool? IsEncrypted,
        string Status);

    public record AnalysisReport(
        string App0Root,
        Engine DetectedEngine,
        string EngineVersion,
        List<FileCheckResult> Files,
        int TotalRequired,
        int PresentCount,
        int MissingCount,
        int CriticalMissingCount,
        int CriticalEncryptedCount,
        double CoveragePercent,
        bool CanBoot,
        string? NextRequiredFile,
        List<string> Recommendations)
    {
        public bool ShouldAbort => !CanBoot && (CriticalMissingCount > 0 || CriticalEncryptedCount > 0);
    }

    // --------------------------------------------------------------------------------------------
    // Engine detection
    // --------------------------------------------------------------------------------------------

    /// <summary>
    /// Detect the game engine by inspecting which files exist in app0.
    /// </summary>
    public static (Engine engine, string version) DetectEngine(string app0Root)
    {
        if (string.IsNullOrEmpty(app0Root) || !Directory.Exists(app0Root))
        {
            return (Engine.Unknown, "unknown");
        }

        // Helper: case-insensitive file existence.
        bool FileExistsCi(string relativePath) =>
            File.Exists(Path.Combine(app0Root, relativePath)) ||
            ResolveCaseInsensitive(app0Root, relativePath) != null;

        // Unity IL2CPP markers: Il2CppUserAssemblies.prx + global-metadata.dat
        // (PS5 dumps vary in casing: "Il2Cpp" vs "Il2cpp")
        if (FileExistsCi("Media/Modules/Il2cppUserAssemblies.prx") ||
            FileExistsCi("Media/Metadata/global-metadata.dat"))
        {
            // Try to read Unity version from boot.config
            var version = "Unity IL2CPP (version unknown)";
            var bootConfigPath = Path.Combine(app0Root, "Media", "boot.config");
            if (File.Exists(bootConfigPath))
            {
                try
                {
                    var lines = File.ReadAllLines(bootConfigPath);
                    foreach (var line in lines)
                    {
                        if (line.StartsWith("unity-version=", StringComparison.OrdinalIgnoreCase))
                        {
                            version = $"Unity IL2CPP {line.Substring("unity-version=".Length).Trim()}";
                            break;
                        }
                    }
                }
                catch { /* ignore */ }
            }
            return (Engine.UnityIl2cpp, version);
        }

        // Unity Mono markers: Managed/ folder with .dll files
        var managedPath = Path.Combine(app0Root, "Media", "Managed");
        if (Directory.Exists(managedPath))
        {
            return (Engine.UnityMono, "Unity Mono");
        }

        // Unreal Engine markers: .pak files
        if (Directory.GetFiles(app0Root, "*.pak", SearchOption.AllDirectories).Length > 0)
        {
            return (Engine.Unreal, "Unreal Engine");
        }

        // Native C++ game: no Unity/Unreal markers, just eboot + PRX modules
        if (File.Exists(Path.Combine(app0Root, "eboot.bin")))
        {
            return (Engine.NativeCpp, "Native C/C++");
        }

        return (Engine.Unknown, "unknown");
    }

    // --------------------------------------------------------------------------------------------
    // Required file lists per engine
    // --------------------------------------------------------------------------------------------

    /// <summary>
    /// Returns the list of files the game needs to boot, based on its engine.
    /// </summary>
    public static List<RequiredFile> GetRequiredFiles(Engine engine)
    {
        var files = new List<RequiredFile>();

        // Every PS5 game needs an eboot.
        // NOTE: libc.prx is optional for Native C++ games because SharpEmu has
        // built-in HLE for libc functions (malloc, mutex, atexit, etc.). It IS
        // critical for Unity IL2CPP games because SharpEmu loads the real PRX
        // module to access Il2cppUserAssemblies.prx exports.
        files.Add(new RequiredFile("eboot.bin", "Main executable", FilePriority.Critical));
        files.Add(new RequiredFile("sce_sys/about/right.sprx", "About page module", FilePriority.Low));

        switch (engine)
        {
            case Engine.UnityIl2cpp:
                // Unity IL2CPP games need real PRX modules — SharpEmu loads them
                // and merges their imports/symbols.
                files.Add(new RequiredFile("sce_module/libc.prx",
                    "C runtime (SharpEmu loads as real PRX for IL2CPP)", FilePriority.Critical));
                files.Add(new RequiredFile("Media/Modules/Il2cppUserAssemblies.prx",
                    "IL2CPP compiled game code (CRITICAL — without this, no game code runs)",
                    FilePriority.Critical));
                files.Add(new RequiredFile("Media/Metadata/global-metadata.dat",
                    "IL2CPP class/method metadata (SharpEmu uses fake stubs — required only for full IL2CPP)",
                    FilePriority.High));
                files.Add(new RequiredFile("Media/Modules/PS5Util.prx",
                    "PS5 Unity utility functions", FilePriority.High));
                files.Add(new RequiredFile("Media/boot.config",
                    "Unity boot configuration", FilePriority.High));
                files.Add(new RequiredFile("Media/globalgamemanagers",
                    "Unity global game managers (scene/manger definitions)", FilePriority.Medium));
                files.Add(new RequiredFile("Media/globalgamemanagers.assets",
                    "Unity global game managers assets", FilePriority.Medium));
                files.Add(new RequiredFile("Media/RuntimeInitializeOnLoads.json",
                    "Unity runtime init callbacks", FilePriority.Low));
                files.Add(new RequiredFile("Media/ScriptingAssemblies.json",
                    "Unity scripting assembly list", FilePriority.Low));
                files.Add(new RequiredFile("Media/Resources/unity default resources",
                    "Unity built-in resources", FilePriority.Low));
                files.Add(new RequiredFile("Media/Resources/unity_builtin_extra",
                    "Unity built-in extra resources", FilePriority.Low));
                files.Add(new RequiredFile("Media/UnitySubsystems",
                    "Unity subsystem registrations directory", FilePriority.Low, IsDirectory: true));
                files.Add(new RequiredFile("Media/level0",
                    "First scene data (main menu / splash)", FilePriority.Medium));
                files.Add(new RequiredFile("Media/resources.assets",
                    "Unity Resources folder assets", FilePriority.Medium));
                files.Add(new RequiredFile("Media/sharedassets0.assets",
                    "Unity shared assets", FilePriority.Medium));
                files.Add(new RequiredFile("Media/StreamingAssets/aa",
                    "Unity Addressables StreamingAssets directory", FilePriority.Low, IsDirectory: true));
                break;

            case Engine.UnityMono:
                files.Add(new RequiredFile("Media/Managed",
                    "Unity Managed/ directory (game .dll files)", FilePriority.Critical, IsDirectory: true));
                files.Add(new RequiredFile("Media/boot.config",
                    "Unity boot configuration", FilePriority.High));
                files.Add(new RequiredFile("Media/globalgamemanagers",
                    "Unity global game managers", FilePriority.High));
                files.Add(new RequiredFile("Media/globalgamemanagers.assets",
                    "Unity global game managers assets", FilePriority.High));
                break;

            case Engine.Unreal:
                files.Add(new RequiredFile("Engine/Binaries/PS5/PS5Game.pak",
                    "Unreal engine pak file", FilePriority.Critical));
                files.Add(new RequiredFile("Paks/pakchunk0.pak",
                    "Main game pak chunk", FilePriority.Critical));
                break;

            case Engine.NativeCpp:
                // Native C++ games (Dreaming Sarah, Arise, etc.) usually only ship eboot.
                // libc.prx is OPTIONAL because SharpEmu has built-in HLE for libc
                // (C11SyncExports, CxxAbiExports, KernelRuntimeCompatExports, etc.).
                // If the game ships a real libc.prx in sce_module/, SharpEmu will load
                // it — but it's not required.
                files.Add(new RequiredFile("sce_module/libc.prx",
                    "C runtime (OPTIONAL — SharpEmu has built-in HLE for libc)",
                    FilePriority.Low));
                files.Add(new RequiredFile("sce_module/libSceNpCppWebApi.prx",
                    "PlayStation Network WebApi (if game uses PSN)", FilePriority.Low));
                break;
        }

        return files;
    }

    // --------------------------------------------------------------------------------------------
    // Format / integrity check
    // --------------------------------------------------------------------------------------------

    /// <summary>
    /// Walk each path segment case-insensitively, returning the actual on-disk
    /// path if found, or null if not. Lets the analyzer accept e.g.
    /// "Media/Modules/Il2cppUserAssemblies.prx" when the file is actually
    /// "Media/Modules/Il2CppUserAssemblies.prx".
    /// </summary>
    private static string? ResolveCaseInsensitive(string root, string relativePath)
    {
        var segments = relativePath.Replace('\\', '/').Split('/', StringSplitOptions.RemoveEmptyEntries);
        var current = root;
        foreach (var seg in segments)
        {
            if (!Directory.Exists(current)) return null;
            var match = Directory.EnumerateFileSystemEntries(current, seg,
                new EnumerationOptions { MatchCasing = MatchCasing.CaseInsensitive, MatchType = MatchType.Simple })
                .FirstOrDefault();
            if (match == null) return null;
            current = match;
        }
        return current;
    }

    private static FileCheckResult CheckFile(RequiredFile spec, string app0Root)
    {
        var fullPath = Path.Combine(app0Root, spec.RelativePath);

        // PS5 game dumps often use slightly different filename casing (e.g. "Il2Cpp"
        // vs "Il2cpp"). Use case-insensitive lookup so the analyzer doesn't false-
        // report a missing file when only the casing differs.
        if (!File.Exists(fullPath) && !Directory.Exists(fullPath))
        {
            var resolved = ResolveCaseInsensitive(app0Root, spec.RelativePath);
            if (resolved != null) fullPath = resolved;
        }

        bool present;
        long? size = null;
        try
        {
            if (spec.IsDirectory)
            {
                present = Directory.Exists(fullPath);
                if (present)
                {
                    var info = new DirectoryInfo(fullPath);
                    size = info.EnumerateFiles("*", SearchOption.AllDirectories)
                        .Sum(f => f.Length);
                }
            }
            else
            {
                present = File.Exists(fullPath);
                if (present)
                {
                    size = new FileInfo(fullPath).Length;
                }
            }
        }
        catch
        {
            present = false;
        }

        if (!present)
        {
            return new FileCheckResult(
                Spec: spec,
                Present: false,
                SizeBytes: null,
                Format: null,
                IsExecutable: null,
                IsEncrypted: null,
                Status: "MISSING");
        }

        // For executable files (eboot.bin, *.prx, *.sprx), verify the format.
        var isExecutable = spec.RelativePath.EndsWith(".bin", StringComparison.OrdinalIgnoreCase) ||
                           spec.RelativePath.EndsWith(".prx", StringComparison.OrdinalIgnoreCase) ||
                           spec.RelativePath.EndsWith(".sprx", StringComparison.OrdinalIgnoreCase) ||
                           spec.RelativePath.EndsWith(".self", StringComparison.OrdinalIgnoreCase);

        if (isExecutable && size is > 4)
        {
            try
            {
                var bytes = new byte[4];
                using (var fs = File.OpenRead(fullPath))
                {
                    fs.ReadExactly(bytes, 0, 4);
                }
                var detection = ExecutableFormatDetector.Detect(bytes.AsSpan(), spec.RelativePath);

                string status;
                if (detection.Format == ExecutableFormatDetector.ExecutableFormat.SelfEncrypted)
                    status = "ENCRYPTED — Cannot execute";
                else if (detection.Format == ExecutableFormatDetector.ExecutableFormat.Unknown)
                    status = "UNKNOWN format";
                else
                    status = $"OK ({size / 1024.0 / 1024.0:F1} MB)";

                return new FileCheckResult(
                    Spec: spec,
                    Present: true,
                    SizeBytes: size,
                    Format: detection.Format,
                    IsExecutable: detection.IsExecutable,
                    IsEncrypted: detection.IsEncrypted,
                    Status: status);
            }
            catch
            {
                return new FileCheckResult(
                    Spec: spec,
                    Present: true,
                    SizeBytes: size,
                    Format: null,
                    IsExecutable: null,
                    IsEncrypted: null,
                    Status: "READ ERROR");
            }
        }

        // Non-executable file or empty file.
        var sizeStr = size switch
        {
            > 1024 * 1024 => $"{size / 1024.0 / 1024.0:F1} MB",
            > 1024 => $"{size / 1024.0:F1} KB",
            > 0 => $"{size} bytes",
            _ => "empty"
        };
        return new FileCheckResult(
            Spec: spec,
            Present: true,
            SizeBytes: size,
            Format: null,
            IsExecutable: null,
            IsEncrypted: null,
            Status: $"OK ({sizeStr})");
    }

    // --------------------------------------------------------------------------------------------
    // Main entry point
    // --------------------------------------------------------------------------------------------

    /// <summary>
    /// Analyze the app0 directory and produce a Boot Dependency Report.
    /// </summary>
    public static AnalysisReport Analyze(string app0Root)
    {
        var (engine, version) = DetectEngine(app0Root);
        var required = GetRequiredFiles(engine);

        var results = required
            .Select(spec => CheckFile(spec, app0Root))
            .ToList();

        var totalRequired = results.Count;
        var presentCount = results.Count(r => r.Present);
        var missingCount = results.Count(r => !r.Present);
        var criticalMissingCount = results.Count(r => !r.Present && r.Spec.Priority == FilePriority.Critical);
        var criticalEncryptedCount = results.Count(r =>
            r.Present && r.IsEncrypted == true && r.Spec.Priority == FilePriority.Critical);

        var coverage = totalRequired == 0 ? 100.0 : (double)presentCount / totalRequired * 100.0;

        // Find the highest-priority missing or encrypted file (recommend it next).
        var nextMissing = results
            .Where(r => !r.Present || r.IsEncrypted == true)
            .OrderByDescending(r => (int)r.Spec.Priority)
            .FirstOrDefault();

        var recommendations = new List<string>();
        if (criticalMissingCount > 0)
        {
            recommendations.Add(
                $"{criticalMissingCount} critical file(s) MISSING — game CANNOT boot. " +
                $"Upload '{nextMissing?.Spec.RelativePath}' first.");
        }
        if (criticalEncryptedCount > 0)
        {
            recommendations.Add(
                $"{criticalEncryptedCount} critical file(s) ENCRYPTED — game CANNOT boot. " +
                $"Provide decrypted / fSELF version of: " +
                string.Join(", ", results
                    .Where(r => r.Present && r.IsEncrypted == true && r.Spec.Priority == FilePriority.Critical)
                    .Select(r => r.Spec.RelativePath)));
        }
        if (criticalMissingCount == 0 && criticalEncryptedCount == 0 && missingCount > 0)
        {
            recommendations.Add(
                $"{missingCount} non-critical file(s) missing — game may boot but be incomplete. " +
                $"Upload '{nextMissing?.Spec.RelativePath}' to improve coverage.");
        }
        if (criticalMissingCount == 0 && criticalEncryptedCount == 0 && missingCount == 0)
        {
            recommendations.Add("All required files present. Game is ready to boot.");
        }

        // Check for any encrypted executables (critical or not).
        var encryptedExecutables = results
            .Where(r => r.Present && r.IsEncrypted == true)
            .ToList();
        if (encryptedExecutables.Count > 0 && criticalEncryptedCount == 0)
        {
            recommendations.Add(
                $"{encryptedExecutables.Count} non-critical executable(s) are still ENCRYPTED and cannot run. " +
                $"Decrypted / fSELF versions required: " +
                string.Join(", ", encryptedExecutables.Select(r => r.Spec.RelativePath)));
        }

        var canBoot = criticalMissingCount == 0 && criticalEncryptedCount == 0 &&
                      !results.Any(r => r.Present && r.IsEncrypted == true && r.Spec.Priority == FilePriority.Critical);

        return new AnalysisReport(
            App0Root: app0Root ?? "(unknown)",
            DetectedEngine: engine,
            EngineVersion: version,
            Files: results,
            TotalRequired: totalRequired,
            PresentCount: presentCount,
            MissingCount: missingCount,
            CriticalMissingCount: criticalMissingCount,
            CriticalEncryptedCount: criticalEncryptedCount,
            CoveragePercent: coverage,
            CanBoot: canBoot,
            NextRequiredFile: nextMissing?.Spec.RelativePath,
            Recommendations: recommendations);
    }

    // --------------------------------------------------------------------------------------------
    // Report printing
    // --------------------------------------------------------------------------------------------

    /// <summary>
    /// Print a human-readable Boot Dependency Report to stderr.
    /// </summary>
    public static void PrintReport(AnalysisReport report)
    {
        var engineLabel = report.DetectedEngine switch
        {
            Engine.UnityIl2cpp => "Unity IL2CPP",
            Engine.UnityMono => "Unity Mono",
            Engine.Unreal => "Unreal Engine",
            Engine.NativeCpp => "Native C/C++",
            _ => "Unknown"
        };

        Console.Error.WriteLine();
        Console.Error.WriteLine("========== Boot Dependency Report ==========");
        Console.Error.WriteLine($"App0 root       : {report.App0Root}");
        Console.Error.WriteLine($"Engine          : {engineLabel}");
        Console.Error.WriteLine($"Engine detail   : {report.EngineVersion}");
        Console.Error.WriteLine($"Coverage        : {report.CoveragePercent:F1}% ({report.PresentCount}/{report.TotalRequired} required files present)");
        Console.Error.WriteLine($"Critical miss   : {report.CriticalMissingCount}");
        Console.Error.WriteLine($"Critical encrypt: {report.CriticalEncryptedCount}");
        Console.Error.WriteLine($"Can boot        : {(report.CanBoot ? "YES" : "NO")}");
        Console.Error.WriteLine();
        Console.Error.WriteLine("Required files:");
        Console.Error.WriteLine();
        // Verbose per-file report (Magic/Encrypted/Loadable) — per user's Rule #002 request.
        foreach (var file in report.Files)
        {
            var priorityLabel = file.Spec.Priority switch
            {
                FilePriority.Critical => "★★★★★",
                FilePriority.High => "★★★★☆",
                FilePriority.Medium => "★★★☆☆",
                FilePriority.Low => "★★☆☆☆",
                _ => "★☆☆☆☆"
            };
            Console.Error.WriteLine($"  [{priorityLabel}] {file.Spec.RelativePath}");
            Console.Error.WriteLine($"      Path       : {file.Spec.RelativePath}");
            Console.Error.WriteLine($"      Description: {file.Spec.Description}");
            Console.Error.WriteLine($"      Exists     : {(file.Present ? "YES" : "NO")}");
            if (file.Present)
            {
                Console.Error.WriteLine($"      Size       : {FormatSize(file.SizeBytes)}");
                if (file.Format.HasValue)
                {
                    Console.Error.WriteLine($"      Magic      : 0x{GetMagicFromFormat(file.Format.Value):X8}");
                    Console.Error.WriteLine($"      Format     : {FormatLabel(file.Format.Value)}");
                    Console.Error.WriteLine($"      Encrypted  : {(file.IsEncrypted == true ? "YES" : "NO")}");
                    Console.Error.WriteLine($"      Loadable   : {(file.IsEncrypted == true ? "NO (encrypted)" : "YES")}");
                }
            }
            Console.Error.WriteLine($"      Priority   : {file.Spec.Priority}");
            Console.Error.WriteLine($"      Status     : {file.Status}");
            Console.Error.WriteLine();
        }

        Console.Error.WriteLine();
        Console.Error.WriteLine("Recommendations:");
        foreach (var rec in report.Recommendations)
        {
            Console.Error.WriteLine($"  • {rec}");
        }

        if (report.NextRequiredFile != null)
        {
            Console.Error.WriteLine();
            Console.Error.WriteLine($"Next required file to upload: {report.NextRequiredFile}");
        }
        Console.Error.WriteLine("============================================");
        Console.Error.WriteLine();
    }

    private static string FormatLabel(ExecutableFormatDetector.ExecutableFormat format) => format switch
    {
        ExecutableFormatDetector.ExecutableFormat.Elf => "ELF",
        ExecutableFormatDetector.ExecutableFormat.SelfDecrypted => "SELF(fSELF)",
        ExecutableFormatDetector.ExecutableFormat.SelfEncrypted => "SELF",
        _ => "Unknown"
    };

    private static uint GetMagicFromFormat(ExecutableFormatDetector.ExecutableFormat format) => format switch
    {
        ExecutableFormatDetector.ExecutableFormat.Elf => 0x7F454C46,
        ExecutableFormatDetector.ExecutableFormat.SelfDecrypted => 0x4F153D1D,
        ExecutableFormatDetector.ExecutableFormat.SelfEncrypted => 0x5414F5EE,
        _ => 0
    };

    private static string FormatSize(long? bytes)
    {
        if (!bytes.HasValue) return "(unknown)";
        var b = bytes.Value;
        if (b >= 1024 * 1024) return $"{b / 1024.0 / 1024.0:F1} MB";
        if (b >= 1024) return $"{b / 1024.0:F1} KB";
        if (b > 0) return $"{b} bytes";
        return "empty";
    }
}
