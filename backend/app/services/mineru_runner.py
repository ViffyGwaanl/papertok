from __future__ import annotations

import os
import subprocess
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MineruResult:
    out_dir: Path
    md_path: Path
    images_dir: Path


def run_mineru_pdf_to_md(
    *,
    pdf_path: str | Path,
    out_root: str | Path,
    model_source: str = "modelscope",
    backend: str = "pipeline",
    method: str = "txt",
    lang: str = "en",
    formula: bool = False,
    table: bool = False,
) -> MineruResult:
    """Run mineru CLI to parse a PDF into markdown + images.

    Notes:
    - We intentionally call mineru via subprocess to avoid multiprocessing/import issues.
    - Output structure (observed):
        {out_root}/{stem}/{method}/{stem}.md
        {out_root}/{stem}/{method}/images/*.jpg
    """

    pdf_path = Path(pdf_path)
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    # Prefer venv-local binary if available; otherwise fall back to PATH.
    venv_mineru = Path(sys.executable).parent / "mineru"
    mineru_exe = str(venv_mineru) if venv_mineru.exists() else (shutil.which("mineru") or "mineru")

    cmd = [
        mineru_exe,
        "-p",
        str(pdf_path),
        "-o",
        str(out_root),
        "-b",
        backend,
        "-m",
        method,
        "-l",
        lang,
        "--formula",
        "true" if formula else "false",
        "--table",
        "true" if table else "false",
        "--source",
        model_source,
    ]

    # Avoid inheriting proxy envs etc.
    env = os.environ.copy()

    subprocess.run(cmd, check=True, env=env)

    stem = pdf_path.stem
    out_dir = out_root / stem / method
    md_path = out_dir / f"{stem}.md"
    images_dir = out_dir / "images"

    return MineruResult(out_dir=out_dir, md_path=md_path, images_dir=images_dir)
