"""Render docs/icon.svg to the PNG sizes the extension needs.

    python pipeline/render_icons.py     # -> extension/icons/icon-{16,32,48,128}.png

Uses headless Chrome with a transparent background; each size is drawn from
the vector source, not scaled down from a large bitmap, so 16 px stays crisp.
A throwaway profile keeps it away from the user's Chrome profile.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs/icon.svg"
OUT = ROOT / "extension/icons"
SIZES = (16, 32, 48, 128)
CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chrome",
)


def find_chrome():
    for candidate in CHROME_CANDIDATES:
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    raise SystemExit("Chrome or Edge not found")


def main():
    chrome = find_chrome()
    svg = SOURCE.read_text(encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for size in SIZES:
            page = Path(tmp) / f"icon-{size}.html"
            page.write_text(
                "<!doctype html><html><body style='margin:0;background:transparent'>"
                f"<div style='width:{size}px;height:{size}px'>{svg.replace('<svg ', f'<svg width={size} height={size} ', 1)}</div>"
                "</body></html>", encoding="utf-8")
            target = OUT / f"icon-{size}.png"
            subprocess.run([
                chrome, "--headless=new", f"--user-data-dir={Path(tmp) / 'profile'}", "--disable-gpu",
                "--hide-scrollbars", "--default-background-color=00000000", "--force-device-scale-factor=1",
                f"--window-size={size},{size}", f"--screenshot={target}", page.as_uri(),
            ], check=True, capture_output=True)
            print(f"{target.relative_to(ROOT)}: {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
