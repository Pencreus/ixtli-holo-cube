# Ixtli Holo Cube

English firmware patch, web UI, Home Assistant bridge and media hub for the cheap "Fangling Huanjing Pro" 480x480 holo-cube
(Allwinner T113, TinaLinux, vendor app `night7`). Independent hobby project, not affiliated with the vendor.

**What is NOT in this repo (on purpose):** the vendor firmware (`night7`, patched or not), a dump of the device config, the vendor's
fonts and videos, and every secret. `patch_en.py` patches *your own* copy: pull it with `adb pull /usr/night7 firmware/night7.orig`
(the patch offsets are for the build this was written against, so check the md5 first; a different build needs new offsets).
Secrets live in git-ignored files: copy `device/secrets.env.example` -> `device/secrets.env` and `hub/.env.example` -> `hub/.env`.
The `10.0.0.x` addresses in the code are examples from the author's LAN: change them (note that URLs baked into the binary must keep
their exact length - see "Traps" below). The Wi-Fi AP password mentioned in `patch_en.py` is the vendor's public default.

Use at your own risk: this modifies a device's firmware and an unauthenticated vendor web API stays reachable on your LAN.
Code is MIT-licensed (see LICENSE).

---

# Ixtli Holo Cube (hardware: 方灵幻镜Pro / "Huanjing Pro") — English + house integration

Not an ESP32: an Allwinner T113 TinaLinux box (USB `adb` = root). The vendor app is one ELF, `/usr/night7`.

| Piece | Where | What it does |
|---|---|---|
| `patch_en.py` | here | Patches `firmware/night7.orig` → `night7.en`: every on-screen string + the web page in English (in place), weather table in English, weather URLs → hub, °F, upload bug fix (`/upload` → SD card), 16 MB receive cap |
| `device/hubagent` | on device, `/usr/bin` (procd service) | MQTT bridge: HA discovery (16 entities), drives the app's local web API, pulls files onto the SD card, ls/rm |
| `hub/` | Jarvis `~/huanjing-hub`, `systemctl --user … huanjing-hub`, **http://10.0.0.196:8098** | Web UI, big uploads (+ffmpeg/Pillow convert to 480×480), house panels → album, Amap-compatible US weather endpoint |

Install patched app: `adb push firmware/night7.en /usr/night7.en && adb shell 'chmod +x /usr/night7.en && mv /usr/night7.en /usr/night7'` then restart app (HA button) or reboot.
Install agent: `device/install.sh`. Deploy hub: `rsync -a hub/ jetson:huanjing-hub/ && ssh jetson 'systemctl --user restart huanjing-hub'`.
Revert app: copy `/mnt/SDCARD/night7/night7_app` (pristine) over `/usr/night7`. Original system config: `firmware/system.config.orig`.

Traps: the app copies some constants with a compile-time length (URLs → must stay the exact same length; web-reply texts → space-padded);
start the app only from the agent/rc.local (a one-off `adb shell` child dies with the shell); `touch /tmp/applog` before `restart_app`
to capture the app log (buffered — flush by changing modes); no `tail/stat/timeout/wc/pkill` on the device.

## 2026-11-12 additions
- **Name: Ixtli** (Nahuatl, "vision"). Device name/BT alias patched in `patch_en.py`; HA device + entities are `*.ixtli_*` (old `huanjing_*` configs are cleared by the agent). MQTT base topic is still `huanjing/` (internal).
- **Boot splash** = The Pencreus sunstone-eye animation, ported from `~/Projects/pencreus-boot-splash/splash.h` to 480x480: `boot/ixtli_splash.py` renders frames (run on Jarvis, Pillow) -> `ffmpeg` -> `boot/out/pencreus_boot.mp4` (79 KB, 7.8 s: 5.0 s animation + logo held 2.8 s).
  On the device: `/usr/share/ixtli/pencreus_boot.mp4`, `/usr/bin/ixtli-splash` (drives the built-in `tplayerdemo`), hooked from `/etc/rc.local` before the app (failsafe, kills the player if it overruns). Original rc.local: `firmware/rc.local.orig`.
- **Fonts:** the app loads a TrueType font from `/mnt/SDCARD/fonts/DingTalk_JinBuTi.ttf` but the card only had it in `night7/` -> copied it there. (`UI_FONT_16.bin` is fine: index = codepoint-10, ASCII complete.)
- **Memory leak:** every `killall night7` + restart leaks ~6 MB of kernel (ION/decoder) memory; ~10 restarts => OOM-kill. A reboot frees it. So the agent/hub no longer offer "Restart app", only a full device Restart. (`restart_app` still exists in the agent for debugging.)

- **Renamed again 2026-11-12: "Ixtli Holo Cube"** (device name string is exactly the vendor slot size, 15 bytes). HA entities are `*.ixtli_holo_cube_*` (agent clears the older `huanjing_*` and `ixtli_*` configs).
- Stock vendor videos were backed up to Jarvis `~/ixtli-clips/stock-videos-backup` (and `backup-stock-videos/` here, manifest with md5) and removed from the card.

## Over-the-air updates (no USB), 2026-11-12
`./ota.sh app|agent|both [--force]` builds nothing: first run `python3 -I patch_en.py firmware/night7.orig firmware/night7.en` (app) and/or edit `device/hubagent` (agent), then `./ota.sh both`.
It copies the files to `hub/fw/` (rsynced to Jarvis `~/huanjing-hub/fw/`), and the hub tells the device (`huanjing/cmd/ota`) to pull `http://10.0.0.196:8098/fw/<file>`.
The agent only accepts URLs under the hub, verifies the md5, keeps `/usr/night7.prev` / `/usr/bin/hubagent.prev`, swaps, and the app update reboots.
Rollback: the update writes `/etc/ota_pending`=1; `rc.local` bumps it each boot; the agent deletes it after the new app answered for 40 s; if the next boot still sees >=2 it restores `night7.prev`.
The hub's Device card shows "up to date" / an Update button by comparing the device's reported md5 (`app_md5`, `agent_md5` in `huanjing/state`) with `hub/fw`. Not covered by OTA: `rc.local`, the splash mp4, the boot-time mute (still USB).
Tested 2026-11-12: foreign URL refused, bad md5 refused (file removed, binary untouched), forced agent OTA, forced app OTA incl. reboot + flag cleared. The rollback path itself was NOT exercised (would need a deliberately broken app).

- 2026-11-12: the device address http://10.0.0.156/ now redirects to the hub (launcher in the web page blob; stays on the vendor page in Wi-Fi-setup AP mode, and `/?classic` always shows the vendor page). Pushed over the air.

- **2026-11-12 (later): rip-and-replace done.** The device now serves its OWN new UI (`device/ui.html`, 9.5 KB, built into the app by `patch_en.py`), standalone from Jarvis: modes, next/prev, volume, ring light, play orders, restart, spectrum gain, AIDA64 host, and the Wi-Fi setup form in AP mode. The earlier redirect launcher and the vendor page (`/?classic`) are gone. The hub remains for uploads, conversion, panels and OTA (the page links to it).
  Page quirk: the vendor app ignores a light change sent within ~1 s of a mode change; the page queues its commands one at a time.
