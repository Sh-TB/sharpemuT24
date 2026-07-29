#!/bin/bash
# bootstrap-runtime.sh — One-command SharpEmuT24 runtime environment restore
#
# Recreates all ephemeral components lost on container restart:
#   1. .NET SDK 10 (user-local install to /home/z/.dotnet)
#   2. Vulkan Lavapipe (user-local extraction to /home/z/.local/vulkan)
#   3. Game files (extraction from persistent ossfs rar archives)
#   4. Xvfb display server (virtual framebuffer on :99)
#   5. Environment variables (DISPLAY, VK_ICD_FILENAMES, LD_LIBRARY_PATH)
#
# Usage:
#   source scripts/bootstrap-runtime.sh
#   # OR
#   bash scripts/bootstrap-runtime.sh && source /tmp/bootstrap-env.sh

set -euo pipefail

BOOTSTRAP_LOG="/tmp/bootstrap-runtime.log"
ENV_EXPORT_FILE="/tmp/bootstrap-env.sh"
: > "$BOOTSTRAP_LOG"
: > "$ENV_EXPORT_FILE"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$BOOTSTRAP_LOG"; }

log "=== SharpEmuT24 Runtime Bootstrap ==="
log "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ============================================================
# 1. .NET SDK 10
# ============================================================
log "[1/5] Checking .NET SDK..."
if /home/z/.dotnet/dotnet --version >/dev/null 2>&1; then
    log "  PASS: .NET SDK already installed: $(/home/z/.dotnet/dotnet --version)"
else
    log "  Installing .NET SDK 10.0.302 to /home/z/.dotnet..."
    curl -sSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
    bash /tmp/dotnet-install.sh --channel 10.0 --install-dir /home/z/.dotnet >> "$BOOTSTRAP_LOG" 2>&1
    log "  PASS: .NET SDK installed: $(/home/z/.dotnet/dotnet --version)"
fi
echo 'export PATH=/home/z/.dotnet:$PATH' >> "$ENV_EXPORT_FILE"
echo 'export DOTNET_ROOT=/home/z/.dotnet' >> "$ENV_EXPORT_FILE"

# ============================================================
# 2. Vulkan Lavapipe
# ============================================================
log "[2/5] Checking Vulkan Lavapipe..."
VULKAN_ICD="/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json"
if [ -f "$VULKAN_ICD" ]; then
    log "  PASS: Vulkan Lavapipe already installed"
else
    log "  Installing mesa-vulkan-drivers (user-local)..."
    cd /tmp
    apt download mesa-vulkan-drivers >> "$BOOTSTRAP_LOG" 2>&1
    mkdir -p /home/z/.local/vulkan
    dpkg -x mesa-vulkan-drivers_*.deb /home/z/.local/vulkan >> "$BOOTSTRAP_LOG" 2>&1
    log "  PASS: Vulkan Lavapipe installed: $VULKAN_ICD"
fi
echo "export VK_ICD_FILENAMES=$VULKAN_ICD" >> "$ENV_EXPORT_FILE"
echo "export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:\${LD_LIBRARY_PATH:-}" >> "$ENV_EXPORT_FILE"

# ============================================================
# 3. Game Files
# ============================================================
log "[3/5] Checking game files..."

# Yatzi
if [ -f /tmp/games/yatzi/eboot.bin ]; then
    log "  PASS: Yatzi already extracted"
else
    log "  Extracting Yatzi from decrypted.part01.rar..."
    mkdir -p /tmp/games/yatzi
    cd /tmp/my-project/upload
    unrar x -y decrypted.part01.rar /tmp/games/yatzi/ >> "$BOOTSTRAP_LOG" 2>&1
    log "  PASS: Yatzi extracted"
fi

# Dreaming Sarah
DS_APP0="/tmp/games/dreaming-sarah/PPSA02929-app0"
if [ -f "$DS_APP0/eboot.bin" ]; then
    MAGIC=$(head -c4 "$DS_APP0/eboot.bin" | od -An -tx1 | tr -d ' \n')
    if [ "$MAGIC" = "7f454c46" ]; then
        log "  PASS: Dreaming Sarah already extracted (decrypted ELF)"
    else
        if [ -f "$DS_APP0/eboot.bin.esbak" ]; then
            mv "$DS_APP0/eboot.bin" "$DS_APP0/eboot.bin.encrypted_self"
            mv "$DS_APP0/eboot.bin.esbak" "$DS_APP0/eboot.bin"
            log "  PASS: Dreaming Sarah: swapped .esbak to eboot.bin"
        else
            log "  Extracting Dreaming Sarah from PPSA02929-app0.rar..."
            mkdir -p /tmp/games/dreaming-sarah
            cd /tmp/my-project/upload
            unrar x -y PPSA02929-app0.rar /tmp/games/dreaming-sarah/ >> "$BOOTSTRAP_LOG" 2>&1
            if [ -f "$DS_APP0/eboot.bin.esbak" ]; then
                mv "$DS_APP0/eboot.bin" "$DS_APP0/eboot.bin.encrypted_self"
                mv "$DS_APP0/eboot.bin.esbak" "$DS_APP0/eboot.bin"
            fi
            log "  PASS: Dreaming Sarah extracted"
        fi
    fi
else
    log "  Extracting Dreaming Sarah from PPSA02929-app0.rar..."
    mkdir -p /tmp/games/dreaming-sarah
    cd /tmp/my-project/upload
    unrar x -y PPSA02929-app0.rar /tmp/games/dreaming-sarah/ >> "$BOOTSTRAP_LOG" 2>&1
    if [ -f "$DS_APP0/eboot.bin.esbak" ]; then
        mv "$DS_APP0/eboot.bin" "$DS_APP0/eboot.bin.encrypted_self"
        mv "$DS_APP0/eboot.bin.esbak" "$DS_APP0/eboot.bin"
    fi
    log "  PASS: Dreaming Sarah extracted"
fi

# ============================================================
# 4. Xvfb Display Server
# ============================================================
log "[4/5] Checking Xvfb..."
if pgrep -f "Xvfb :99" >/dev/null 2>&1; then
    log "  PASS: Xvfb already running on :99"
else
    log "  Starting Xvfb on :99..."
    mkdir -p /tmp/.X11-unix /tmp/xdg
    chmod 1777 /tmp/.X11-unix /tmp/xdg
    setsid Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null &
    sleep 2
    if pgrep -f "Xvfb :99" >/dev/null 2>&1; then
        log "  PASS: Xvfb started (PID $(pgrep -f 'Xvfb :99' | head -1))"
    else
        log "  FAIL: Xvfb failed to start — check /tmp/xvfb.log"
    fi
fi
echo 'export DISPLAY=:99' >> "$ENV_EXPORT_FILE"
echo 'export XDG_RUNTIME_DIR=/tmp/xdg' >> "$ENV_EXPORT_FILE"

# ============================================================
# 5. SharpEmu Environment Variables
# ============================================================
log "[5/5] Setting SharpEmu environment variables..."
echo 'export SHARPEMU_SEMA_FAST_PATH=1' >> "$ENV_EXPORT_FILE"
echo 'export SHARPEMU_VIDEOOUT_FALLBACK_IMAGE=1' >> "$ENV_EXPORT_FILE"

# ============================================================
# Summary
# ============================================================
log ""
log "=== Bootstrap Complete ==="
log "To activate: source /tmp/bootstrap-env.sh"
log "To verify:   bash scripts/env-fingerprint.sh"
log "To build:    cd /tmp/my-project/work/sharpemuT24 && dotnet build SharpEmu.slnx -c Release"

echo ""
echo "=== Environment exports (source these) ==="
cat "$ENV_EXPORT_FILE"
