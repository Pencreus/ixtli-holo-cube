#!/bin/sh
# Push new firmware to the Ixtli Holo Cube over the air (no USB).
#   ./ota.sh app|agent|both [--force]
# Build first:  python3 -I patch_en.py firmware/night7.orig firmware/night7.en
set -e
cd "$(dirname "$0")"
HUB_SSH=${HUB_SSH:-jetson}   # ssh alias of the machine running the hub
K=${1:-both}; F=""; [ "$2" = "--force" ] && F=',"force":true'
cp firmware/night7.en hub/fw/night7
cp device/hubagent hub/fw/hubagent
rsync -a hub/fw/ "$HUB_SSH":huanjing-hub/fw/
ssh "$HUB_SSH" 'systemctl --user is-active huanjing-hub >/dev/null'
send() { ssh "$HUB_SSH" "curl -s -X POST -H 'content-type: application/json' -d '{\"kind\":\"$1\"$F}' localhost:8098/api/ota"; echo; }
# helper first (it restarts quickly), then the app (it reboots the device)
if [ "$K" = agent ] || [ "$K" = both ]; then send agent; fi
if [ "$K" = both ]; then sleep 20; fi
if [ "$K" = app ] || [ "$K" = both ]; then send app; fi
exit 0
