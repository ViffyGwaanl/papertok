"""Smoke test for mineru pipeline in-process.

Run:
  source .venv/bin/activate
  python scripts/mineru_smoketest.py

Notes:
- Must use `if __name__ == '__main__'` on macOS because mineru uses multiprocessing.
"""

import os
from pathlib import Path


def main():
    # Use CPU by default (more compatible for dev)
    os.environ.setdefault("MINERU_DEVICE_MODE", "cpu")

    # PyTorch 2.6+ uses weights_only by default; allowlist doclayout_yolo class.
    import torch
    from doclayout_yolo.nn.tasks import YOLOv10DetectionModel

    torch.serialization.add_safe_globals([YOLOv10DetectionModel])

    from mineru.cli.client import main as mineru_cmd

    pdf = Path(
        "/Users/gwaanl/.openclaw/workspace/papertok/data/raw/pdfs/2602.03560.pdf"
    )
    out_dir = Path("/Users/gwaanl/.openclaw/workspace/papertok/data/mineru_test3")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Prefer modelscope in CN networks (more stable than huggingface).
    args = [
        "-p",
        str(pdf),
        "-o",
        str(out_dir),
        "-b",
        "pipeline",
        "-m",
        "txt",
        "--formula",
        "false",
        "--table",
        "false",
        "--source",
        os.getenv("MINERU_MODEL_SOURCE", "modelscope"),
    ]

    print("Running mineru:", " ".join(args))

    # click command invocation
    mineru_cmd.main(args=args, standalone_mode=False)

    print("DONE")


if __name__ == "__main__":
    main()
