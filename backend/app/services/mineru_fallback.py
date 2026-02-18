from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.services.mineru_runner import MineruResult


def merge_mineru_outputs(
    *,
    dst: MineruResult,
    src: MineruResult,
    backup_md: bool = True,
    copy_images: bool = True,
) -> dict:
    """Merge `src` output into `dst` output.

    Current use:
    - dst: method=txt result (stable URL paths in PaperTok)
    - src: method=ocr result (higher robustness for garbled symbols)

    Behavior:
    - Overwrite dst markdown content with src markdown content.
    - Optionally copy extracted images from src/images into dst/images (no deletions).

    Returns a small summary dict for logging.
    """

    dst.md_path.parent.mkdir(parents=True, exist_ok=True)
    dst.images_dir.mkdir(parents=True, exist_ok=True)

    if backup_md and dst.md_path.exists():
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        bak = dst.md_path.with_suffix(dst.md_path.suffix + f".bak.{ts}")
        try:
            shutil.copy2(dst.md_path, bak)
        except Exception:
            pass

    # Overwrite markdown (text)
    md_text = src.md_path.read_text(encoding="utf-8", errors="replace")
    dst.md_path.write_text(md_text, encoding="utf-8")

    copied = 0
    if copy_images and src.images_dir.exists() and src.images_dir.is_dir():
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        for fp in sorted(src.images_dir.iterdir()):
            if not fp.is_file():
                continue
            if fp.suffix.lower() not in exts:
                continue
            out = dst.images_dir / fp.name
            if out.exists():
                continue
            try:
                shutil.copy2(fp, out)
                copied += 1
            except Exception:
                continue

    return {
        "dst_md": str(dst.md_path),
        "src_md": str(src.md_path),
        "copied_images": copied,
    }
