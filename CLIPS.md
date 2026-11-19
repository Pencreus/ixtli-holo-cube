# Loop library: sources and licences

The card ships empty of vendor videos. This is the free-to-use library the project builds from. Nothing here is committed to the repo,
only the recipe, so you can rebuild it.

## Recipe (what the hub does for every upload)
480x480, H.264 high profile, 30 fps, CRF 23, `+faststart`, no audio, **fill** (centre-crop to square). Black backgrounds look best on the
holo cube because the pyramid only reflects what is lit. Muted on purpose: the device boots silent.

```
ffmpeg -ss <skip> -i in.mp4 -map 0:v:0 \
  -vf "scale=480:480:force_original_aspect_ratio=increase,crop=480:480,fps=30,format=yuv420p" \
  -c:v libx264 -preset veryfast -crf 23 -profile:v high -level 4.0 -movflags +faststart -an out.mp4
```

## Sources
- **Pexels** (Pexels License: free to use, no attribution required). Direct download: `https://www.pexels.com/download/video/<id>/`.
  Look for clips by creators who publish 1-4 minute dark "background" loops (e.g. the long particle clips) and for smoke/ink/flower macro on black.
- **NASA via the Internet Archive** (public domain). "Earth Illuminated" (`archive.org/details/EarthIlluminated`, CC0) and the "NASA Ultra High
  Definition" item (`archive.org/details/NASA-Ultra-High-Definition`, public domain mark): ISS Earth views, 1-3 minutes each, mostly black space.
  They open with a title card, so skip the first 8-12 s (`-ss`).

## Longer clips
Short loops (8-15 s) repeat noticeably. The 1-3 minute clips above (cosmic particles 2 min, ISS Earth views 1-2.5 min, dark smoke 1 min)
keep the display fresh; the card has room (a 2 minute clip is 1-4 MB at this size).
