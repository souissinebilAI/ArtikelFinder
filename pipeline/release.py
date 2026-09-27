"""Prepare a release: test everything, set the version, build the zip, commit and tag.

    python pipeline/release.py 0.1.1            # -> commit "Release 0.1.1" + tag v0.1.1
    python pipeline/release.py 0.1.1 --dry-run  # only tests and builds; changes nothing in git

Pushes nothing. Afterwards: git push origin main --tags, then create a GitHub
release for the tag and attach build/artikelfinder-<version>.zip.
Needs build/lexicon.json (python pipeline/build_lexicon.py).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "extension/manifest.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def run(*cmd):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=ROOT, check=True)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def node():
    found = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
    if not Path(found).exists():
        raise SystemExit("node not found; install Node.js 20+ to run the JS tests")
    return found


def parse(version):
    return tuple(int(x) for x in version.split("."))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="new version, e.g. 0.1.1")
    parser.add_argument("--dry-run", action="store_true", help="test and build only; no version change, commit or tag")
    args = parser.parse_args()

    manifest_text = MANIFEST.read_text(encoding="utf-8")
    current = json.loads(manifest_text)["version"]
    if not VERSION.match(args.version):
        raise SystemExit(f"version must look like 1.2.3, got {args.version!r}")
    if not args.dry_run and parse(args.version) <= parse(current):
        raise SystemExit(f"{args.version} is not newer than the current version {current}")
    if git("status", "--porcelain"):
        raise SystemExit("working tree has uncommitted changes; commit or stash them first")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise SystemExit("releases are made from main")
    if not args.dry_run and git("tag", "-l", f"v{args.version}"):
        raise SystemExit(f"tag v{args.version} already exists")

    # Everything the tests read is rebuilt, so they cannot pass on stale data.
    py = sys.executable
    run(py, "pipeline/export_runtime.py")
    run(py, "pipeline/export_runtime.py", "--out", "extension/data")
    run(py, "tests/make_golden.py")
    run(py, "-m", "unittest", "discover", "tests")
    run(node(), "--test", "extension/test/**/*.test.js")

    if args.dry_run:
        run(py, "pipeline/package_extension.py")
        print(f"\ndry run OK: all tests pass and the {current} zip builds; nothing committed")
        return

    MANIFEST.write_text(
        re.sub(r'("version":\s*")[^"]+(")', rf"\g<1>{args.version}\g<2>", manifest_text, count=1),
        encoding="utf-8", newline="\n")
    assert json.loads(MANIFEST.read_text(encoding="utf-8"))["version"] == args.version
    run(py, "pipeline/package_extension.py")
    run("git", "commit", "-q", "-m", f"Release {args.version}", "--", str(MANIFEST.relative_to(ROOT)))
    run("git", "tag", "-a", f"v{args.version}", "-m", f"ArtikelFinder {args.version}")

    print(f"""
Release {args.version} prepared (commit + tag v{args.version}, nothing pushed).
Next:
  git push origin main --tags
  then https://github.com/souissinebilAI/ArtikelFinder/releases/new?tag=v{args.version}
  and attach build/artikelfinder-{args.version}.zip""")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
