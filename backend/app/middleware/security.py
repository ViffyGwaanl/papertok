from __future__ import annotations

import base64
import ipaddress
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _parse_cidrs(cidrs: Iterable[str]) -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    for s in cidrs:
        s = (s or "").strip()
        if not s or s == "*":
            continue
        try:
            nets.append(ipaddress.ip_network(s, strict=False))
        except Exception:
            # ignore malformed entries
            continue
    return nets


def _ip_allowed(ip: str, nets: list[ipaddress._BaseNetwork]) -> bool:
    if not nets:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except Exception:
        return False
    return any(addr in n for n in nets)


class ClientIPAllowlistMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        allowed_cidrs: list[str],
        trust_x_forwarded_for: bool = False,
        exempt_paths: set[str] | None = None,
    ):
        super().__init__(app)
        self._raw = allowed_cidrs
        self._nets = _parse_cidrs(allowed_cidrs)
        self._trust_xff = trust_x_forwarded_for
        self._exempt = exempt_paths or set()

    async def dispatch(self, request: Request, call_next):
        # If disabled
        if not self._raw or "*" in self._raw:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in self._exempt:
            return await call_next(request)

        ip = None
        if self._trust_xff:
            xff = request.headers.get("x-forwarded-for")
            if xff:
                ip = xff.split(",")[0].strip()

        if not ip:
            ip = request.client.host if request.client else None

        if not ip or not _ip_allowed(ip, self._nets):
            return JSONResponse(
                {
                    "detail": "Forbidden (client IP not allowed)",
                    "client_ip": ip,
                },
                status_code=403,
            )

        return await call_next(request)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool,
        username: str,
        password: str,
        exempt_paths: set[str] | None = None,
    ):
        super().__init__(app)
        self._enabled = bool(enabled)
        self._user = username
        self._pass = password
        self._exempt = exempt_paths or set()

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in self._exempt:
            return await call_next(request)

        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("basic "):
            b64 = auth.split(" ", 1)[1].strip()
            try:
                raw = base64.b64decode(b64).decode("utf-8", errors="ignore")
                if ":" in raw:
                    u, p = raw.split(":", 1)
                    if u == self._user and p == self._pass:
                        return await call_next(request)
            except Exception:
                pass

        # Prompt browser for credentials
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="PaperTok"'},
        )
