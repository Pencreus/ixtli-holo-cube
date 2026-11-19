"""Ixtli Hub - web control + media manager for the Huanjing Pro, runs on Jarvis.

The device itself only has a tiny vendor web server (3 MB upload cap, painfully slow).
Here: browser -> Jarvis (fast, any size) -> the device *pulls* the file onto its SD card
(over the MQTT-driven hubagent). Also renders house "glance" panels into the album.
"""
import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

import amap
import media
import panels

ROOT = Path(__file__).parent
STAGING = ROOT / "staging"
PANEL_DIR = ROOT / "panels"
SETTINGS_FILE = ROOT / "settings.json"
BASE = "huanjing"
PUBLIC = os.environ.get("HUB_PUBLIC", "http://10.0.0.196:8098")
FOLDERS = {"pic": "Photos", "video": "Videos", "music": "Music", "weather": "Weather art", "clockbg": "Clock backgrounds"}
MODES = ["Clock", "Video", "Album", "Music", "Bluetooth", "Weather", "Spectrum", "AIDA64"]
BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

STAGING.mkdir(exist_ok=True)
PANEL_DIR.mkdir(exist_ok=True)

# ------------------------------------------------------------------ settings -----
DEFAULTS = {"panels_enabled": True, "panels": {"weather": True, "home": True, "printer": True}, "interval_min": 10}


def load_settings():
    try:
        s = json.loads(SETTINGS_FILE.read_text())
    except Exception:
        s = {}
    out = json.loads(json.dumps(DEFAULTS))
    out.update({k: v for k, v in s.items() if k in DEFAULTS})
    out["panels"] = {**DEFAULTS["panels"], **s.get("panels", {})}
    return out


def save_settings(s):
    SETTINGS_FILE.write_text(json.dumps(s, indent=1))


settings = load_settings()

# ------------------------------------------------------------------ device state --
dev = {"online": False, "seen": 0.0, "state": {}, "light": {}, "ls": {}}
jobs = {}            # id -> job dict
queue = []           # job ids waiting to be sent to the device
panel_hash = {}      # panel name -> sha of the last image pushed
panel_info = {}      # panel name -> {updated, pushed}

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="huanjing-hub")
client.username_pw_set(os.environ.get("MQTT_USER"), os.environ.get("MQTT_PASS"))


def on_connect(c, userdata, flags, rc, props=None):
    c.subscribe(f"{BASE}/#")


def on_message(c, userdata, msg):
    t = msg.topic
    try:
        raw = msg.payload.decode("utf-8", "replace")
        if t == f"{BASE}/status":
            dev["online"] = raw == "online"
            if dev["online"]:
                dev["seen"] = time.time()
        elif t == f"{BASE}/state":
            dev["state"] = json.loads(raw)
            dev["seen"] = time.time()
        elif t == f"{BASE}/light":
            dev["light"] = json.loads(raw)
        elif t == f"{BASE}/ls":
            j = json.loads(raw)
            dev["ls"][j.get("dir", "")] = {"t": time.time(), **j}
        elif t.startswith(f"{BASE}/fetch/"):
            jid = t.rsplit("/", 1)[1]
            j = jobs.get(jid)
            if j:
                m = json.loads(raw)
                j.update(device=m, touched=time.time())
                st = m.get("state")
                if st == "downloading":
                    j["state"] = "sending"
                elif st == "done":
                    j["state"] = "done"
                elif st == "error":
                    j["state"] = "error"
                    j["error"] = m.get("error", "failed")
    except Exception as e:  # never kill the network thread
        print("mqtt message error", t, e)


client.on_connect = on_connect
client.on_message = on_message
client.connect_async(os.environ.get("MQTT_HOST", "10.0.0.190"), 1883, 30)
client.loop_start()


def cmd(name, payload=""):
    client.publish(f"{BASE}/cmd/{name}", payload if isinstance(payload, str) else json.dumps(payload))


# ------------------------------------------------------------------ app ----------
app = FastAPI(title="Ixtli Holo Cube Hub")


def safe_name(name):
    name = BAD_CHARS.sub("_", Path(name).name).strip(" .")
    if not name or len(name) > 120:
        raise HTTPException(400, "bad file name")
    return name


def check_dir(d):
    if d not in FOLDERS:
        raise HTTPException(400, "unknown folder")
    return d


def online():
    return dev["online"] and time.time() - dev["seen"] < 90


@app.get("/", response_class=HTMLResponse)
async def index():
    return (ROOT / "static" / "index.html").read_text()


@app.get("/api/state")
async def api_state():
    now = time.time()
    return {
        "online": online(),
        "state": dev["state"],
        "light": dev["light"],
        "folders": FOLDERS,
        "modes": MODES,
        "jobs": [{k: v for k, v in j.items() if k not in ("path",)} for j in sorted(jobs.values(), key=lambda j: j["created"], reverse=True)[:12]],
        "settings": settings,
        "panels": {n: {"title": panels.TITLES[n], **panel_info.get(n, {})} for n in panels.PANELS},
        "now": now,
        "fw": {k: (fw_md5(k) or "")[:8] for k in FW_FILES},
    }


# --- plain controls -------------------------------------------------------------
@app.post("/api/mode")
async def api_mode(body: dict):
    if body.get("mode") not in MODES:
        raise HTTPException(400, "unknown mode")
    cmd("mode", body["mode"])
    return {"ok": True}


@app.post("/api/item")
async def api_item(body: dict):
    if body.get("dir") not in ("next", "prev"):
        raise HTTPException(400)
    cmd("item", body["dir"])
    return {"ok": True}


@app.post("/api/volume")
async def api_volume(body: dict):
    v = int(body.get("value", -1))
    if not 0 <= v <= 100:
        raise HTTPException(400)
    cmd("volume", str(v))
    return {"ok": True}


@app.post("/api/light")
async def api_light(body: dict):
    out = {}
    if body.get("state") in ("ON", "OFF"):
        out["state"] = body["state"]
    if "brightness" in body:
        out["brightness"] = max(0, min(100, int(body["brightness"])))
    if "color" in body:
        out["color"] = {k: max(0, min(255, int(body["color"][k]))) for k in "rgb"}
    cmd("light", out)
    return {"ok": True}


@app.post("/api/loop")
async def api_loop(body: dict):
    kind = body.get("kind")
    if kind not in ("video", "music", "album"):
        raise HTTPException(400)
    cmd("album_mode" if kind == "album" else f"{kind}_loop", str(body.get("value", "")))
    return {"ok": True}


@app.post("/api/restart_app")
async def api_restart_app():
    cmd("restart_app", "1")
    return {"ok": True}


@app.post("/api/reboot")
async def api_reboot():
    cmd("reboot", "1")
    return {"ok": True}


# --- media manager --------------------------------------------------------------
@app.get("/api/ls")
async def api_ls(dir: str):
    check_dir(dir)
    t0 = time.time()
    cmd("ls", dir)
    for _ in range(40):
        await asyncio.sleep(0.1)
        r = dev["ls"].get(dir)
        if r and r["t"] >= t0:
            break
    r = dev["ls"].get(dir)
    if not r:
        raise HTTPException(504, "device did not answer")
    files = sorted(r.get("files", []), key=lambda f: (not f["d"], f["n"].lower()))
    return {"dir": dir, "files": files, "stale": r["t"] < t0}


@app.post("/api/rm")
async def api_rm(body: dict):
    path = str(body.get("path", ""))
    top, _, name = path.partition("/")
    check_dir(top)
    if not name or "/" in name or ".." in name:
        raise HTTPException(400)
    cmd("rm", path)
    dev["ls"].pop(top, None)
    return {"ok": True}


def pump():
    """Send the next queued file to the device if it is idle."""
    if any(j["state"] == "sending" and time.time() - j.get("touched", 0) < 90 for j in jobs.values()):
        return
    while queue:
        jid = queue.pop(0)
        j = jobs.get(jid)
        if not j or j["state"] != "queued":
            continue
        j["state"] = "sending"
        j["touched"] = time.time()
        cmd("fetch", {"id": jid, "url": f"{PUBLIC}/stage/{jid}/{quote(j['name'])}", "dest": f"{j['dir']}/{j['name']}", "size": j["size"]})
        return


def enqueue(jid):
    queue.append(jid)
    pump()


async def process(jid, path, fill, mute=False):
    """Convert a freshly uploaded file for the screen (if it needs it), then queue it."""
    j = jobs[jid]
    try:
        k = media.kind(path.name)
        if j["dir"] in ("video", "clockbg", "pic") and k in ("video", "image"):
            if k == "video" and j["dir"] != "pic":
                info = await media.probe(path)
                vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
                has_audio = any(x.get("codec_type") == "audio" for x in info.get("streams", []))
                already = vs.get("codec_name") == "h264" and vs.get("width") == 480 and vs.get("height") == 480 and not (mute and has_audio)
                if not already:
                    j.update(state="converting", progress=0, touched=time.time())
                    dst = path.with_name(path.stem + ".screen.mp4")
                    await media.video(path, dst, fill, lambda p: j.update(progress=p, touched=time.time()), mute)
                    path.unlink(missing_ok=True)
                    path = dst.rename(path.with_name(path.stem.removesuffix(".screen") + ".mp4"))
            elif k == "image" and j["dir"] in ("pic", "clockbg"):
                j.update(state="converting", progress=0, touched=time.time())
                dst = path.with_name(path.stem + ".screen.jpg")
                await run_in_threadpool(media.image, path, dst, fill)
                path.unlink(missing_ok=True)
                path = dst.rename(path.with_name(path.stem.removesuffix(".screen") + ".jpg"))
        j.update(name=path.name, path=str(path), size=path.stat().st_size, state="queued", touched=time.time())
        enqueue(jid)
    except Exception as e:
        j.update(state="error", error=str(e)[:160], touched=time.time())


@app.post("/api/upload")
async def api_upload(request: Request, dir: str, name: str, convert: int = 1, fill: int = 0, mute: int = 0):
    check_dir(dir)
    name = safe_name(name)
    jid = uuid.uuid4().hex[:8]
    folder = STAGING / jid
    folder.mkdir()
    path = folder / name
    size = int(request.headers.get("content-length", 0))
    job = {"id": jid, "name": name, "dir": dir, "size": size, "state": "uploading", "created": time.time(), "touched": time.time(), "path": str(path)}
    jobs[jid] = job
    got = 0
    try:
        with open(path, "wb") as f:
            async for chunk in request.stream():
                await run_in_threadpool(f.write, chunk)
                got += len(chunk)
    except Exception as e:
        job.update(state="error", error=f"upload interrupted ({e})")
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(400, "upload interrupted")
    job.update(size=got, touched=time.time())
    if convert:
        job["state"] = "processing"
        asyncio.create_task(process(jid, path, bool(fill), bool(mute)))
    else:
        job["state"] = "queued"
        enqueue(jid)
    return {"id": jid}


def _blocked(host):
    import ipaddress, socket
    try:
        for fam, _, _, _, sa in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(sa[0])
            if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                return True
    except Exception:
        return True
    return False


async def grab(jid, url, fill, mute, convert):
    """Download a link on Jarvis (never on the device), then treat it like an upload."""
    import httpx
    from urllib.parse import urlparse, unquote
    j = jobs[jid]
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Ixtli Hub)"}) as c:
            async with c.stream("GET", url) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"the link answered {r.status_code}")
                ctype = r.headers.get("content-type", "")
                if "text/html" in ctype:
                    raise RuntimeError("that link is a web page, not a video file - use the file's direct download link")
                total = int(r.headers.get("content-length", 0))
                cd = r.headers.get("content-disposition", "")
                m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
                name = unquote(m.group(1)) if m else unquote(Path(urlparse(str(r.url)).path).name) or "download"
                name = safe_name(name)
                if media.kind(name) == "other" and j["dir"] in ("video", "pic", "clockbg"):
                    name += ".mp4" if "video" in ctype else ".jpg" if "image" in ctype else ""
                path = STAGING / jid / name
                j.update(name=name, size=total, path=str(path), got=0)
                got = 0
                with open(path, "wb") as f:
                    async for chunk in r.aiter_bytes(262144):
                        f.write(chunk)
                        got += len(chunk)
                        if got > 4_000_000_000:
                            raise RuntimeError("file is over 4 GB")
                        j.update(got=got, touched=time.time())
        j.update(size=path.stat().st_size, touched=time.time())
        if convert:
            j["state"] = "processing"
            await process(jid, path, fill, mute)
        else:
            j["state"] = "queued"
            enqueue(jid)
    except Exception as e:
        j.update(state="error", error=str(e)[:160] or "download failed", touched=time.time())


@app.post("/api/fetch_url")
async def api_fetch_url(body: dict):
    from urllib.parse import urlparse
    url = str(body.get("url", "")).strip()
    d = check_dir(str(body.get("dir", "")))
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname or _blocked(u.hostname):
        raise HTTPException(400, "that is not a usable web link")
    jid = uuid.uuid4().hex[:8]
    (STAGING / jid).mkdir()
    jobs[jid] = {"id": jid, "name": u.hostname, "dir": d, "size": 0, "got": 0, "state": "downloading", "created": time.time(), "touched": time.time(), "path": ""}
    asyncio.create_task(grab(jid, url, bool(body.get("fill")), bool(body.get("mute")), bool(body.get("convert", True))))
    return {"id": jid}


@app.get("/stage/{jid}/{name}")
async def stage(jid: str, name: str):
    p = STAGING / jid / name
    if not re.fullmatch(r"[0-9a-f]{8}", jid) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p)


async def janitor():
    """Clean staged files for finished jobs, expire stuck ones, keep the queue moving."""
    while True:
        await asyncio.sleep(3)
        now = time.time()
        for jid, j in list(jobs.items()):
            if j["state"] == "sending" and now - j.get("touched", now) > 120:
                j.update(state="error", error="device stopped responding")
            if j["state"] in ("done", "error") and now - j.get("touched", now) > 30:
                shutil.rmtree(STAGING / jid, ignore_errors=True)
            if j["state"] in ("done", "error") and now - j["created"] > 3600:
                jobs.pop(jid, None)
        pump()


# --- house panels ---------------------------------------------------------------
def render_and_push(name, force=False):
    img = panels.render(name)
    (PANEL_DIR / f"{name}.jpg").write_bytes(img)
    h = hashlib.sha1(img).hexdigest()
    info = panel_info.setdefault(name, {})
    info["updated"] = time.time()
    if settings["panels_enabled"] and settings["panels"].get(name):
        jid = uuid.uuid4().hex[:8]
        folder = STAGING / jid
        folder.mkdir()
        fname = f"hub_{name}.jpg"
        (folder / fname).write_bytes(img)
        jobs[jid] = {"id": jid, "name": fname, "dir": "pic", "size": len(img), "state": "queued", "created": time.time(), "touched": time.time(), "path": str(folder / fname), "kind": "panel"}
        enqueue(jid)
        info["pushed"] = time.time()
        panel_hash[name] = h


async def panel_loop():
    await asyncio.sleep(20)
    while True:
        if online() and settings["panels_enabled"]:
            for n in panels.PANELS:
                if settings["panels"].get(n):
                    try:
                        await run_in_threadpool(render_and_push, n)
                    except Exception as e:
                        print("panel error", n, e)
        await asyncio.sleep(max(2, settings["interval_min"]) * 60)


@app.get("/api/panel/{name}.jpg")
async def panel_img(name: str):
    if name not in panels.PANELS:
        raise HTTPException(404)
    img = await run_in_threadpool(panels.render, name)
    return Response(img, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/panels/push")
async def panels_push():
    for n in panels.PANELS:
        if settings["panels"].get(n):
            await run_in_threadpool(render_and_push, n, True)
    return {"ok": True}


@app.post("/api/settings")
async def api_settings(body: dict):
    if "panels_enabled" in body:
        settings["panels_enabled"] = bool(body["panels_enabled"])
    if isinstance(body.get("panels"), dict):
        for k, v in body["panels"].items():
            if k in panels.PANELS:
                settings["panels"][k] = bool(v)
    if "interval_min" in body:
        settings["interval_min"] = max(2, min(240, int(body["interval_min"])))
    save_settings(settings)
    return settings


@app.post("/api/panels/remove")
async def panels_remove():
    """Take the hub panels out of the album (deletes hub_*.jpg from /pic)."""
    for n in panels.PANELS:
        cmd("rm", f"pic/hub_{n}.jpg")
    dev["ls"].pop("pic", None)
    return {"ok": True}


# --- Amap look-alike so the weather clock shows US weather (see amap.py / patch_en.py) --
@app.get("/v3/ip")
async def amap_ip():
    return amap.ip_reply()


@app.get("/v3/weather/weatherInfo")
async def amap_weather(extensions: str = "base"):
    fn = amap.forecast_reply if extensions == "all" else amap.live_reply
    return await run_in_threadpool(fn)


# --- over-the-air updates --------------------------------------------------------
FW = ROOT / "fw"
FW_FILES = {"app": "night7", "agent": "hubagent"}


def fw_md5(kind):
    p = FW / FW_FILES[kind]
    return hashlib.md5(p.read_bytes()).hexdigest() if p.is_file() else None


@app.get("/fw/{name}")
async def fw_file(name: str):
    if name not in FW_FILES.values() or not (FW / name).is_file():
        raise HTTPException(404)
    return FileResponse(FW / name)


@app.post("/api/ota")
async def api_ota(body: dict):
    kind = body.get("kind")
    if kind not in FW_FILES:
        raise HTTPException(400)
    m = fw_md5(kind)
    if not m:
        raise HTTPException(404, "no build on the hub")
    have = dev["state"].get("app_md5" if kind == "app" else "agent_md5")
    if have == m[:8] and not body.get("force"):
        return {"ok": True, "note": "already up to date"}
    cmd("ota", {"kind": kind, "url": f"{PUBLIC}/fw/{FW_FILES[kind]}", "md5": m})
    return {"ok": True, "note": "update sent"}


@app.on_event("startup")
async def startup():
    for p in STAGING.iterdir():
        shutil.rmtree(p, ignore_errors=True)
    asyncio.create_task(janitor())
    asyncio.create_task(panel_loop())
