from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_QRUN_RE = re.compile(r"\?{2,}")


@dataclass(frozen=True)
class MdQuality:
    length: int
    qmarks: int
    qruns: int
    max_run: int
    qmarks_per_k: float


def measure_md_quality(md_path: str | Path) -> MdQuality:
    p = Path(md_path)
    text = p.read_text(encoding="utf-8", errors="replace")
    length = len(text)
    qmarks = text.count("?")

    runs = list(_QRUN_RE.finditer(text))
    qruns = len(runs)
    max_run = max((len(m.group(0)) for m in runs), default=0)

    denom = max(1.0, length / 1000.0)
    qmarks_per_k = qmarks / denom

    return MdQuality(
        length=length,
        qmarks=qmarks,
        qruns=qruns,
        max_run=max_run,
        qmarks_per_k=qmarks_per_k,
    )


def is_garbled(
    q: MdQuality,
    *,
    qmarks_threshold: int = 80,
    qmarks_per_k_threshold: float = 1.0,
    qruns_threshold: int = 6,
    max_run_threshold: int = 6,
) -> bool:
    """Heuristic gate for "garbled" text caused by PDF text extraction failures.

    We primarily target sequences like "??" "????" inside scientific PDFs where symbols
    cannot be decoded and get replaced by '?'.

    Thresholds are intentionally conservative; tune based on corpus stats.
    """

    if q.length < 2000:
        # Too short: avoid false positives
        return False

    if q.qmarks >= int(qmarks_threshold):
        return True

    if q.qmarks_per_k >= float(qmarks_per_k_threshold) and (
        q.qruns >= int(qruns_threshold) or q.max_run >= int(max_run_threshold)
    ):
        return True

    return False
