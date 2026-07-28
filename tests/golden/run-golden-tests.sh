#!/bin/bash
set -euo pipefail

SHARPEMU_BIN="${SHARPEMU_BIN:-/home/z/my-project/work/sharpemu-build/SharpEmu}"
GAME_DIR="${GAME_DIR:-/tmp/games/dreaming-sarah/PPSA02929-app0}"
EBOOT="${EBOOT:-$GAME_DIR/eboot.bin}"
VULKAN_ICD="${VULKAN_ICD:-/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json}"
VULKAN_LIB="${VULKAN_LIB:-/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu}"
X11_LIB="${X11_LIB:-/home/z/.local/x11/usr/lib/x86_64-linux-gnu}"
FRAMEBUFFER_DIR="${FRAMEBUFFER_DIR:-/tmp/golden-framebuffers}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-30}"
MIN_FRAMES=50
MIN_COLORS=50

echo "============================================"
echo "  SharpEmuT24 Golden Game Validation"
echo "============================================"
echo ""

if [ ! -f "$SHARPEMU_BIN" ]; then echo "FAIL: binary not found"; exit 1; fi
if [ ! -f "$EBOOT" ]; then echo "FAIL: eboot not found"; exit 1; fi

if ! pgrep -f "Xvfb :99" > /dev/null 2>&1; then
    pkill -9 Xvfb 2>/dev/null || true; sleep 1
    rm -f /tmp/.X*-lock /tmp/.X11-unix/X* 2>/dev/null
    mkdir -p /tmp/.X11-unix /tmp/xdg; chmod 1777 /tmp/.X11-unix /tmp/xdg
    nohup setsid Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null &
    disown; sleep 3
fi

rm -rf "$FRAMEBUFFER_DIR"
mkdir -p "$FRAMEBUFFER_DIR"
LOG_FILE="/tmp/golden-test.log"

export VK_ICD_FILENAMES="$VULKAN_ICD"
export LD_LIBRARY_PATH="$X11_LIB:$VULKAN_LIB:$(dirname $SHARPEMU_BIN):${LD_LIBRARY_PATH:-}"
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_APP0_DIR="$GAME_DIR"
export SHARPEMU_TRACE_GUEST_IMAGES=present
export SHARPEMU_GUEST_IMAGE_DUMP_DIR="$FRAMEBUFFER_DIR"
export SHARPEMU_GUEST_IMAGE_DUMP_CONTINUOUS=1
unset SHARPEMU_HEADLESS
unset SHARPEMU_SEMA_FAST_PATH

echo "Running Dreaming Sarah (${TIMEOUT_SECONDS}s)..."
timeout "$TIMEOUT_SECONDS" "$SHARPEMU_BIN" --log-level=info "$EBOOT" > "$LOG_FILE" 2>&1 || true

echo ""
echo "============================================"

PASS=true

if grep -q "GLFW windowing platform in use: X11" "$LOG_FILE"; then
    echo "✅ PASS: GLFW X11 backend selected"
else
    echo "❌ FAIL: GLFW X11 backend not selected"
    PASS=false
fi

if grep -q "Vulkan VideoOut ready" "$LOG_FILE"; then
    echo "✅ PASS: Vulkan VideoOut initialized"
else
    echo "❌ FAIL: Vulkan VideoOut not initialized"
    PASS=false
fi

FRAME_COUNT=$(ls "$FRAMEBUFFER_DIR"/*.bgra 2>/dev/null | wc -l)
echo "Frame count: $FRAME_COUNT (min: $MIN_FRAMES)"
if [ "$FRAME_COUNT" -ge "$MIN_FRAMES" ]; then
    echo "✅ PASS: Sufficient frames"
else
    echo "❌ FAIL: Not enough frames"
    PASS=false
fi

MAX_COLORS=$(python3 -c "
import os
from PIL import Image
fb_dir = '$FRAMEBUFFER_DIR'
files = sorted([f for f in os.listdir(fb_dir) if f.endswith('.bgra')])
mc = 0
for f in files[-20:]:
    with open(os.path.join(fb_dir, f), 'rb') as fh:
        data = fh.read()
    if len(data) != 1280*720*4: continue
    img = Image.frombytes('RGBA', (1280, 720), data, 'raw', 'BGRA')
    pixels = list(img.getdata())
    d = len(set(pixels))
    if d > mc:
        mc = d
        bf = f
        bdata = data
if mc > 0:
    img = Image.frombytes('RGBA', (1280, 720), bdata, 'raw', 'BGRA')
    img.save('/home/z/my-project/download/golden-test-best-frame.png')
print(mc)
" 2>/dev/null || echo "0")

echo "Max distinct colors: $MAX_COLORS (min: $MIN_COLORS)"
if [ "$MAX_COLORS" -ge "$MIN_COLORS" ]; then
    echo "✅ PASS: Real game content detected"
else
    echo "❌ FAIL: Not enough distinct colors"
    PASS=false
fi

echo ""
if [ "$PASS" = "true" ]; then
    echo "============================================"
    echo "  ✅ GOLDEN TEST PASSED"
    echo "============================================"
    echo "Dreaming Sarah is rendering correctly."
    exit 0
else
    echo "============================================"
    echo "  ❌ GOLDEN TEST FAILED"
    echo "============================================"
    echo "Do NOT merge this change."
    exit 1
fi
