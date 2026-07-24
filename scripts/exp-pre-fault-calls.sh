#!/bin/bash
# EXP-PRE-FAULT-CALLS
# Trace ALL HLE import calls between "VideoOut ready" and the first UNMAPPED fault
# in Yatzi, to identify what Unity was trying to do before going into error state.
set -uo pipefail

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/x11/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_APP0_DIR=/tmp/games/yatzi
export SHARPEMU_WRITABLE_APP0=1
export SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1
# Enable the SHARPEMU_TRACE_IMPORTS-style trace if it exists
# Actually we need to grep for "Import#" or "[LOADER][TRACE] Import#" lines

LOG=/tmp/exp-pre-fault-calls.log
rm -f "$LOG"
echo "Running Yatzi for 10s..."
timeout 10 /home/z/my-project/work/sharpemu-build/SharpEmu \
    --log-level=info /tmp/games/yatzi/eboot.bin > "$LOG" 2>&1 || true

# Find line numbers
VO_READY=$(grep -n "Vulkan VideoOut ready" "$LOG" | head -1 | cut -d: -f1)
FAULT=$(grep -n "UNMAPPED.*#1" "$LOG" | head -1 | cut -d: -f1)

echo "VideoOut ready at line: $VO_READY"
echo "First UNMAPPED fault at line: $FAULT"
echo ""

if [ -z "$VO_READY" ] || [ -z "$FAULT" ]; then
  echo "Could not find both events"
  exit 1
fi

# Extract all HLE import trace lines between these two events
echo "=== HLE import calls between VideoOut ready and first UNMAPPED fault ==="
sed -n "${VO_READY},${FAULT}p" "$LOG" | grep -E "Import#|HLE\]|LOADER.*Import" | head -80
echo ""
echo "=== Total HLE trace lines in window: $(sed -n "${VO_READY},${FAULT}p" "$LOG" | grep -cE "Import#|HLE\]|LOADER.*Import") ==="
echo ""
echo "=== Other events between VideoOut ready and first fault: ==="
sed -n "${VO_READY},${FAULT}p" "$LOG" | head -50
