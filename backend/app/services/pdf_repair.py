from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PdfRepairResult:
    ok: bool
    tool: str | None = None
    output_pdf: Path | None = None
    error: str | None = None


def _which(name: str) -> str | None:
    p = shutil.which(name)
    if p:
        return p

    # launchd may have a minimal PATH; try common Homebrew locations
    candidates = [
        f"/opt/homebrew/bin/{name}",
        f"/usr/local/bin/{name}",
        f"/usr/bin/{name}",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def repair_pdf_for_pdfium(
    *,
    input_pdf: str | Path,
    output_pdf: str | Path,
    tool: str = "auto",
) -> PdfRepairResult:
    """Best-effort PDF repair/normalization to improve PDFium compatibility.

    This does NOT modify input_pdf. It writes output_pdf.

    Supported tools:
    - qpdf (preferred)
    - mutool (MuPDF)
    - gs (Ghostscript)

    If tool is not available, returns ok=False with error.
    """

    input_pdf = Path(input_pdf)
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    tool = (tool or "auto").strip().lower()
    candidates = [tool] if tool != "auto" else ["qpdf", "mutool", "gs"]

    last_err: str | None = None

    for t in candidates:
        if t == "qpdf":
            exe = _which("qpdf")
            if not exe:
                last_err = "qpdf not found"
                continue

            # Rewrite/normalize PDF. Keep original filename stem in output.
            cmd = [
                exe,
                "--linearize",
                "--object-streams=disable",
                str(input_pdf),
                str(output_pdf),
            ]

        elif t == "mutool":
            exe = _which("mutool")
            if not exe:
                last_err = "mutool not found"
                continue

            # MuPDF clean: rewrite PDF structure.
            cmd = [exe, "clean", "-gg", "-o", str(output_pdf), str(input_pdf)]

        elif t == "gs":
            exe = _which("gs")
            if not exe:
                last_err = "gs not found"
                continue

            # Ghostscript pdfwrite: re-render/rewrite PDF.
            cmd = [
                exe,
                "-sDEVICE=pdfwrite",
                "-dNOPAUSE",
                "-dBATCH",
                "-dSAFER",
                "-o",
                str(output_pdf),
                str(input_pdf),
            ]

        else:
            last_err = f"unknown tool: {t}"
            continue

        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env=os.environ.copy(),
            )

            # qpdf returns exit code 3 for "succeeded with warnings".
            if t == "qpdf" and r.returncode == 3:
                # Treat as success if output looks valid.
                if output_pdf.exists() and output_pdf.stat().st_size >= 1024:
                    return PdfRepairResult(ok=True, tool=t, output_pdf=output_pdf)

            if r.returncode != 0:
                last_err = (r.stderr or r.stdout or "").strip() or f"repair failed rc={r.returncode}"
                continue

            if not output_pdf.exists() or output_pdf.stat().st_size < 1024:
                last_err = "repair produced empty output"
                continue

            return PdfRepairResult(ok=True, tool=t, output_pdf=output_pdf)
        except Exception as e:
            last_err = str(e)
            continue

    return PdfRepairResult(ok=False, tool=None, output_pdf=None, error=last_err or "no repair tool available")
