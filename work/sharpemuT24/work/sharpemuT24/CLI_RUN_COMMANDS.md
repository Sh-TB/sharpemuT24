# CLI Run Commands (Permanent — Never Delete)

## Environment Setup (Required for all games)

```bash
export VK_ICD_FILENAMES=/home/z/.local/vulkan/usr/share/vulkan/icd.d/lvp_icd.json
export LD_LIBRARY_PATH=/home/z/.local/vulkan/usr/lib/x86_64-linux-gnu:/home/z/my-project/work/sharpemu-build:${LD_LIBRARY_PATH:-}
export DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/xdg
export SHARPEMU_SEMA_FAST_PATH=1

# Ensure Xvfb running
if ! pgrep -f "Xvfb :99" > /dev/null 2>&1; then
    pkill -9 Xvfb 2>/dev/null; sleep 1
    rm -f /tmp/.X*-lock /tmp/.X11-unix/X* 2>/dev/null
    mkdir -p /tmp/.X11-unix /tmp/xdg; chmod 1777 /tmp/.X11-unix /tmp/xdg
    nohup setsid Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac -noreset > /tmp/xvfb.log 2>&1 < /dev/null &
    disown; sleep 3
fi
```

## Game Commands

### Dreaming Sarah (Golden Test — Regression)
```bash
export SHARPEMU_APP0_DIR=/home/z/my-project/upload/PPSA02929/PPSA02929-app0
./work/sharpemu-build/SharpEmu --log-level=info upload/PPSA02929/PPSA02929-app0/eboot.bin
```
Result: First Frame 3840x2160 ✅

### Arise
```bash
export SHARPEMU_APP0_DIR=/tmp/arise-app0
# Ensure save data
mkdir -p work/sharpemu-build/user/savedata/268435456/arise/SaveData
touch work/sharpemu-build/user/savedata/268435456/arise/SaveData/{save.xml,statistics.bin,trophies.bin,unlockables.bin}
# Ensure game data
mkdir -p /tmp/arise-app0/resources/{cookeddata,shaders/2d,texts/en.lproj}
touch /tmp/arise-app0/resources/cookeddata/bigfile.bfdb
./work/sharpemu-build/SharpEmu --log-level=info /tmp/arise-app0/eboot.bin
```
Result: First Frame 3840x2160 ✅ (splash screen)

### Harvest Days
```bash
export SHARPEMU_APP0_DIR=/tmp/games/harvest
./work/sharpemu-build/SharpEmu --log-level=info /tmp/games/harvest/eboot.bin
```
Result: Running, IL2CPP block

### New Game
```bash
export SHARPEMU_APP0_DIR=/tmp/games/newgame
./work/sharpemu-build/SharpEmu --log-level=info /tmp/games/newgame/eboot.bin
```
Result: Running, IL2CPP block

## Quick Test All Games
```bash
./scripts/game-loop.sh
```

## Build Command
```bash
export PATH="/home/z/.dotnet:$PATH"
cd work/sharpemuT24
dotnet publish src/SharpEmu.CLI/SharpEmu.CLI.csproj -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true -o /home/z/my-project/work/sharpemu-build
```

## Environment
- OS: Debian 13 (trixie)
- .NET SDK: 10.0.302
- .NET Runtime: 10.0.10
- Vulkan: Lavapipe (mesa-vulkan-drivers 25.0.7)
- X11: Xvfb on display :99
- Display: 1920x1080x24
