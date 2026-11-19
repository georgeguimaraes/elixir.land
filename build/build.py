#!/usr/bin/env python3
"""Build index.html from build/atlas.src.html.

Steps: compile build/app.css with the Tailwind CLI (daisyUI comes from build/vendor), then put the CSS and build/data.js into the page.
The script downloads the pinned Tailwind CLI to build/bin on the first run and checks its SHA-256.

build/data.js comes from a private export script that lives with the private dataset, outside this repo.
"""
import hashlib
import platform
import subprocess
from pathlib import Path

TAILWIND = "v4.3.4"
SHA256 = {
    "macos-arm64": "a516a11b439bfbb5ecd4a2d13b75e6cdcc284dc710aed8731e31d2e5c03895a4",
    "linux-x64": "149a8ece5b855587a9c10de6da9dcbcfad0e47c4ed5dca219f721b3eae39d817",
}

HERE = Path(__file__).resolve().parent


def tailwind():
    system = {"Darwin": "macos", "Linux": "linux"}[platform.system()]
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}[platform.machine()]
    target = f"{system}-{arch}"
    binary = HERE / "bin" / f"tailwindcss-{TAILWIND}-{target}"
    if not binary.exists():
        url = f"https://github.com/tailwindlabs/tailwindcss/releases/download/{TAILWIND}/tailwindcss-{target}"
        data = subprocess.run(["curl", "-fsSL", url], check=True, capture_output=True).stdout
        digest = hashlib.sha256(data).hexdigest()
        if digest != SHA256[target]:
            raise SystemExit(f"Checksum mismatch for {url}: {digest}")
        binary.parent.mkdir(exist_ok=True)
        binary.write_bytes(data)
        binary.chmod(0o755)
    return binary


css = subprocess.run(
    [tailwind(), "--input", HERE / "app.css", "--output", "-", "--minify"],
    check=True, capture_output=True, text=True, cwd=HERE,
).stdout
page = (HERE / "atlas.src.html").read_text(encoding="utf-8")
data = (HERE / "data.js").read_text(encoding="utf-8")
for marker in ("/*__CSS__*/", "/*__DATA__*/"):
    assert page.count(marker) == 1, marker
page = page.replace("/*__CSS__*/", css.strip()).replace("/*__DATA__*/", data)
(HERE.parent / "index.html").write_text(page, encoding="utf-8")
print(f"index.html: {len(page.encode()) // 1024} KB, CSS {len(css.encode()) // 1024} KB")
