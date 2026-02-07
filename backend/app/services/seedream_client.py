from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings


ARK_DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"


def _load_seedream_keys() -> list[str]:
    # 1) backend env: single key
    if settings.seedream_api_key and settings.seedream_api_key.strip():
        return [settings.seedream_api_key.strip()]

    # 2) backend env: JSON array
    if settings.seedream_api_keys_json and settings.seedream_api_keys_json.strip():
        try:
            keys = json.loads(settings.seedream_api_keys_json)
            if isinstance(keys, list):
                return [str(k).strip() for k in keys if str(k).strip()]
        except Exception:
            pass

    # 3) fallback: reuse keys from the OpenClaw seedream-image skill config (round-robin)
    # This keeps secrets out of the repo and avoids duplicating key config.
    home = Path.home()

    config_candidates = [
        home / ".openclaw" / "skills" / "seedream-image" / "config.json",
        home / ".claude" / "skills" / "seedream-image" / "config.json",
        home / ".claude" / "config.json",
    ]

    for cfg in config_candidates:
        try:
            if not cfg.exists():
                continue
            j = json.loads(cfg.read_text(encoding="utf-8", errors="ignore") or "{}")

            # Preferred: apiKeys array
            if isinstance(j.get("apiKeys"), list):
                out = [str(x).strip() for x in j.get("apiKeys") if str(x).strip()]
                if out:
                    return out

            # Alternative: seedream_api_key single
            if isinstance(j.get("seedream_api_key"), str) and j.get("seedream_api_key").strip():
                return [j.get("seedream_api_key").strip()]
        except Exception:
            continue

    # 4) fallback: read skill .env if present
    env_candidates = [
        home / ".openclaw" / "skills" / "seedream-image" / ".env",
        home / ".claude" / "skills" / "seedream-image" / ".env",
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

                if k == "SEEDREAM_API_KEYS" and v:
                    try:
                        keys = json.loads(v)
                        if isinstance(keys, list):
                            out = [str(x).strip() for x in keys if str(x).strip()]
                            if out:
                                return out
                    except Exception:
                        pass

                if k == "SEEDREAM_API_KEY" and v:
                    return [v]
        except Exception:
            continue

    return []


_seedream_key_index = 0


def _pick_key(keys: list[str]) -> str:
    global _seedream_key_index
    if not keys:
        raise ValueError("Seedream API key not configured. Set SEEDREAM_API_KEY or SEEDREAM_API_KEYS in papertok/.env")
    key = keys[_seedream_key_index % len(keys)]
    _seedream_key_index = (_seedream_key_index + 1) % len(keys)
    return key


@dataclass
class SeedreamResult:
    remote_url: str
    local_path: Path
    sha256: str
    size: str


def seedream_has_keys() -> bool:
    try:
        return bool(_load_seedream_keys())
    except Exception:
        return False


def seedream_generate_image(
    *,
    prompt: str,
    size: str,
    out_path: Path,
    negative_prompt: Optional[str] = None,
    watermark: bool = False,
    timeout_s: int = 180,
) -> SeedreamResult:
    """Generate and download an image to out_path.

    Uses Volcano Engine Ark Seedream API.
    """

    keys = _load_seedream_keys()
    url = (settings.seedream_endpoint or ARK_DEFAULT_ENDPOINT).strip()

    body: dict = {
        "model": settings.seedream_model,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": watermark,
        "sequential_image_generation": "disabled",
        "stream": False,
    }
    if negative_prompt:
        body["negative_prompt"] = negative_prompt

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Round-robin over keys on retryable errors
    last_err: Exception | None = None
    for _ in range(max(1, len(keys))):
        api_key = _pick_key(keys)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=timeout_s, trust_env=False) as client:
                r = client.post(url, headers=headers, json=body)

                # Try parse JSON error payload early
                try:
                    j = r.json()
                except Exception:
                    j = {}

                if not r.is_success:
                    if r.status_code in (401, 403, 429):
                        # retryable: try next key; add a tiny backoff for 429
                        if r.status_code == 429:
                            import time

                            time.sleep(1.2)
                        last_err = RuntimeError(
                            f"Seedream API key failed: HTTP {r.status_code}: {str(j)[:2000] or r.text[:2000]}"
                        )
                        continue

                    # Non-retryable API error
                    msg = None
                    if isinstance(j, dict):
                        msg = (
                            (j.get("error") or {}).get("message")
                            if isinstance(j.get("error"), dict)
                            else None
                        )
                    msg = msg or (r.text[:2000] if isinstance(r.text, str) else "")
                    raise RuntimeError(f"Seedream API error HTTP {r.status_code}: {msg}")

                data = (j.get("data") if isinstance(j, dict) else None) or []
                if not data:
                    raise RuntimeError(f"Seedream returned no data: {j}")
                remote_url = data[0].get("url")
                if not remote_url:
                    raise RuntimeError(f"Seedream returned no url: {j}")

                img = client.get(remote_url)
                img.raise_for_status()
                b = img.content

        except Exception as e:
            last_err = e
            continue

        # success
        out_path.write_bytes(b)
        sha = hashlib.sha256(b).hexdigest()
        return SeedreamResult(remote_url=remote_url, local_path=out_path, sha256=sha, size=size)

    raise RuntimeError(f"Seedream request failed. Last error: {last_err}")
