#!/usr/bin/env python3
"""EXP-037: Apply instrumentation patches."""
import sys
from pathlib import Path

REPO = Path("/tmp/my-project/work/sharpemuT24")
EXCEPTIONS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Exceptions.cs"
IMPORTS = REPO / "src/SharpEmu.Core/Cpu/Native/DirectExecutionBackend.Imports.cs"


def patch_exceptions():
    src = EXCEPTIONS.read_text()
    original = src

    if "Exp037TryHandleWatchpointInt3" in src:
        print("[SKIP] Exceptions already patched for EXP-037")
        return

    # Add EXP-037 check before EXP-036 check
    old = """                        // EXP-036: Handle INT3 from il2cpp_init (traces ENTER).
                        // Must be checked before EXP-035 since both use SIGTRAP.
                        if (exceptionCode == 2147483651u && Exp036TryHandleIl2cppInitInt3(contextRecord, rip))
                        {
                                return -1;
                        }"""

    new = """                        // EXP-037: Handle INT3 from global pointer watchpoints.
                        if (exceptionCode == 2147483651u && Exp037TryHandleWatchpointInt3(contextRecord, rip))
                        {
                                return -1;
                        }
                        // EXP-036: Handle INT3 from il2cpp_init (traces ENTER).
                        // Must be checked before EXP-035 since both use SIGTRAP.
                        if (exceptionCode == 2147483651u && Exp036TryHandleIl2cppInitInt3(contextRecord, rip))
                        {
                                return -1;
                        }"""

    if old in src:
        src = src.replace(old, new)
        print("[OK] Patched VectoredHandler (added EXP-037 watchpoint check)")
    else:
        print("[FAIL] Could not find EXP-036 insertion point")
        sys.exit(1)

    if src != original:
        EXCEPTIONS.write_text(src)
        print(f"[WRITE] {EXCEPTIONS}")


def patch_imports():
    src = IMPORTS.read_text()
    original = src

    if "Exp037InstallWatchpoints" in src:
        print("[SKIP] Imports already patched for EXP-037")
        return

    # Add Exp037InstallWatchpoints() call right after Exp036PatchIl2cppInit()
    old = """                                    // EXP-036: Patch il2cpp_init with INT3 to trace when it's called.
                                    // il2cpp_init = global[0] = 0x804ED85D0
                                    Exp036PatchIl2cppInit();
                                }"""

    new = """                                    // EXP-036: Patch il2cpp_init with INT3 to trace when it's called.
                                    // il2cpp_init = global[0] = 0x804ED85D0
                                    Exp036PatchIl2cppInit();

                                    // EXP-037: Install watchpoints for the NULL global pointer at 0x801E51240.
                                    // The crash is at 0x80135DE83: mov ecx, [rax+0x98] where rax comes from
                                    // the global at 0x801E51240. We patch the WRITE site (0x8013EF019)
                                    // with INT3 to trace when the global is initialized.
                                    Exp037InstallWatchpoints();
                                }"""

    if old in src:
        src = src.replace(old, new)
        print("[OK] Patched Imports (added Exp037InstallWatchpoints call)")
    else:
        print("[FAIL] Could not find Exp036PatchIl2cppInit call")
        sys.exit(1)

    if src != original:
        IMPORTS.write_text(src)
        print(f"[WRITE] {IMPORTS}")


if __name__ == "__main__":
    patch_exceptions()
    print()
    patch_imports()
    print()
    print("[DONE] EXP-037 patches applied")
