"""Convert uploads into what the Huanjing Pro screen likes: 480x480 H.264/AAC mp4 and
baseline 480x480 JPEG. Runs on Jarvis (ffmpeg + Pillow) so the little device never has to."""
import asyncio
import json
import re
from pathlib import Path

from PIL import Image, ImageOps

SIZE = 480
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv", ".flv", ".ts", ".3gp"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def kind(name):
    ext = Path(name).suffix.lower()
    return "video" if ext in VIDEO_EXT else "image" if ext in IMAGE_EXT else "other"


async def probe(path):
    p = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    out, _ = await p.communicate()
    try:
        return json.loads(out)
    except Exception:
        return {}


async def video(src: Path, dst: Path, fill: bool, progress, mute: bool = False):
    """Re-encode to 480x480 H.264/AAC. `progress(pct)` is called while ffmpeg runs.
    Returns the destination path; raises RuntimeError with a readable message."""
    info = await probe(src)
    vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vs:
        raise RuntimeError("no video track found in that file")
    dur = float(info.get("format", {}).get("duration") or 0)
    if fill:
        vf = f"scale={SIZE}:{SIZE}:force_original_aspect_ratio=increase,crop={SIZE}:{SIZE},fps=30,format=yuv420p"
    else:
        vf = (f"scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease,"
              f"pad={SIZE}:{SIZE}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30,format=yuv420p")
    has_audio = (not mute) and any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    cmd = ["ffmpeg", "-y", "-nostdin", "-v", "error", "-progress", "pipe:1", "-nostats", "-i", str(src),
           "-map", "0:v:0", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-profile:v", "high", "-level", "4.0", "-movflags", "+faststart"]
    if mute:
        cmd += ["-an"]
    if has_audio:
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"]
    cmd.append(str(dst))
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def pump():
        async for raw in p.stdout:
            m = re.match(r"out_time_(?:us|ms)=(\d+)", raw.decode("utf-8", "replace"))
            if m and dur:
                # both out_time_us and out_time_ms are microseconds in ffmpeg's -progress output
                progress(min(99.0, int(m.group(1)) / 1e6 / dur * 100))

    t = asyncio.create_task(pump())
    err = (await p.stderr.read()).decode("utf-8", "replace")
    await p.wait()
    await t
    if p.returncode != 0 or not dst.exists():
        raise RuntimeError("could not convert that video: " + (err.strip().splitlines() or ["unknown error"])[-1][:120])
    return dst


def image(src: Path, dst: Path, fill: bool):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if fill:
            im = ImageOps.fit(im, (SIZE, SIZE), Image.LANCZOS)
        else:
            im = ImageOps.pad(im, (SIZE, SIZE), Image.LANCZOS, color=(0, 0, 0))
        im.save(dst, "JPEG", quality=90, subsampling=0, progressive=False, optimize=False)
    return dst
