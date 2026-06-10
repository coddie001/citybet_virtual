#!/usr/bin/env python3
"""Compress default_image in team_fix_imgs for web delivery."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "front_end" / "static" / "img" / "team_fix_imgs"
OUT_WEBP = IMG_DIR / "default_image.webp"
SOURCES = [
    IMG_DIR / "default_image.png",
    IMG_DIR / "default_image.jpg",
    IMG_DIR / "default_image.jpeg",
]


def main() -> None:
    src = next((p for p in SOURCES if p.is_file()), None)
    if not src:
        print("No default_image source found — skip")
        return

    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed — keeping existing default_image files")
        return

    img = Image.open(src)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    max_side = 800
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    img.save(OUT_WEBP, "WEBP", quality=82, method=6)
    size_kb = OUT_WEBP.stat().st_size / 1024
    print(f"Wrote {OUT_WEBP.name} ({size_kb:.1f} KB) from {src.name}")


if __name__ == "__main__":
    main()
