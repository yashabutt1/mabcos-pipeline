#!/bin/bash
# Installs a static ffmpeg + ffprobe into ./bin (gitignored, so not restored by
# git). Run this once, and again if reels ever stop rendering ("ffmpeg missing").
# Source: ffbinaries.com (prebuilt static macOS binaries, no Homebrew needed).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$PROJECT_DIR/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

mkdir -p "$PROJECT_DIR/bin"
cd "$PROJECT_DIR"

"$PY" - <<'PY'
import requests, zipfile, io, os, platform
plat = "osx-64" if platform.system() == "Darwin" else "linux-64"
api = requests.get("https://ffbinaries.com/api/v1/version/latest", timeout=30).json()
b = api["bin"][plat]
for name in ("ffmpeg", "ffprobe"):
    data = requests.get(b[name], timeout=180).content
    zipfile.ZipFile(io.BytesIO(data)).extract(name, "bin")
    os.chmod(os.path.join("bin", name), 0o755)
    print(f"installed bin/{name}")
print("ffbinaries version:", api.get("version"))
PY

# Clear macOS quarantine so the unsigned binaries run.
xattr -dr com.apple.quarantine "$PROJECT_DIR/bin/ffmpeg" "$PROJECT_DIR/bin/ffprobe" 2>/dev/null || true
"$PROJECT_DIR/bin/ffmpeg" -version | head -1
echo "ffmpeg ready."
