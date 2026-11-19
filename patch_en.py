#!/usr/bin/env python3
"""Patch the English strings into the 方灵幻镜Pro app binary (/usr/night7).

Every replacement is in place: the English text (+ NUL) must fit in the space
the Chinese string already occupies, so no offsets, pointers or code move.
Run:  python3 -I patch_en.py  firmware/night7.orig  firmware/night7.en
"""
import os
import re
import sys

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, "rb").read())
orig = bytes(d)

# --- slot finder -----------------------------------------------------------
def slot(off):
    end = orig.index(b"\0", off)
    j = end
    while orig[j] == 0:
        j += 1
    return end - off, j - off - 1      # current byte length, max byte length

# --- on-screen / protocol strings, keyed by file offset ---------------------
S = {
 0x33dcc4: "Fanhua T113 86Box",
 0x33dce0: "T113 86Box Release",
 0x33dcfc: "T113 86Box Mod2",
 0x33dd14: "Taiji Pi",
 0x33dd28: "Huohuo Necklace",
 0x33dd44: "FL Box",
 0x33dd5c: "Ixtli Holo Cube",
 0x33dd74: "Holo Pod",
 0x33dd88: "Fuxuan Star Chart",
 0x33dda4: "LitBox",
 0x33ddb8: "BT Amplifier",
 0x33ddd0: "Unknown model",
 0x33de98: "Bluetooth Pairing",
 0x33deb0: "%s [%s] requests to connect\nCode: %d",
 0x33dee4: "Accept",
 0x33deec: "Reject",
 0x33def4: "Device not activated \nSerial: %s\nContact #e74f0e Sanalan's Dusk# (Bilibili, Xianyu)\n#666666 A small tip keeps updates coming#",
 0x33e23c: "Cloud action: restarting device\nRestarting..",
 0x33f388: "SSID : %s\nIP : %s\nMAC : %s\nBand : %s Ghz\nRate : %s Mbit/s\nSignal : %s",
 0x33fe28: "Too fast, please wait...",
 0x33fe48: "Parameter error",
 0x33fe7c: "Wrong mode",
 0x33ff54: "Restarting device",
 0x33ff68: "Bad command",
 0x33ff84: "Too fast, please wait",
 0x33ffa0: "Invalid activation code",
 0x33ffbc: "Activated. Restarting device.",
 0x33ffe4: "Activation failed: bad code.",
 0x340024: "Saved",
 0x340040: "No RGB light",
 0x340050: "Invalid param",
 0x34007c: "Wrong parameter",
 0x3400cc: "Bad SSID",
 0x3400dc: "Wrong password",
 0x3400ec: "Configuring network. Watch the device screen for the result. On success it restarts by itself; if not, setup failed - restart it, check the SSID/password and retry.",
 0x34022c: "Bluetooth busy, try again later",
 # holidays / solar terms / lunar days+months (calendar widget)
 0x3459c0: "LNY ", 0x3459c8: "Lantern ", 0x3459d4: "Duanwu ", 0x3459e0: "MidAutumn ",
 0x3459ec: "Chongyang ", 0x3459f8: "New Year ", 0x345a04: "Labor Day ", 0x345a10: "Natl Day ",
 0x345a1c: "Sl.Cold", 0x345a24: "GrCold", 0x345a2c: "SprStrt", 0x345a34: "Rain",
 0x345a3c: "Insects", 0x345a44: "SprEqnx", 0x345a4c: "Clear", 0x345a54: "GrnRain",
 0x345a5c: "SumStrt", 0x345a64: "SmFull", 0x345a6c: "GrnEar", 0x345a74: "SumSol",
 0x345a7c: "SmHeat", 0x345a84: "GrHeat", 0x345a8c: "AutStrt", 0x345a94: "HeatEnd",
 0x345a9c: "WhtDew", 0x345aa4: "AutEqnx", 0x345aac: "ColdDew", 0x345ab4: "Frost",
 0x345abc: "WinStrt", 0x345ac4: "SmSnow", 0x345acc: "GrSnow", 0x345ad4: "WinSol",
 0x346784: "Restarting soon...",
 0x34679c: "WiFi setup OK",
 0x3467ac: "Setup OK\nConnection info saved",
 0x3467d0: "WIFI Manager init failed",
 0x3467ec: "Setup failed",
 0x3467fc: "Failed to start AP mode",
 0x346814: "Restart manually,\nthen check SSID/password & retry",
 0x34684c: "WIFI STA mode start failed",
 0x346868: "Joining..",
 0x346bec: "BT provisioning",
 0x346c00: "BT provisioning, please wait",
 0x346c24: "BT provisioning failed",
 0x347778: "BT A2DP SINK connected",
 0x3477d8: "BT A2DP SINK disconnected",
 0x348044: "Restarting device...",
 0x348070: "AP provisioning enabled. Steps:\n\n1. Join the network AW-AP (password 12345678)\n\n2. Once joined, open 192.168.5.1 in a browser\n\n3. Enter the SSID and password to use\n\n4. Wait for setup to finish; it restarts by itself on success\n\n5. If setup fails, restart the device and try again",
 0x34818c: "Settings reset",
 0x34819c: "Connecting... don't close window",
 0x3481cc: 'WeChat mini program "萨纳兰的黄昏的工作台"\nIf not found, restart the device..',
 0x34823c: "Bluetooth control ON",
 0x348254: "Bluetooth control OFF\nRestarting..",
 0x348280: "Bluetooth control OFF",
 0x348298: "USB file transfer ON",
 0x3482b4: "USB file transfer OFF",
 0x3482d0: "Web control ON",
 0x3482ec: "Web control OFF\nRestarting..",
 0x34831c: "Wifi ON",
 0x34832c: "Wifi OFF",
 0x34833c: 'Join "%s"',
 0x34834c: "Password...",
 0x34835c: "Close",
 0x348378: "Set OK",
 0x348388: "API KEY format invalid",
 0x3483a0: "Set failed",
 0x3483b0: "City Code must be 6 digits\nSee the matching EXCEL file",
 0x3483e8: "Invalid IP address",
 0x348400: "Activated",
 0x348410: "Wrong code",
 0x348420: "Activate fail",
 0x348438: "Connected, info saved",
 0x348460: "Connect failed, WIFI Manager init failed",
 0x34848c: "Connect failed, WIFI STA mode start failed",
 0x3484b8: "Join AP...",
 0x3484d0: "Web control #017aff http://%s#  Version: %s",
 0x348504: "Activated",
 0x348514: "Not activated",
 0x348528: "On/Off",
 0x348534: "Scan",
 0x34853c: "Networks",
 0x34854c: "Connection info",
 0x348560: "System volume",
 0x348574: "Brightness",
 0x34858c: "AIDA64",
 0x348594: "Host IP address",
 0x3485a8: "Weather Clock",
 0x3485b8: "Amap API_KEY",
 0x3485cc: "City Code",
 0x3485e4: "Activation code:",
 0x3485f8: "Commands",
 0x34860c: "Web Control",
 0x34861c: "BT Control",
 0x348630: "USB Xfer",
 0x34863c: "Restart",
 0x348650: "Reset Settings",
 0x34866c: "Written by Sanalan's Dusk()\nManual: https://pressf5.run\nFeedback: DM on Bilibili\nFollow the UP if you like it\nYour support keeps updates coming\n\nDevice: %s\nVersion: v%d.%d.%d\nSerial: %s\nThanks to @Fanhua Cloud for the big help",
 0x34877c: "Back",
 0x34878c: "Sound",
 0x348794: "Display",
 0x3487a0: "Apps",
 0x3487a8: "System",
 0x3487b0: "About",
 0x3487c0: "AP Setup",
 0x3487cc: "Brightness",
 0x3487dc: "Volume",
 0x3488f8: "Bluetooth busy\nWaiting for Bluetooth..",
 0x348920: "Opening Bluetooth\nDon't switch pages",
 0x348948: "Bluetooth on, connect from phone\nIf connected, just start playing",
 0x3489a4: "Bluetooth on, connect from phone",
 0x3489cc: "Bluetooth off",
 0x3489f8: "Set WIFI in Settings, or wait",
 0x348a24: "No WIFI connection",
 0x348a38: "WIFI connected\nOpen %s in browser",
 0x348a60: "Please set host IP",
 0x348aa0: "Put JPG image files\ninto the [pic] folder on the TF card",
 0x348ae4: "No image files",
 0x348af8: "Image file not found\n%s",
 0x348b14: "Wrong image type\n%s",
 0x348b2c: "Image too large\n%s",
 0x348b44: "Image exceeds screen resolution\n%s",
 0x348b6c: "Other error\n%s",
 0x348b7c: "No decoder\n%s",
 0x348b94: "Bad interlace opt\n%s",
 0x348c4c: "Lp",
 0x348c6c: "%s",
 # --- weather condition table. The app strcmp()s the weather service's reply against
 # these to pick the icon, so these are ALSO the exact words the hub's weather endpoint
 # (hub/amap.py) must return. Keep the two lists in sync.
 0x347d98: "Sun", 0x347d9c: "Fair", 0x347da4: "Calm", 0x347dac: "Cloudy", 0x347db4: "Ovc",
 0x347db8: "Windy", 0x347dc0: "Breeze", 0x347dc8: "MdBreez", 0x347dd0: "FrBreez",
 0x347dd8: "Sleet", 0x347de8: "",            # "Rain" is moved to 0x347de0 below
 0x347dec: "Hvy T-Storm", 0x347dfc: "T-Storm", 0x347e08: "Fog", 0x347e0c: "Dust",
 0x347e14: "Sand", 0x347e1c: "Sandstorm", 0x347e28: "Hvy Sandstorm", 0x347e38: "NrGale",
 0x347e40: "Gale", 0x347e48: "StrGale", 0x347e50: "Storm", 0x347e58: "VioStorm",
 0x347e64: "Hurrcn", 0x347e6c: "Trop Storm", 0x347e7c: "Tornado",
 0x347e88: "T-Storm w/ hail", 0x347ea4: "Part Cloudy",
 0x347eb4: "",                                 # "Snow" is moved to 0x347eb0 below
 0x347eb8: "Hot", 0x347ebc: "Haz", 0x347ec0: "Strong Wind",
 0x348ca4: "%sF/%sF",                           # daily high/low, was %s℃/%s℃ (US: Fahrenheit)
}
# lunar day (初一..三十) and month (正月..腊月) names, 8 bytes apart in the string pool
def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"
for i in range(30):
    S[0x345adc + 8 * i] = ordinal(i + 1)
for i, off in enumerate(range(0x345bcc, 0x345c24 + 1, 8)):
    S[off] = f"Mth {i + 1}"
# weekday letters (日 一 二 三 四 五 六)
for off, t in zip(range(0x347eec, 0x347f08, 4), ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]):
    S[off] = t

# --- apply -------------------------------------------------------------------
# Found by auditing the code: these strings are copied with their ORIGINAL compile-time length
# (web replies etc.), so pad them with spaces up to that length instead of NULs.
PAD_SPACES = {0x33fe28, 0x33ff54, 0x33ff68, 0x33ff84, 0x33ffa0, 0x33ffbc, 0x33ffe4, 0x340024,
              0x340050, 0x3400cc, 0x346814, 0x3483a0, 0x348aa0}
bad = 0
for off, en in sorted(S.items()):
    cur, mx = slot(off)
    old = orig[off:off + cur]
    if not re.search(rb"[\xe2-\xe9\xef][\x80-\xbf]{2}", old):
        print(f"SKIP  {off:#x}: no Chinese at offset: {old[:30]!r}"); bad += 1; continue
    eb = en.encode()
    if len(eb) > mx:
        print(f"TOO LONG {off:#x}: {len(eb)} > {mx}: {en!r}  (was {old.decode()!r})"); bad += 1; continue
    if old.count(b"\n") != eb.count(b"\n") and off != 0x3481cc:
        print(f"NEWLINE MISMATCH {off:#x}: {old!r} -> {en!r}"); bad += 1
    if re.findall(rb"%[0-9.]*[sdxlu]+", old) != re.findall(rb"%[0-9.]*[sdxlu]+", eb):
        print(f"FORMAT MISMATCH {off:#x}: {old!r} -> {en!r}"); bad += 1; continue
    if off in PAD_SPACES:                      # consumers that copy the old length: no NULs inside
        eb = eb.ljust(cur)
    d[off:off + mx + 1] = eb + b"\0" * (mx + 1 - len(eb))

# --- the web control page ----------------------------------------------------
HS = 0x3402b4
HE = orig.index(b"\0", HS)
html = orig[HS:HE].decode()
H = {
 "增益校准（在安静环境下进行，切换下面4个挡位以确保在安静的时候几乎没有频谱）": "Gain calibration (do this in a quiet room; try the 4 levels until the spectrum is nearly flat when silent)",
 "该颜色仅限视频、相册、设置、关于页面，若设置为全黑，则以上页面采用随机颜色": "Applies only to Video, Album, Settings and About pages. If set to black, random colors are used.",
 "网络配置中，配网成功设备会自动重启，如果没重启说明配网失败，请重启设备，检查SSID和密码再来一遍": "Configuring network. On success the device restarts by itself; if it does not, setup failed - restart it, check the SSID and password and try again",
 "参数设置（留空表示不修改）": "Settings (leave blank to keep unchanged)",
 "视频播放循环设置": "Video Loop Mode", "音乐播放循环设置": "Music Loop Mode", "相册循环设置": "Album Loop Mode",
 "获取状态信息失败": "Failed to get status", "获取状态信息中": "Getting status",
 "命令执行中": "Running command", "同步时间中": "Syncing time",
 "激活码格式不对": "Invalid activation code format", "SSID不能为空": "SSID cannot be empty",
 "开机后自动进入": "Auto-start App on Boot", "天气城市代码": "Weather City Code",
 "副屏主机地址": "Second-Screen Host IP", "AIDA64副屏": "AIDA64 Second Screen",
 "天气APIKEY": "Weather API Key", "输入激活码": "Activation Code", "本机机器码": "Device Serial",
 "TXT阅读": "TXT Reader", "RGB亮度": "RGB Brightness", "RGB设置": "RGB Settings",
 "拾音频谱": "Audio Spectrum", "特色时钟": "Feature Clock", "蓝牙音乐": "Bluetooth Music",
 "音乐播放": "Music Player", "视频播放": "Video Player", "图片相册": "Photo Album",
 "动态天气": "Live Weather", "顺序单张": "Sequential Single", "顺序幻灯": "Sequential Slideshow",
 "随机单张": "Random Single", "随机幻灯": "Random Slideshow", "单个循环": "Repeat One",
 "列表循环": "Repeat List", "随机播放": "Shuffle", "功能切换": "Mode Select",
 "子项切换": "Item Switch", "控制面板": "Control Panel", "其他命令": "Other Commands",
 "重启设备": "Restart Device", "设备激活": "Device Activation", "音量设置": "Volume",
 "保存中": "Saving", "激活中": "Activating", "前一个": "Previous", "后一个": "Next",
 "主题": "Themes", "配网": "WiFi Setup", "密码": "Password", "连接": "Connect",
 "设置": "Set", "保存": "Save", "激活": "Activate",
}
for zh in sorted(H, key=len, reverse=True):
    html = html.replace(zh, H[zh])
# free space: drop the unused image-picker JS, redundant viewport limits, stray CSS
html = re.sub(r"var rgb565Array=null;function handleImgSelect\(event\)\{.*?reader\.readAsDataURL\(file\)\}\}", "", html, flags=re.S)
html = re.sub(r"function setDateTime\(\)\{.*?\}\)\}", "", html, count=1, flags=re.S)   # unused
html = re.sub(r"h2\{[^}]*\}", "", html, count=1)                                    # unused

# --- the device's own address opens the Ixtli hub (the redo); the vendor page stays at /?classic ---
# In Wi-Fi-setup (AP) mode the page must stay, it is the only way to enter Wi-Fi credentials.
LAUNCH = ("(function(){var h=document.documentElement,s=function(){h.style.visibility='visible'};"
          "if(location.search.indexOf('classic')>=0){return}"
          "h.style.visibility='hidden';setTimeout(s,3500);"
          "fetch('/getstatus').then(function(r){return r.json()}).then(function(d){"
          "if(d.Mark&8){s();return}"
          "fetch('http://10.0.0.196:8098/api/state',{mode:'no-cors'}).then(function(){location.replace('http://10.0.0.196:8098/')},s)},s)})();")
assert "<script>" in html
html = html.replace("<script>", "<script>" + LAUNCH, 1)
html = html.replace(", maximum-scale=1.0, minimum-scale=1.0, user-scalable=no", "")
html = html.replace("<title>CONTROL</title>", "<title>Ixtli Holo Cube</title>")
# RIP AND REPLACE: the device serves its own new UI (device/ui.html) instead of the vendor page.
# It talks to the app's own endpoints (/docmd /savevol /savergb /getstatus ...), keeps the Wi-Fi
# setup form for AP mode, and links to the hub for uploads / panels / updates.
html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "device", "ui.html"), encoding="utf-8").read()
hb = html.encode()
room = HE - HS
if re.search(rb"[\xe2-\xe9][\x80-\xbf]{2}", hb):
    print("HTML still has Chinese:", re.findall(r"[一-鿿]+", html)); bad += 1
if len(hb) > room:
    print(f"HTML too long: {len(hb)} > {room}"); bad += 1
else:
    d[HS:HE] = hb + b" " * (room - len(hb))
    print(f"HTML ok: {len(hb)} of {room} bytes")

# Bluetooth alias that phones see when pairing for music (was PHAN_MIR-xx:x-xx)
i = orig.find(b"PHAN_MIR\0")
if i < 0 or orig.count(b"PHAN_MIR\0") != 1:
    print("PHAN_MIR not found"); bad += 1
else:
    d[i:i + 9] = b"IXTLI" + b"\0" * 4

# --- code patches (ARMv7, file offset = vaddr - 0x10000) -----------------------
import struct
def patch_word(vaddr, old, new):
    global bad
    o = vaddr - 0x10000
    cur = struct.unpack_from("<I", d, o)[0]
    if cur != old:
        print(f"CODE MISMATCH {vaddr:#x}: {cur:#010x} != {old:#010x}"); bad += 1; return
    struct.pack_into("<I", d, o, new)

# Vendor bug: /upload writes to "u/<name>" (relative, folder doesn't exist) so every
# upload silently vanished. Point the folder argument at "/mnt/SDCARD/" (string @0x34d384).
patch_word(0x134c34, 0xe3003620, 0xe30d3384)   # movw r3,#0x620 -> movw r3,#0xd384
patch_word(0x134c50, 0xe3403036, 0xe3403034)   # movt r3,#0x36  -> movt r3,#0x34
assert orig[0x34d384 - 0x10000:0x34d384 - 0x10000 + 13] == b"/mnt/SDCARD/\0"
# Mongoose receive limit 3 MB -> 16 MB (two checks) so music files can be uploaded.
patch_word(0xb751c, 0xe3520603, 0xe3520610)    # cmp r2,#0x300000 -> #0x1000000
patch_word(0xb77d8, 0xe3530603, 0xe3530610)    # cmp r3,#0x300000 -> #0x1000000

# --- US weather: send the app's weather lookups to the hub instead of Amap (China) ---
# The app copies these URLs with a compile-time length, so the replacement MUST be exactly
# as long as the original (no NUL padding - it would cut off the key/city appended after it).
# ":08098" is a decimal port with a leading zero, used to make up the length.
HUB = b"10.0.0.196:08098"
for old, new in ((b"http://restapi.amap.com/v3/ip?key=", b"http://" + HUB + b"/v3/ip?key="),
                 (b"http://restapi.amap.com/v3/weather/weatherInfo?key=", b"http://" + HUB + b"/v3/weather/weatherInfo?key=")):
    i = orig.find(old)
    if i < 0 or orig.count(old) != 1 or len(new) != len(old):
        print("URL patch problem", old, len(old), len(new)); bad += 1; continue
    d[i:i + len(old)] = new

# "Rain" and "Snow" don't fit their 3-char table slots. Write them into padding freed by the
# neighbouring strings and repoint every movw/movt pair that loaded the old address.
def repoint(old_va, new_va):
    global bad
    lo, hi = old_va & 0xFFFF, old_va >> 16
    n = 0
    for i in range(0, 0x340000, 4):
        w = struct.unpack_from("<I", d, i)[0]
        if (w & 0x0FF00000) == 0x03000000 and (((w >> 4) & 0xF000) | (w & 0xFFF)) == lo:
            rd = (w >> 12) & 0xF
            for k in range(1, 8):
                j = i + 4 * k
                w2 = struct.unpack_from("<I", d, j)[0]
                if (w2 & 0x0FF00000) == 0x03400000 and ((w2 >> 12) & 0xF) == rd and (((w2 >> 4) & 0xF000) | (w2 & 0xFFF)) == hi:
                    nl, nh = new_va & 0xFFFF, new_va >> 16
                    struct.pack_into("<I", d, i, (w & 0xFFF0F000) | ((nl & 0xF000) << 4) | (nl & 0xFFF))
                    struct.pack_into("<I", d, j, (w2 & 0xFFF0F000) | ((nh & 0xF000) << 4) | (nh & 0xFFF))
                    n += 1
                    break
    if n != 2:
        print(f"repoint {old_va:#x}: expected 2 references, found {n}"); bad += 1

for off_old, off_new, text in ((0x347de8, 0x347de0, b"Rain"), (0x347eb4, 0x347eb0, b"Snow")):
    assert all(b == 0 for b in d[off_new:off_new + 8]) or off_new == 0x347eb0, "padding not free"
    d[off_new:off_new + len(text) + 1] = text + b"\0"
    repoint(off_old + 0x10000, off_new + 0x10000)

if bad:
    print(f"\n{bad} problem(s) - nothing written"); sys.exit(1)
assert len(d) == len(orig)
open(dst, "wb").write(d)
print(f"wrote {dst}: {len(d)} bytes, {sum(1 for a, b in zip(orig, d) if a != b)} bytes changed")
