from pydantic import BaseModel
from dotenv import load_dotenv
import os
from pathlib import Path

# Repo root (papertok/)
_PAPERTOK_ROOT = Path(__file__).resolve().parents[3]

# Load env from project root (single source of truth): papertok/.env
load_dotenv(dotenv_path=_PAPERTOK_ROOT / ".env", override=False)


class Settings(BaseModel):
    hf_daily_papers_url: str = os.getenv(
        "HF_DAILY_PAPERS_URL", "https://huggingface.co/api/daily_papers"
    )
    hf_top_n: int = int(os.getenv("HF_TOP_N", "10"))

    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "http://localhost:3003/v1")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Text model used for lightweight generations (e.g. one-liner)
    llm_model_text: str = os.getenv("LLM_MODEL_TEXT", "glm-x-preview")

    # MVP helper: allow ingest-only runs.
    skip_llm: bool = os.getenv("SKIP_LLM", "").lower() in {"1", "true", "yes"}

    download_pdf: bool = os.getenv("DOWNLOAD_PDF", "").lower() in {"1", "true", "yes"}
    papers_pdf_dir: str = os.getenv(
        "PAPERS_PDF_DIR",
        str(_PAPERTOK_ROOT / "data" / "raw" / "pdfs"),
    )

    # mineru (PDF -> markdown + images)
    run_mineru: bool = os.getenv("RUN_MINERU", "").lower() in {"1", "true", "yes"}
    mineru_out_root: str = os.getenv(
        "MINERU_OUT_ROOT",
        str(_PAPERTOK_ROOT / "data" / "mineru"),
    )
    mineru_model_source: str = os.getenv("MINERU_MODEL_SOURCE", "modelscope")
    mineru_max: int = int(os.getenv("MINERU_MAX", "2"))

    # Optional: attempt PDF repair (into a cache copy) when MinerU fails to parse.
    mineru_repair_on_fail: bool = os.getenv("MINERU_REPAIR_ON_FAIL", "1").lower() in {
        "1",
        "true",
        "yes",
    }
    mineru_repair_tool: str = os.getenv("MINERU_REPAIR_TOOL", "auto")  # auto|qpdf|mutool|gs
    mineru_repair_cache_dir: str = os.getenv(
        "MINERU_REPAIR_CACHE_DIR",
        str(_PAPERTOK_ROOT / "data" / "raw" / "pdfs_repaired"),
    )

    # Languages to generate/store for content fields (affects pipeline stages).
    # Example: PAPERTOK_LANGS=zh,en
    papertok_langs: list[str] = (
        [x.strip().lower() for x in os.getenv("PAPERTOK_LANGS", "zh").split(",") if x.strip()]
        or ["zh"]
    )

    # Optional: analyze parsed markdown into teaching-style explanation.
    run_content_analysis: bool = os.getenv("RUN_CONTENT_ANALYSIS", "").lower() in {
        "1",
        "true",
        "yes",
    }
    content_analysis_max: int = int(os.getenv("CONTENT_ANALYSIS_MAX", "2"))
    content_analysis_input_chars: int = int(os.getenv("CONTENT_ANALYSIS_INPUT_CHARS", "80000"))
    # Model used for long-form explanation
    llm_model_analysis: str = os.getenv("LLM_MODEL_ANALYSIS", llm_model_text)

    # one-liner quality
    # NOTE: historically generated at the end of scripts.daily_run. We keep that behavior,
    # and add RUN_ONE_LINER=1 to allow running the one-liner stage in isolation.
    run_one_liner: bool = os.getenv("RUN_ONE_LINER", "").lower() in {"1", "true", "yes"}
    one_liner_max: int = int(os.getenv("ONE_LINER_MAX", "100000"))

    one_liner_prefer_mineru: bool = os.getenv("ONE_LINER_PREFER_MINERU", "1").lower() in {
        "1",
        "true",
        "yes",
    }
    one_liner_mineru_input_chars: int = int(os.getenv("ONE_LINER_MINERU_INPUT_CHARS", "20000"))
    rewrite_one_liner_from_mineru: bool = os.getenv("REWRITE_ONE_LINER_FROM_MINERU", "").lower() in {
        "1",
        "true",
        "yes",
    }
    rewrite_one_liner_max: int = int(os.getenv("REWRITE_ONE_LINER_MAX", "10"))
    rewrite_one_liner_skip_recent_minutes: int = int(os.getenv("REWRITE_ONE_LINER_SKIP_RECENT_MINUTES", "30"))

    db_url: str = os.getenv(
        "DB_URL",
        f"sqlite:////{_PAPERTOK_ROOT / 'data' / 'db' / 'papertok.sqlite'}",
    )

    cors_allow_origins: list[str] = (
        os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
        if os.getenv("CORS_ALLOW_ORIGINS")
        else ["*"]
    )

    # Security boundary (recommended even for "LAN only")
    # Default: allow only private LAN + localhost.
    allowed_cidrs: list[str] = (
        [x.strip() for x in os.getenv("PAPERTOK_ALLOWED_CIDRS", "").split(",") if x.strip()]
        if os.getenv("PAPERTOK_ALLOWED_CIDRS")
        else [
            "127.0.0.1/32",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "::1/128",
            "fc00::/7",
        ]
    )
    trust_x_forwarded_for: bool = os.getenv("PAPERTOK_TRUST_X_FORWARDED_FOR", "").lower() in {
        "1",
        "true",
        "yes",
    }

    basic_auth_enabled: bool = os.getenv("PAPERTOK_BASIC_AUTH", "").lower() in {
        "1",
        "true",
        "yes",
    }
    basic_auth_user: str = os.getenv("PAPERTOK_BASIC_USER", "")
    basic_auth_pass: str = os.getenv("PAPERTOK_BASIC_PASS", "")

    # Optional admin token for /api/admin/* (if set, client must send X-Admin-Token)
    admin_token: str = os.getenv("PAPERTOK_ADMIN_TOKEN", "")

    # Logs directory (used by admin log viewer / truncation helpers)
    log_dir: str = os.getenv(
        "PAPERTOK_LOG_DIR",
        str(_PAPERTOK_ROOT / "data" / "logs"),
    )

    # Optional: serve built frontend from backend (single-process local deploy)
    frontend_dist_dir: str = os.getenv(
        "FRONTEND_DIST_DIR",
        str(_PAPERTOK_ROOT / "frontend" / "wikitok" / "frontend" / "dist"),
    )

    # Optional: caption MinerU extracted images with a VLM and cache into DB.
    run_image_caption: bool = os.getenv("RUN_IMAGE_CAPTION", "").lower() in {
        "1",
        "true",
        "yes",
    }
    image_caption_model: str = os.getenv("IMAGE_CAPTION_MODEL", "glm-4.6v")
    # Caption ALL extracted images by default (can be limited via env)
    image_caption_max: int = int(os.getenv("IMAGE_CAPTION_MAX", "100000"))
    image_caption_per_paper: int = int(os.getenv("IMAGE_CAPTION_PER_PAPER", "100000"))
    # For each image, take context around the markdown reference (chars)
    image_caption_context_chars: int = int(os.getenv("IMAGE_CAPTION_CONTEXT_CHARS", "2000"))
    # How to pick context when an image is referenced multiple times
    # - merge: merge up to N occurrences
    # - last: only use the last occurrence
    image_caption_context_strategy: str = os.getenv("IMAGE_CAPTION_CONTEXT_STRATEGY", "merge")
    image_caption_context_occurrences: int = int(os.getenv("IMAGE_CAPTION_CONTEXT_OCCURRENCES", "3"))

    # Paper illustration generation (Seedream / GLM-Image)
    run_paper_images: bool = os.getenv("RUN_PAPER_IMAGES", "").lower() in {
        "1",
        "true",
        "yes",
    }
    paper_images_per_paper: int = int(os.getenv("PAPER_IMAGES_PER_PAPER", "3"))
    paper_images_max_papers: int = int(os.getenv("PAPER_IMAGES_MAX_PAPERS", "1"))

    # Which providers to GENERATE for (comma-separated), e.g. "seedream,glm".
    paper_images_providers: list[str] = (
        [x.strip() for x in os.getenv("PAPER_IMAGES_PROVIDERS", "seedream").split(",") if x.strip()]
    )

    # Which provider to DISPLAY on feed cards: seedream|glm|auto
    paper_images_display_provider: str = os.getenv("PAPER_IMAGES_DISPLAY_PROVIDER", "seedream")

    seedream_endpoint: str = os.getenv(
        "SEEDREAM_ENDPOINT",
        "https://ark.cn-beijing.volces.com/api/v3/images/generations",
    )
    seedream_model: str = os.getenv("SEEDREAM_MODEL", "doubao-seedream-4-5-251128")
    seedream_api_key: str = os.getenv("SEEDREAM_API_KEY", "")
    seedream_api_keys_json: str = os.getenv("SEEDREAM_API_KEYS", "")

    paper_gen_images_dir: str = os.getenv(
        "PAPER_GEN_IMAGES_DIR",
        str(_PAPERTOK_ROOT / "data" / "gen_images"),
    )
    # Seedream API currently enforces a minimum pixel count; 1440x2560 is 9:16 and meets the threshold.
    paper_gen_image_size: str = os.getenv("PAPER_GEN_IMAGE_SIZE", "1440x2560")

    # GLM-Image provider (BigModel)
    glm_image_endpoint: str = os.getenv(
        "GLM_IMAGE_ENDPOINT",
        "https://open.bigmodel.cn/api/paas/v4/images/generations",
    )
    glm_image_model: str = os.getenv("GLM_IMAGE_MODEL", "glm-image")
    glm_image_quality: str = os.getenv("GLM_IMAGE_QUALITY", "hd")

    glm_api_key: str = os.getenv("GLM_API_KEY", "")
    glm_api_keys_json: str = os.getenv("GLM_API_KEYS", "")

    paper_gen_images_glm_dir: str = os.getenv(
        "PAPER_GEN_IMAGES_GLM_DIR",
        str(_PAPERTOK_ROOT / "data" / "gen_images_glm"),
    )
    # GLM-Image supports max 2048px; use portrait 9:16 under that cap.
    paper_glm_image_size: str = os.getenv("PAPER_GLM_IMAGE_SIZE", "1088x1920")


settings = Settings()
