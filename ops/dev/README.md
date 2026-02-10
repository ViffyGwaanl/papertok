# ops/dev

Dev helpers that are safe-by-default.

- `run_full_pipeline_existing.sh`
  - Forces `HF_TOP_N=0` and `DOWNLOAD_PDF=0`
  - Runs MinerU → explain → captions → paper_images for existing papers only
  - Intended for dev/regression environments with a frozen dataset
