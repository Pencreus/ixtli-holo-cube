#!/usr/bin/env python3
"""Back up the vendor's stock videos (everything in /mnt/SDCARD/video except the files the hub added)
to Jarvis, verifying checksums. Writes a manifest of what is safe to delete."""
import hashlib
import json
import os
import subprocess
import sys

NEW = {"flower-blue-dark", "flower-daffodil-bloom", "galaxy-spiral-pink", "galaxy-spiral-purple", "ink-green-orange",
       "ink-orange-black", "ink-red", "jellyfish-blue", "jellyfish-dark-ocean", "jellyfish-trails", "nebula-teal", "roses-dark"}
TMP = os.path.expanduser("~/Projects/fangling-huanjing-en/backup-stock-videos")
os.makedirs(TMP, exist_ok=True)


def adb(*a):
    return subprocess.run(["adb", *a], capture_output=True)


import re
ANSI = re.compile(r"\x1b\[[0-9;]*m")
names = [ANSI.sub("", n).strip() for n in adb("shell", "ls -1 /mnt/SDCARD/video").stdout.decode("utf-8").splitlines()]
names = [n for n in names if n.endswith(".mp4")]
stock = [n for n in names if n[:-4] not in NEW]
print("stock files:", len(stock), flush=True)
manifest = []
for n in stock:
    dst = os.path.join(TMP, n)
    r = adb("pull", f"/mnt/SDCARD/video/{n}", dst)
    h = hashlib.md5(open(dst, "rb").read()).hexdigest()
    remote = adb("shell", f'md5sum "/mnt/SDCARD/video/{n}"').stdout.decode().split()[0]
    ok = h == remote
    print(("OK  " if ok else "BAD ") + n, os.path.getsize(dst), flush=True)
    manifest.append({"name": n, "md5": h, "ok": ok})
json.dump(manifest, open(os.path.join(TMP, "manifest.json"), "w"), ensure_ascii=False, indent=1)
if not all(m["ok"] for m in manifest):
    print("MISMATCH - not copying", flush=True)
    sys.exit(1)
subprocess.run(["ssh", "jetson", "mkdir -p ~/ixtli-clips/stock-videos-backup"], check=True)
subprocess.run(["rsync", "-a", TMP + "/", "jetson:ixtli-clips/stock-videos-backup/"], check=True)
chk = subprocess.run(["ssh", "jetson", "cd ~/ixtli-clips/stock-videos-backup && ls | wc -l && du -sh ."], capture_output=True).stdout.decode()
print("on Jarvis:", chk.replace("\n", " "), flush=True)
print("DONE", flush=True)
