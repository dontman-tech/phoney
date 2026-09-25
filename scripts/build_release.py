"""Release packaging helper — builds a distributable wheel + sdist for Phoney."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def build() -> int:
    root = Path(__file__).parent.parent
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    for f in dist.glob("*"):
        f.unlink()
    r = subprocess.run([sys.executable, "setup.py", "sdist", "bdist_wheel"],
                       cwd=root, capture_output=True, text=True)
    print(r.stdout[-1500:] if r.stdout else "", file=sys.stderr)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
    else:
        for f in sorted(dist.iterdir()):
            print(f"built: {f.name} ({f.stat().st_size} bytes)")
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(build())
