from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings


def _load_glm_keys() -> list[str]:
    # 1) backend env: single key
    if settings.glm_api_key and settings.glm_api_key.strip():
        return [settings.glm_api_key.strip()]

    # 2) backend env: JSON array
    if settings.glm_api_keys_json and settings.glm_api_keys_json.strip():
        try:
            keys = json.loads(settings.glm_api_keys_json)
            if isinstance(keys, list):
                return [str(k).strip() for k in keys if str(k).strip()]
        except Exception:
            pass

    # 3) fallback: skill .env (recommended)
    home = Path.home()
    env_candidates = [
        home / ".openclaw" / "skills" / "glm-image" / ".env",
        home / ".claude" / "skills" / "glm-image" / ".env",
    ]

    for env_path in env_candidates:
        try:
            if not env_path.exists():
                continue
            text = env_path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")

                if k == "GLM_API_KEYS" and v:
                    try:
                        keys = json.loads(v)
                        if isinstance(keys, list):
                            out = [str(x).strip() for x in keys if str(x).strip()]
                            if out:
                                return out
                    except Exception:
                        pass

                if k == "GLM_API_KEY" and v:
                    return [v]
        except Exception:
            continue

    # 4) fallback: skill config.json if user creates it
    cfg_candidates = [
        home / ".openclaw" / "skills" / "glm-image" / "config.json",
        home / ".claude" / "skills" / "glm-image" / "config.json",
        home / ".claude" / "config.json",
    ]
    for cfg in cfg_candidates:
        try:
            if not cfg.exists():
                continue
            j = json.loads(cfg.read_text(encoding="utf-8", errors="ignore") or "{}")
            if isinstance(j.get("api_key"), str) and j.get("api_key").strip():
                return [j["api_key"].strip()]
            if isinstance(j.get("apiKeys"), list):
                out = [str(x).strip() for x in j.get("apiKeys") if str(x).strip()]
                if out:
                    return out
        except Exception:
            continue

    return []


_glm_key_index = 0


def _pick_key(keys: list[str]) -> str:
    global _glm_key_index
    if not keys:
        raise ValueError("GLM API key not configured. Put GLM_API_KEY in papertok/.env or in ~/.openclaw/skills/glm-image/.env")
    key = keys[_glm_key_index % len(keys)]
    _glm_key_index = (_glm_key_index + 1) % len(keys)
    return key


@dataclass
class GlmImageResult:
    remote_url: str
    local_path: Path
    sha256: str
    size: str


def glm_image_has_keys() -> bool:
    try:
        return bool(_load_glm_keys())
    except Exception:
        return False


def glm_image_generate(
    *,
    prompt: str,
    size: str,
    out_path: Path,
    quality: Optional[str] = None,
    watermark: bool = False,
    timeout_s: int = 180,
) -> GlmImageResult:
    """Generate and download an image to out_path using BigModel GLM-Image API."""

    keys = _load_glm_keys()
    url = (settings.glm_image_endpoint or "").strip()
    if not url:
        raise ValueError("GLM_IMAGE_ENDPOINT is empty")

    quality = (quality or settings.glm_image_quality or "hd").strip()

    body: dict = {
        "model": settings.glm_image_model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "watermark_enabled": str(bool(watermark)).lower(),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)

    last_err: Exception | None = None
    for _ in range(max(1, len(keys))):
        api_key = _pick_key(keys)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=timeout_s, trust_env=False) as client:
                r = client.post(url, headers=headers, json=body)
                # parse json early
                try:
                    j = r.json()
                except Exception:
                    j = {}

                if not r.is_success:
                    # retryable auth/rate
                    if r.status_code in (401, 403, 429):
                        if r.status_code == 429:
                            import time

                            time.sleep(1.2)
                        last_err = RuntimeError(
                            f"GLM-Image key failed: HTTP {r.status_code}: {str(j)[:2000] or r.text[:2000]}"
                        )
                        continue
                    raise RuntimeError(f"GLM-Image API error HTTP {r.status_code}: {str(j)[:2000] or r.text[:2000]}")

                data = (j.get("data") if isinstance(j, dict) else None) or []
                if not data or not isinstance(data, list) or not data[0].get("url"):
                    raise RuntimeError(f"GLM-Image returned no url: {j}")

                remote_url = data[0]["url"]

                img = client.get(remote_url)
                img.raise_for_status()
                b = img.content

        except Exception as e:
            last_err = e
            continue

        out_path.write_bytes(b)
        sha = hashlib.sha256(b).hexdigest()
        return GlmImageResult(remote_url=remote_url, local_path=out_path, sha256=sha, size=size)

    raise RuntimeError(f"GLM-Image request failed. Last error: {last_err}")
