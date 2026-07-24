#!/bin/bash
# game-loop.sh — Run all 4 games, collect boot progress
set -u
LOG_DIR="/home/z/my-project/work/sharpemu-build/logs"
WORKLOG="/home/z/my-project/GAME_BRINGUP_WORKLOG.md"
mkdir -p "$LOG_DIR"

# Ensure Xvfb running
if ! pgrep -f "Xvfb :99" > /dev/null 2>&1; then
    pkill -9 Xvfb 2>/dev/null; sleep 1
    rm -f /tmp/.X*-lock /tmp/.X11-unix/X* 2>/dev/null
    mkdir -p /tmp/.X11-unix /tmp/xdg; chmod 1777 /tmp/.X11-unix /tmp/xdg
    nohup setsid Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null &
    disown; sleep 3
fi

export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build:${LD_LIBRARY_PATH:-}
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_LOG_IMPORT_RECENT=1
export SHARPEMU_DUMP_TLS=0
export SHARPEMU_LOG_IL2CPP_STUBS=0
export SHARPEMU_LOG_STDIO=0
export SHARPEMU_SEMA_FAST_PATH=1

EMU="/home/z/my-project/work/sharpemu-build/SharpEmu"

# Create save data for all games
SAVEDIR="/home/z/my-project/work/sharpemu-build/user/savedata/268435456"
mkdir -p "$SAVEDIR/arise/SaveData" "$SAVEDIR/harvest/SaveData" "$SAVEDIR/newgame/SaveData"
touch "$SAVEDIR/arise/SaveData/save.xml" "$SAVEDIR/arise/SaveData/statistics.bin" 2>/dev/null
touch "$SAVEDIR/arise/SaveData/trophies.bin" "$SAVEDIR/arise/SaveData/unlockables.bin" 2>/dev/null

# Create dummy game data for Arise
mkdir -p /tmp/arise-app0/resources/cookeddata /tmp/arise-app0/resources/shaders/2d /tmp/arise-app0/resources/texts/en.lproj
touch /tmp/arise-app0/resources/cookeddata/bigfile.bfdb
touch /tmp/arise-app0/resources/shaders/2d/basic_vs_a3cd97ea_vs.ags
touch /tmp/arise-app0/resources/shaders/2d/basic_fs_3488995a_ps.ags
touch /tmp/arise-app0/resources/texts/en.lproj/localizable.strings
touch /tmp/arise-app0/resources/texts/localizable.strings

run_game() {
    local name="$1"
    local app0="$2"
    local timeout_sec="$3"
    local ts=$(date +%Y%m%d-%H%M%S)
    local log="$LOG_DIR/${name}-${ts}.log"
    
    export SHARPEMU_APP0_DIR="$app0"
    
    echo "[$(date -Iseconds)] RUN $name (timeout ${timeout_sec}s)"
    timeout --preserve-status $timeout_sec "$EMU" --log-level=info "${app0}/eboot.bin" > "$log" 2>&1
    local exit_code=$?
    
    local imports=$(grep -oE 'import#[0-9]+' "$log" | tail -1 | grep -oE '[0-9]+')
    local videoout=$(grep -c 'VideoOut ready' "$log" 2>/dev/null)
    local presented=$(grep -c 'presented first frame' "$log" 2>/dev/null)
    local null_rec=$(grep -c 'NULL execute' "$log" 2>/dev/null)
    local unmapped_rec=$(grep -c 'Unmapped memory' "$log" 2>/dev/null)
    local crashes=$(grep -c 'posix-signal#' "$log" 2>/dev/null)
    
    echo "  imports=${imports:-0} videoout=$videoout presented=$presented null_rec=$null_rec unmapped_rec=$unmapped_rec crashes=$crashes"
    
    cat >> "$WORKLOG" << EOF
---
Date: $(date -Iseconds)
Game: $name
Commit: $(cd /home/z/my-project && git rev-parse --short HEAD 2>/dev/null)
Imports: ${imports:-0} | VideoOut: $videoout | Presented: $presented | NULL: $null_rec | Unmapped: $unmapped_rec | Crashes: $crashes
Result: $([ "$presented" -gt 0 ] 2>/dev/null && echo "FIRST FRAME RENDERED" || ([ "$videoout" -gt 0 ] 2>/dev/null && echo "VideoOut reached" || echo "No VideoOut"))
EOF
}

cat > "$WORKLOG" << 'EOF'
# Game Bring-up Worklog (Permanent)
EOF

echo "========== ITERATION =========="
run_game "sarah"   "/home/z/my-project/upload/PPSA02929/PPSA02929-app0" 60
run_game "arise"   "/tmp/arise-app0" 90
run_game "harvest" "/tmp/games/harvest" 90
run_game "newgame" "/tmp/games/newgame" 90

echo ""
echo "========== SUMMARY =========="
tail -20 "$WORKLOG"
