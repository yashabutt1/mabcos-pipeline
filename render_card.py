"""Render an HTML card to a crisp PNG at the feed size using headless Chromium.

This replaces the old Pillow quote-card renderer. HTML/CSS gives full design
control (brand colors, web fonts, icons, data-viz, carousels) so cards look
designed, not auto-generated.

    python render_card.py input.html output.png [--w 1080] [--h 1350] [--scale 2]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import os
import shutil
import subprocess
import tempfile

# Playwright doesn't ship Chromium for macOS 13, so we drive the system browser
# directly in headless mode — no extra download, and it's fully scriptable.
_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def _chrome() -> str:
    env = os.getenv("CHROME_BIN", "").strip()
    if env and os.path.exists(env):
        return env
    for c in _CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    raise RuntimeError("No Chrome/Chromium found. Set CHROME_BIN to a browser binary.")


def render(html_path, out_path, w: int = 1080, h: int = 1350, scale: int = 2) -> str:
    """Screenshot an HTML file to PNG at w*scale × h*scale via headless Chrome."""
    html_path = Path(html_path).resolve()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            _chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-sandbox", f"--user-data-dir={profile}",
            f"--force-device-scale-factor={scale}",
            "--default-background-color=00000000",
            # Advance virtual time so async web-font loading completes before the
            # screenshot (otherwise text can fall back to a serif).
            "--virtual-time-budget=4000", "--timeout=15000",
            f"--window-size={w},{h}",
            f"--screenshot={out_path}", html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    if not out_path.exists():
        raise RuntimeError("Chrome headless did not produce an image")
    return str(out_path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("out")
    ap.add_argument("--w", type=int, default=1080)
    ap.add_argument("--h", type=int, default=1350)
    ap.add_argument("--scale", type=int, default=2)
    a = ap.parse_args(argv)
    print(render(a.html, a.out, a.w, a.h, a.scale))


if __name__ == "__main__":
    main(sys.argv[1:])
