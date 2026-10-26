"""Build a finished reel: stock clip + branded HTML overlay + music.

The overlay is rendered the SAME way as the cards — an HTML template through
headless Chrome to a transparent 1080x1920 PNG — so reels match the card brand
exactly (Space Grotesk, navy/gold, the logo badge). ffmpeg then composites the
clip (cover-cropped to 9:16, looped/trimmed), overlays the PNG, mixes music with
fades, and encodes H.264/AAC.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import config
import cards        # render_html injects the logo + uses the Jinja env
import render_card  # headless-Chrome screenshot (transparent background)


def make_reel_overlay(hook, out_png, sub=None, pill="Reel") -> str:
    """Render the branded transparent overlay PNG (1080x1920)."""
    data = {"hook": hook, "sub": sub, "pill": pill}
    out_png = Path(out_png)
    html_path = out_png.with_suffix(".overlay.html")
    html_path.write_text(cards.render_html(data, "reel_overlay.html.j2"), encoding="utf-8")
    # scale=1 -> exact 1080x1920; Chrome's transparent background keeps the video visible.
    render_card.render(html_path, out_png, w=config.REEL_W, h=config.REEL_H, scale=1)
    try:
        html_path.unlink()
    except Exception:
        pass
    return str(out_png)


def make_reel(clip_paths, hook, out_path, music_path=None, seconds=None,
              sub=None, pill="Reel") -> str:
    """Composite SEVERAL short clips (cut together) + branded overlay + optional
    music into a finished reel MP4. ``clip_paths`` may be one path or a list —
    multiple clips make a far more dynamic, engaging reel."""
    seconds = seconds or config.REEL_TARGET_SECONDS
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(clip_paths, (str, Path)):
        clip_paths = [clip_paths]
    clips = [str(c) for c in clip_paths if c]
    if not clips:
        raise ValueError("no clips provided for reel")
    n = len(clips)
    seg = seconds / n           # each clip fills an equal slice of the reel

    overlay_png = out_path.with_suffix(".overlay.png")
    make_reel_overlay(hook, overlay_png, sub=sub, pill=pill)

    cmd = [config.FFMPEG, "-y"]
    for c in clips:
        # loop each clip a bit so a short one still fills its slice
        cmd += ["-stream_loop", "2", "-i", c]
    cmd += ["-i", str(overlay_png)]                       # index n: overlay
    if music_path:
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]  # index n+1: music

    fade = 0.6
    parts = []
    for i in range(n):
        parts.append(
            f"[{i}:v]trim=0:{seg:.3f},setpts=PTS-STARTPTS,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,fps=30[v{i}]"
        )
    concat_in = "".join(f"[v{i}]" for i in range(n))
    parts.append(f"{concat_in}concat=n={n}:v=1:a=0[cat]")
    parts.append(
        f"[cat][{n}:v]overlay=0:0:format=auto,"
        f"fade=t=in:st=0:d={fade},fade=t=out:st={seconds - fade:.2f}:d={fade}[v]"
    )
    vfilter = ";".join(parts)

    if music_path:
        afilter = (f"[{n + 1}:a]afade=t=in:st=0:d=1,"
                   f"afade=t=out:st={seconds - 1.5:.2f}:d=1.5,volume=0.85[a]")
        cmd += ["-filter_complex", vfilter + ";" + afilter, "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-filter_complex", vfilter, "-map", "[v]"]

    cmd += [
        "-t", str(seconds),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-preset", "medium", "-crf", "20", "-r", "30",
    ]
    if music_path:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(out_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        overlay_png.unlink()
    except Exception:
        pass
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-1500:]}")
    return str(out_path)
