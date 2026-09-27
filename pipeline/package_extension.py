"""Package the extension as a store-ready zip.

    python pipeline/package_extension.py     # -> build/artikelfinder-<version>.zip

Needs build/lexicon.json (python pipeline/build_lexicon.py). The dictionary is
exported fresh into a staging folder, so the zip never carries stale data from
extension/data. dev/ and test/ stay out; LICENSE and DATA_LICENSE.md go in.
The zip is deterministic (sorted entries, fixed timestamps): the same inputs
always give a byte-identical file.
"""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "extension"
EXCLUDED_DIRS = {"dev", "test", "data"}  # data/ is exported fresh below
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def source_files():
    """Extension files that ship, relative to extension/."""
    return sorted(
        p.relative_to(EXTENSION) for p in EXTENSION.rglob("*")
        if p.is_file() and p.relative_to(EXTENSION).parts[0] not in EXCLUDED_DIRS
    )


def referenced_files(manifest):
    """Files the manifest points at; a missing one would break the installed extension."""
    refs = [manifest["background"]["service_worker"], manifest["options_ui"]["page"], *manifest["icons"].values()]
    return refs + ["src/bubble.js"]  # injected by background.js via chrome.scripting


def main():
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    staging = ROOT / "build" / "package" / f"artikelfinder-{version}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for rel in source_files():
        (staging / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXTENSION / rel, staging / rel)
    for name in ("LICENSE", "DATA_LICENSE.md"):
        shutil.copy2(ROOT / name, staging / name)
    subprocess.run([sys.executable, str(ROOT / "pipeline/export_runtime.py"), "--out", str(staging / "data")],
                   check=True, stdout=subprocess.DEVNULL)

    missing = [f for f in referenced_files(manifest) + ["data/meta.json"] if not (staging / f).is_file()]
    if missing:
        raise SystemExit(f"package incomplete, missing: {missing}")

    out = ROOT / "build" / f"artikelfinder-{version}.zip"
    files = sorted(p for p in staging.rglob("*") if p.is_file())
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(staging).as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    print(f"{out.relative_to(ROOT)}: {len(files)} files, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
