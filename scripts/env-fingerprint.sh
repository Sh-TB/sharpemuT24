#!/bin/bash
# env-fingerprint.sh — Capture environment state for reproducibility
#
# Run before every debug session to document the exact environment.
# Output: EXP_ENVIRONMENT_TIMESTAMP.txt

set -euo pipefail

TS=$(date -u +%Y%m%d_%H%M%S)
OUT="EXP_ENVIRONMENT_${TS}.txt"

echo "=== SharpEmuT24 Environment Fingerprint ===" > "$OUT"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT"
echo "" >> "$OUT"

echo "--- OS ---" >> "$OUT"
uname -a >> "$OUT"
cat /etc/os-release 2>/dev/null | head -3 >> "$OUT"
echo "" >> "$OUT"

echo "--- .NET SDK ---" >> "$OUT"
dotnet --version 2>&1 >> "$OUT" || echo "MISSING" >> "$OUT"
echo "" >> "$OUT"

echo "--- Git ---" >> "$OUT"
cd /tmp/my-project/work/sharpemuT24 2>/dev/null
git log -1 --oneline >> "$OUT" 2>&1
git branch -vv >> "$OUT" 2>&1
echo "" >> "$OUT"

echo "--- Display ---" >> "$OUT"
echo "DISPLAY=$DISPLAY" >> "$OUT"
echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR" >> "$OUT"
pgrep -af Xvfb >> "$OUT" 2>&1 || echo "Xvfb: NOT RUNNING" >> "$OUT"
ls /tmp/.X11-unix/ >> "$OUT" 2>&1 || echo "No X11 sockets" >> "$OUT"
echo "" >> "$OUT"

echo "--- Vulkan ---" >> "$OUT"
echo "VK_ICD_FILENAMES=$VK_ICD_FILENAMES" >> "$OUT"
ls -la "$VK_ICD_FILENAMES" 2>&1 >> "$OUT"
echo "" >> "$OUT"

echo "--- Games ---" >> "$OUT"
echo "Yatzi: $(file /tmp/games/yatzi/eboot.bin 2>&1 | grep -oE 'ELF [0-9-]+ bit' || echo MISSING)" >> "$OUT"
echo "DS:    $(file /tmp/games/dreaming-sarah/PPSA02929-app0/eboot.bin 2>&1 | grep -oE 'ELF [0-9-]+ bit' || echo MISSING)" >> "$OUT"
echo "" >> "$OUT"

echo "--- SharpEmu Build ---" >> "$OUT"
EMU=/tmp/my-project/work/sharpemuT24/artifacts/bin/Release/net10.0/linux-x64/SharpEmu
if [ -f "$EMU" ]; then
    echo "Binary: EXISTS ($(stat -c%y "$EMU" | cut -d. -f1))" >> "$OUT"
    strings "$EMU" 2>/dev/null | grep -c "Exp028" >> "$OUT" 2>&1 && echo "Exp028 strings found" >> "$OUT" || echo "No Exp028 strings" >> "$OUT"
else
    echo "Binary: NOT BUILT" >> "$OUT"
fi
echo "" >> "$OUT"

echo "--- Environment Variables ---" >> "$OUT"
env | grep -E "SHARPEMU|DOTNET|VK_|DISPLAY|LD_LIBRARY" | sort >> "$OUT"

echo ""
echo "Environment fingerprint saved: $OUT"
cat "$OUT"
