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


def make_reel(clip_path, hook, out_path, music_path=None, seconds=None,
              sub=None, pill="Reel") -> str:
    """Composite clip + branded overlay + optional music into a finished reel MP4."""
    seconds = seconds or config.REEL_TARGET_SECONDS
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    overlay_png = out_path.with_suffix(".overlay.png")
    make_reel_overlay(hook, overlay_png, sub=sub, pill=pill)

    fade = 0.6
    vfilter = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,fps=30[bg];"
        "[bg][1:v]overlay=0:0:format=auto,"
        f"fade=t=in:st=0:d={fade},fade=t=out:st={seconds - fade:.2f}:d={fade}[v]"
    )

    cmd = [
        config.FFMPEG, "-y",
        "-stream_loop", "-1", "-i", str(clip_path),   # 0: video (looped)
        "-i", str(overlay_png),                        # 1: overlay
    ]
    if music_path:
        cmd += ["-stream_loop", "-1", "-i", str(music_path)]  # 2: music (looped)
        afilter = (
            f"[2:a]afade=t=in:st=0:d=1,"
            f"afade=t=out:st={seconds - 1.5:.2f}:d=1.5,volume=0.85[a]"
        )
        filter_complex = vfilter + ";" + afilter
        cmd += ["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"]
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
