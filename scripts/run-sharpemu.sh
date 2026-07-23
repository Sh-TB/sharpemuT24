#!/bin/bash
set -e
if ! pgrep -f "Xvfb :1" > /dev/null 2>&1; then
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null
    mkdir -p /tmp/.X11-unix /tmp/xdg; chmod 1777 /tmp/.X11-unix /tmp/xdg
    nohup setsid Xvfb :1 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null &
    disown; sleep 3
fi
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/glfw-deps/usr/lib/x86_64-linux-gnu:/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
export DISPLAY=:1 XDG_RUNTIME_DIR=/tmp/xdg
( while true; do sleep 2; if ! pgrep -f "Xvfb :1" > /dev/null 2>&1; then rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null; nohup setsid Xvfb :1 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null & disown; fi; done ) &
W=$!; "$@"; R=$?; kill $W 2>/dev/null; exit $R
