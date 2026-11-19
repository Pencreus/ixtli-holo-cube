#!/usr/bin/env python3
"""The Pencreus boot splash, ported from ~/Projects/pencreus-boot-splash/splash.h (LovyanGFX, 320x240)
to the Ixtli's 480x480 screen. Same palette, same geometry (in 200-unit mark space) and the same
timeline - only the layout is re-centred for a square (and possibly round) glass.

    python3 ixtli_splash.py frames_dir [fps]      # writes frame_0000.png ...
"""
import math
import os
import sys
from multiprocessing import Pool

from PIL import Image, ImageDraw, ImageFont

W = 480
SS = 3                                   # supersampling for anti-aliasing
CX, CY = 240, 196                        # mark centre
U = 1.30                                 # px per mark unit (original: 0.68 at 320x240)
K = 1.5                                  # scale of the original's small text/numeral
DURATION = 5.0
HOLD = 0.8                               # keep the finished frame a moment

BLK, JADE, GOLD = (5, 7, 6), (77, 240, 160), (242, 193, 78)
TEAL, PAPR, DIM, MUTE = (46, 196, 182), (233, 242, 236), (22, 35, 29), (111, 138, 125)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
STAGES = ["starting display", "reading card", "joining wi-fi", "syncing time", "waking up"]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Canvas:
    def __init__(self):
        self.im = Image.new("RGB", (W * SS, W * SS), BLK)
        self.d = ImageDraw.Draw(self.im)

    def P(self, r, a, cx=CX, cy=CY):                      # polar point in mark space
        t = math.radians(a)
        return (cx + r * U * math.sin(t), cy - r * U * math.cos(t))

    def poly(self, pts, col):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=col)

    def circle(self, x, y, r, col):
        self.d.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=col)

    def rot_rect(self, cx, cy, w, h, deg, col):
        t = math.radians(deg)
        c, s = math.cos(t), math.sin(t)
        pts = [(cx + hx * c - hy * s, cy + hx * s + hy * c)
               for hx, hy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
        self.poly(pts, col)

    def out(self):
        return self.im.resize((W, W), Image.LANCZOS)


def build_mark():
    c = Canvas()
    for i in range(32):
        a = i * 11.25
        r1 = 110 if i % 2 == 0 else 103
        c.poly([c.P(97, a - 3.2), c.P(r1, a), c.P(97, a + 3.2)], GOLD)
    c.circle(CX, CY, 95.5 * U, GOLD)
    c.circle(CX, CY, 92.5 * U, BLK)
    c.circle(CX, CY, 68.75 * U, JADE)
    c.circle(CX, CY, 67.25 * U, BLK)
    for i in range(68):
        x, y = c.P(62, i * 360 / 68)
        c.circle(x, y, 1.5 * U, GOLD)
    for a in range(45, 360, 90):
        x, y = c.P(44, a)
        c.rot_rect(x, y, 20 * U, 20 * U, a, TEAL)
        c.rot_rect(x, y, 15.6 * U, 15.6 * U, a, BLK)
        c.rot_rect(x, y, 9 * U, 9 * U, a, TEAL)
    c.circle(CX, CY, 30.5 * U, JADE)
    c.circle(CX, CY, 27.5 * U, BLK)
    return c


MARK = None


def init_worker():
    global MARK
    MARK = build_mark()


def draw_eye(c, t):
    if t < 2.9:
        return
    ry = 1.0
    if t > 2.9:
        ry = 1.0 + 21.0 * min(1.0, (t - 2.9) / 0.4)
    if 3.9 < t < 4.2:
        ry = 22.0 - 20.0 * math.sin((t - 3.9) / 0.3 * math.pi)
    look = 0.0
    if t > 3.3:
        look = math.sin((t - 3.3) * 2.2) * 4.5 * min(1.0, (4.4 - t) / 0.6 + 1.0)
    rx, ryp = 22 * U, max(ry * U, 0.6)
    # eye white
    mask = Image.new("L", c.im.size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse(((CX - rx) * SS, (CY - ryp) * SS, (CX + rx) * SS, (CY + ryp) * SS), fill=255)
    layer = Image.new("RGB", c.im.size, PAPR)
    ld = ImageDraw.Draw(layer)
    ix = CX + look * U

    def lc(x, y, r, col):
        ld.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=col)

    lc(ix, CY, 12.5 * U, TEAL)
    lc(ix, CY, 5.8 * U, BLK)
    lc(ix - 4.5 * U, CY - 4.5 * U, 2.6 * U, PAPR)
    c.im.paste(layer, (0, 0), mask)


def draw_wordmark(c, t):
    a = min(1.0, max(0.0, (t - 3.1) / 0.5))
    if a <= 0:
        return
    s = "THE PENCREUS"
    f = ImageFont.truetype(FONT, int(round(21 * SS)))
    gap = 6 * SS
    widths = [c.d.textlength(ch, font=f) for ch in s]
    total = sum(widths) + gap * (len(s) - 1)
    x = CX * SS - total / 2
    y = (372 + 9 * (1 - a)) * SS
    col = lerp(BLK, PAPR, a)
    for ch, w in zip(s, widths):
        c.d.text((x, y), ch, font=f, fill=col)
        x += w + gap


def draw_status(c, n):
    msg = "ready" if n >= 20 else STAGES[min(4, n // 4)]
    f = ImageFont.truetype(FONT, int(round(16 * SS)))
    w = c.d.textlength(msg, font=f)
    c.d.text((CX * SS - w / 2, 408 * SS), msg, font=f, fill=MUTE)


def draw_numeral(c, n):
    ox, oy = 366, 344
    bars, dots = n // 5, n % 5
    if n == 0:
        c.d.ellipse(((ox + 16.5 - 13.5) * SS, (oy + 12 - 7.5) * SS, (ox + 16.5 + 13.5) * SS, (oy + 12 + 7.5) * SS), outline=JADE, width=int(2 * SS))
        return
    for d in range(dots):
        c.circle(ox + 16.5 + (d - (dots - 1) / 2.0) * 9, oy + 4.5, 3, JADE)
    y0 = 12 if dots else 0
    for b in range(bars):
        y = oy + y0 + b * 8.25
        c.d.rounded_rectangle((ox * SS, y * SS, (ox + 33) * SS, (y + 6) * SS), radius=int(1.5 * SS), fill=JADE)


def frame(t):
    c = Canvas()
    c.im.paste(MARK.im)
    c.d = ImageDraw.Draw(c.im)
    prog = min(1.0, max(0.0, (t - 0.5) / 2.4))
    n = int(prog * 20)
    for i in range(20):
        a = i * 18.0
        x, y = c.P(78.5, a)
        col = JADE if i < n else DIM
        if i == n and t > 0.5 and n < 20:
            col = GOLD
        c.rot_rect(x, y, 10 * U, 13 * U, a, col)
    draw_eye(c, t)
    draw_wordmark(c, t)
    draw_status(c, n)
    draw_numeral(c, n)
    return c.out()


def work(args):
    i, fps, outdir = args
    t = min(i / fps, DURATION)
    frame(t).save(os.path.join(outdir, f"frame_{i:04d}.png"))
    return i


if __name__ == "__main__":
    outdir = sys.argv[1]
    fps = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    os.makedirs(outdir, exist_ok=True)
    total = int((DURATION + HOLD) * fps) + 1
    with Pool(initializer=init_worker) as p:
        for _ in p.imap_unordered(work, [(i, fps, outdir) for i in range(total)]):
            pass
    print("frames:", total)
