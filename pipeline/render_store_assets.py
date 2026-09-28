"""Render the Chrome Web Store images from the real extension code.

    python pipeline/render_store_assets.py    # -> store/*.png

Screenshots are 1280x800 (the store's preferred size) and come from
extension/dev/harness.html in ?shot mode, which runs the real lookup, view and
bubble modules against extension/data. The promo tile (440x280) is
store/promo.html. Re-run after any UI change so the listing never shows an
outdated bubble. Needs extension/data (export_runtime.py --out extension/data).
"""
import functools
import http.server
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).parent))
from render_icons import find_chrome  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "store"

SCREENSHOTS = [
    ("1-tischen.png", "light", "Tischen", True,
     "der, die or das for any word you select",
     "Works on inflected forms: Tischen is der Tisch, dative plural. Full declension included."),
    ("2-leitern.png", "light", "Leitern", False,
     "Every reading, not a guess",
     "Leitern can be die Leiter (ladder) or der Leiter (leader), so both are shown."),
    ("3-dach.png", "dark", "Dach", False,
     "Honest about how sure it is",
     "Every answer says where its gender comes from, and says so when the sources disagree."),
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def screenshot(chrome, profile, url, out, width, height, scheme="light", scale=1.0):
    """Capture width x height CSS px at `scale`: the PNG is (width*scale) x (height*scale)."""
    subprocess.run([
        chrome, "--headless=new", f"--user-data-dir={profile}", "--disable-gpu", "--hide-scrollbars",
        f"--blink-settings=preferredColorScheme={1 if scheme == 'light' else 0}",
        f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
        "--virtual-time-budget=8000", f"--screenshot={out}", url,
    ], check=True, capture_output=True)
    print(f"{out.relative_to(ROOT)}")


def main():
    if not (ROOT / "extension/data/meta.json").exists():
        raise SystemExit("extension/data missing: run python pipeline/export_runtime.py --out extension/data")
    chrome = find_chrome()
    (STORE / "screenshots").mkdir(parents=True, exist_ok=True)
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with tempfile.TemporaryDirectory() as profile:
            for name, scheme, word, expand, caption, sub in SCREENSHOTS:
                query = {"shot": "", "word": word, "caption": caption, "sub": sub}
                if expand:
                    query["expand"] = ""
                # 800x500 at 1.6x = 1280x800: store thumbnails stay readable.
                screenshot(chrome, profile, f"{base}/extension/dev/harness.html?{urlencode(query)}",
                           STORE / "screenshots" / name, 800, 500, scheme, scale=1.6)
            screenshot(chrome, profile, f"{base}/store/about-shot.html",
                       STORE / "screenshots" / "4-about.png", 800, 500, scale=1.6)
            screenshot(chrome, profile, f"{base}/store/promo.html", STORE / "promo-small-440x280.png", 440, 280)
    finally:
        server.shutdown()
    shutil.copy2(ROOT / "extension/icons/icon-128.png", STORE / "icon-128.png")
    print(f"{(STORE / 'icon-128.png').relative_to(ROOT)} (96x96 artwork, 16 px padding)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
