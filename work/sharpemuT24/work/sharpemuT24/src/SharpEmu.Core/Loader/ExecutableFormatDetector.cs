// ---------------------------------------------------------------------------------------------
// Copyright (c) SharpEmu Contributors. Licensed under the GPL-2.0-or-later or MIT license.
// ---------------------------------------------------------------------------------------------

using System;
using System.IO;

namespace SharpEmu.Core.Loader;

/// <summary>
/// Detects the format of a PlayStation executable file (eboot.bin, *.self, *.sprx, *.prx)
/// by inspecting its leading bytes. Prints a one-line summary to stderr so that the
/// emulator log shows the file's encrypted/decrypted status up-front, before any
/// further parsing happens. This makes it obvious when a still-encrypted retail eboot
/// is being loaded (SharpEmu cannot decrypt) versus a properly decrypted ELF.
/// </summary>
public static class ExecutableFormatDetector
{
    // Big-endian "\x7fELF" — read via BinaryPrimitives.ReadUInt32BigEndian.
    private const uint ElfMagic = 0x7F454C46;

    // SELF magic (encrypted retail SELF, e.g. eboot.bin straight from a .pkg dump).
    private const uint SelfMagicEncrypted = 0x5414F5EE;

    // fSELF magic (fake-signed decrypted SELF — produced by PS5 decryption tools).
    private const uint SelfMagicDecrypted = 0x4F153D1D;

    public enum ExecutableFormat
    {
        Elf,           // 7F 45 4C 46 — standard decrypted ELF
        SelfDecrypted, // 4F 15 3D 1D — fSELF (decrypted fake-signed SELF)
        SelfEncrypted, // 54 14 F5 EE — still-encrypted retail SELF (cannot execute)
        Unknown
    }

    public record DetectionResult(
        string FileName,
        ExecutableFormat Format,
        uint Magic,
        bool IsExecutable,
        bool IsEncrypted,
        string Status);

    /// <summary>
    /// Inspect the first 4 bytes of <paramref name="data"/> and return the detected
    /// format. The result is also logged to <see cref="Console.Error"/> in a
    /// standard one-line format that the user's Feature Request asked for:
    ///
    ///   [FORMAT] eboot.bin magic=7F454C46 ELF Decrypted Ready
    ///   [FORMAT] Il2cppUserAssemblies.prx magic=5414F5EE SELF Encrypted Cannot execute
    ///
    /// </summary>
    public static DetectionResult DetectAndLog(ReadOnlySpan<byte> data, string fileName)
    {
        var result = Detect(data, fileName);
        Console.Error.WriteLine(
            $"[FORMAT] {result.FileName} magic=0x{result.Magic:X8} " +
            $"{FormatLabel(result.Format)} " +
            $"{(result.IsEncrypted ? "Encrypted" : "Decrypted")} " +
            $"{result.Status}");
        return result;
    }

    /// <summary>
    /// Inspect the first 4 bytes of <paramref name="data"/> and return the detected
    /// format without logging. Useful when callers want to check the format
    /// programmatically.
    /// </summary>
    public static DetectionResult Detect(ReadOnlySpan<byte> data, string fileName)
    {
        if (data.Length < 4)
        {
            return new DetectionResult(
                FileName: fileName,
                Format: ExecutableFormat.Unknown,
                Magic: 0,
                IsExecutable: false,
                IsEncrypted: false,
                Status: "Too small");
        }

        // Read as big-endian so the magic constants above match the byte order
        // shown by `xxd file.bin | head -1` on disk.
        var magic = ((uint)data[0] << 24) | ((uint)data[1] << 16) | ((uint)data[2] << 8) | data[3];

        return magic switch
        {
            ElfMagic => new DetectionResult(
                FileName: fileName,
                Format: ExecutableFormat.Elf,
                Magic: magic,
                IsExecutable: true,
                IsEncrypted: false,
                Status: "Ready"),
            SelfMagicDecrypted => new DetectionResult(
                FileName: fileName,
                Format: ExecutableFormat.SelfDecrypted,
                Magic: magic,
                IsExecutable: true,
                IsEncrypted: false,
                Status: "Ready (fSELF)"),
            SelfMagicEncrypted => new DetectionResult(
                FileName: fileName,
                Format: ExecutableFormat.SelfEncrypted,
                Magic: magic,
                IsExecutable: false,
                IsEncrypted: true,
                Status: "Cannot execute (still encrypted — needs decryption keys)"),
            _ => new DetectionResult(
                FileName: fileName,
                Format: ExecutableFormat.Unknown,
                Magic: magic,
                IsExecutable: false,
                IsEncrypted: false,
                Status: "Unknown format")
        };
    }

    private static string FormatLabel(ExecutableFormat format) => format switch
    {
        ExecutableFormat.Elf => "ELF",
        ExecutableFormat.SelfDecrypted => "SELF(fSELF)",
        ExecutableFormat.SelfEncrypted => "SELF",
        _ => "Unknown"
    };
}
