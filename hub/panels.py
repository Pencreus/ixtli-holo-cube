"""House 'glance' panels for the Huanjing Pro photo album (480x480 JPEG).

Design rules: one huge number per screen, plain language, phosphor
terminal look with block-character bars. Everything important stays inside the central
circle (r<=215) so it also works if the glass is round.
"""
import datetime as dt
import os
import io
import math
from PIL import Image, ImageDraw, ImageFont

import ha

W = 480
BG = (0, 0, 0)
GREEN = (74, 255, 130)
DIM = (24, 120, 58)
FAINT = (10, 52, 26)
AMBER = (255, 176, 0)
RED = (255, 72, 64)
WHITE = (205, 255, 220)

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONOB = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def font(size, bold=True):
    return ImageFont.truetype(MONOB if bold else MONO, size)


def _canvas():
    im = Image.new("RGB", (W, W), BG)
    d = ImageDraw.Draw(im)
    # faint ring so the panel reads as a "screen" even on a square glass
    d.ellipse((6, 6, W - 7, W - 7), outline=FAINT, width=2)
    return im, d


def _scanlines(im):
    ov = Image.new("RGB", (W, W), (0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(0, W, 3):
        d.line((0, y, W, y), fill=(0, 0, 0))
    mask = Image.new("L", (W, W), 0)
    md = ImageDraw.Draw(mask)
    for y in range(0, W, 3):
        md.line((0, y, W, y), fill=46)
    return Image.composite(ov, im, mask)


def _center(d, y, text, f, fill=GREEN):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def _bar(pct, cells=20):
    pct = max(0, min(100, pct))
    full = round(cells * pct / 100)
    return "█" * full + "░" * (cells - full)


def _footer(d):
    now = dt.datetime.now().strftime("%-I:%M %p").lower()
    _center(d, 418, f"updated {now}", font(16, False), DIM)


def _to_jpeg(im):
    buf = io.BytesIO()
    _scanlines(im).save(buf, "JPEG", quality=90, subsampling=0, optimize=False, progressive=False)
    return buf.getvalue()


def _compass(deg):
    if deg is None:
        return ""
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((deg + 22.5) % 360 // 45)]


def _cond(text):
    return (text or "").replace("_", " ").replace("-", " ").upper()[:20]


# ---------------------------------------------------------------- panels -------
def weather():
    t = ha.number("sensor.openweathermap_temperature")
    feels = ha.number("sensor.openweathermap_apparent_temperature")
    hum = ha.number("sensor.openweathermap_humidity")
    wind = ha.number("sensor.openweathermap_wind_speed")
    wdir = ha.number("sensor.openweathermap_wind_direction")
    uv = ha.number("sensor.openweathermap_uv_index")
    cond = ha.value("sensor.openweathermap_weather") or ha.value("weather.openweathermap") or ""
    fc = ha.forecast("weather.openweathermap")
    hi = lo = None
    if fc:
        hi, lo = fc[0].get("temperature"), fc[0].get("templow")
    im, d = _canvas()
    _center(d, 44, "OUTSIDE", font(22), DIM)
    _center(d, 78, f"{t:.0f}°" if t is not None else "--", font(170), GREEN)
    _center(d, 268, _cond(cond), font(30), WHITE)
    if hi is not None and lo is not None:
        _center(d, 316, f"HIGH {hi:.0f}°   LOW {lo:.0f}°", font(26), GREEN)
    row = []
    if feels is not None:
        row.append(f"FEELS {feels:.0f}°")
    if hum is not None:
        row.append(f"HUMIDITY {hum:.0f}%")
    _center(d, 356, "   ".join(row), font(20, False), DIM)
    w = f"WIND {wind:.0f} MPH {_compass(wdir)}" if wind is not None else ""
    if uv is not None:
        w += f"   UV {uv:.0f}"
    _center(d, 384, w.strip(), font(20, False), DIM)
    _footer(d)
    return _to_jpeg(im)


def home():
    cur = ha.state("climate.main_floor_temp") or {"state": "?", "attributes": {}}
    a = cur["attributes"]
    t = a.get("current_temperature")
    target = a.get("temperature")
    action = (a.get("hvac_action") or cur["state"] or "").replace("_", " ").upper()
    hum = ha.number("sensor.main_floor_temp_humidity")
    who = ha.state(os.environ.get("HA_PERSON", "person.owner"))
    name = os.environ.get("HA_PERSON_LABEL", "HOME").upper()
    home_txt = f"{name}: HOME" if who and who["state"] == "home" else f"{name}: AWAY"
    out = ha.number("sensor.openweathermap_temperature")
    im, d = _canvas()
    _center(d, 44, "INSIDE", font(22), DIM)
    _center(d, 78, f"{t:.0f}°" if t is not None else "--", font(170), GREEN)
    color = AMBER if action in ("COOLING", "HEATING") else WHITE
    line = action if target is None else f"{action}  SET {target:.0f}°"
    _center(d, 268, line.strip(), font(30), color)
    if hum is not None:
        _center(d, 316, f"HUMIDITY {_bar(hum, 12)} {hum:.0f}%", font(22, False), GREEN)
    if out is not None and t is not None:
        diff = out - t
        _center(d, 354, f"OUTSIDE {out:.0f}°  ({diff:+.0f}°)", font(22, False), DIM)
    _center(d, 384, home_txt, font(22), GREEN if "HOME" in home_txt and "AWAY" not in home_txt else AMBER)
    _footer(d)
    return _to_jpeg(im)


def printer():
    p = "sensor.a1_03919d530601176_"
    status = ha.value(p + "print_status")
    prog = ha.number(p + "print_progress")
    watts = ha.number("sensor.garage_garage_bamabu_a1_power_power")
    im, d = _canvas()
    _center(d, 44, "3D PRINTER", font(22), DIM)
    if status is None:                       # integration unavailable = printer off / asleep
        _center(d, 120, "OFFLINE" if not watts or watts < 5 else "STANDBY", font(70), DIM if not watts or watts < 5 else AMBER)
        _center(d, 250, "not reporting to Home Assistant", font(20, False), DIM)
        if watts is not None:
            _center(d, 296, f"POWER  {watts:.0f} W", font(40), GREEN if watts > 5 else DIM)
    else:
        remaining = ha.number(p + "remaining_time")
        layer = ha.value(p + "current_layer")
        layers = ha.value(p + "total_layer_count")
        nozzle = ha.number(p + "nozzle_temperature")
        bed = ha.number(p + "bed_temperature")
        name = (ha.value(p + "task_name") or "")[:26]
        running = status.lower() in ("running", "printing", "prepare")
        if running and prog is not None:
            _center(d, 70, f"{prog:.0f}%", font(150), GREEN)
            _center(d, 252, _bar(prog, 22), font(26, False), GREEN)
            if remaining is not None:
                h, m = int(remaining), int(round((remaining % 1) * 60))
                _center(d, 296, f"{h}h {m:02d}m LEFT" if h else f"{m} MIN LEFT", font(34), WHITE)
            if layer and layers:
                _center(d, 342, f"LAYER {layer} / {layers}", font(22, False), DIM)
            if name:
                _center(d, 372, name.upper(), font(18, False), DIM)
        else:
            _center(d, 110, status.replace("_", " ").upper(), font(64), WHITE)
            if nozzle is not None and bed is not None:
                _center(d, 250, f"NOZZLE {nozzle:.0f}°   BED {bed:.0f}°", font(26, False), GREEN)
            if watts is not None:
                _center(d, 300, f"POWER  {watts:.0f} W", font(30), DIM)
    _footer(d)
    return _to_jpeg(im)


PANELS = {"weather": weather, "home": home, "printer": printer}
TITLES = {"weather": "Outside weather", "home": "Inside the house", "printer": "3D printer"}


def render(name):
    return PANELS[name]()
