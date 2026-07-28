#!/bin/bash
# test-game.sh — run a single game under SharpEmu with a timeout, capture log
# Usage: ./test-game.sh <game-name> <app0-dir> [timeout]
set -u
GAME_NAME="$1"
APP0_DIR="$2"
TIMEOUT="${3:-90}"

LOG_DIR="/home/z/my-project/work/sharpemu-build/logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$LOG_DIR/${GAME_NAME}-${TS}.log"

# Ensure Xvfb is running on display :99
if ! pgrep -f "Xvfb :99" > /dev/null 2>&1; then
    pkill -9 Xvfb 2>/dev/null; sleep 1
    rm -f /tmp/.X*-lock /tmp/.X11-unix/X* 2>/dev/null
    mkdir -p /tmp/.X11-unix /tmp/xdg; chmod 1777 /tmp/.X11-unix /tmp/xdg
    nohup setsid Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null &
    disown; sleep 3
fi

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/glfw-deps/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build:${LD_LIBRARY_PATH:-}
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
# Set the app0 directory so /app0/ paths resolve to the correct host directory
export SHARPEMU_APP0_DIR="$APP0_DIR"
# Diagnostics flags
export SHARPEMU_LOG_IMPORT_RECENT=1
export SHARPEMU_LOG_GUEST_THREADS=1
# IL2CPP stub logging — useful for first run
export SHARPEMU_LOG_IL2CPP_STUBS=1
# TLS diagnostics — dump TLS at init and crash
export SHARPEMU_DUMP_TLS=1
# File I/O tracing
export SHARPEMU_LOG_STDIO=1

EMU="/home/z/my-project/work/sharpemu-build/SharpEmu"
EBOOT="${APP0_DIR}/eboot.bin"

echo "=== Test: $GAME_NAME ==="
echo "=== App0:  $APP0_DIR ==="
echo "=== Log:   $LOG_FILE ==="
echo "=== Started: $(date -Iseconds) ==="

timeout --preserve-status $TIMEOUT "$EMU" --log-level=info "$EBOOT" 2>&1 | tee "$LOG_FILE" | tail -300
EXIT=${PIPESTATUS[0]}
echo "=== Finished: $(date -Iseconds), exit=$EXIT ==="
echo "=== Log saved: $LOG_FILE ==="
echo "LOG_FILE=$LOG_FILE"
echo "EXIT=$EXIT"
