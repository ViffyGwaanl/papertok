from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.middleware.security import ClientIPAllowlistMiddleware, BasicAuthMiddleware

from app.core.config import settings
from app.db.init_db import init_db
from app.api.papers import router as papers_router
from app.api.status import router as status_router
from app.api.admin import router as admin_router
from app.api.jobs import router as jobs_router

app = FastAPI(title="PaperTok API", version="0.1.0")

# Security boundary (LAN-safe by default):
# - IP allowlist defaults to private subnets; can be disabled by setting PAPERTOK_ALLOWED_CIDRS=*
# - Optional Basic Auth (off by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    # We don't use cookies for the MVP; disabling credentials allows wildcard origins.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    BasicAuthMiddleware,
    enabled=settings.basic_auth_enabled,
    username=settings.basic_auth_user,
    password=settings.basic_auth_pass,
    exempt_paths={"/healthz"},
)

app.add_middleware(
    ClientIPAllowlistMiddleware,
    allowed_cidrs=settings.allowed_cidrs,
    trust_x_forwarded_for=settings.trust_x_forwarded_for,
    exempt_paths={"/healthz"},
)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/healthz")
def healthz():
    return {"ok": True}


# Quiet template leftovers / cached clients (reduces log noise)
@app.api_route("/_vercel/insights/script.js", methods=["GET", "HEAD"])  # type: ignore

def _vercel_insights_script():
    return Response(content="/* disabled */\n", media_type="application/javascript")


@app.api_route("/_vercel/insights/view", methods=["GET", "POST"])  # type: ignore

def _vercel_insights_view():
    return Response(status_code=204)


# Serve local artifacts (MVP): MinerU outputs + downloaded PDFs + generated images
Path(settings.mineru_out_root).mkdir(parents=True, exist_ok=True)
Path(settings.papers_pdf_dir).mkdir(parents=True, exist_ok=True)
Path(settings.paper_gen_images_dir).mkdir(parents=True, exist_ok=True)
Path(settings.paper_gen_images_glm_dir).mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/mineru",
    StaticFiles(directory=settings.mineru_out_root),
    name="mineru",
)
app.mount(
    "/static/pdfs",
    StaticFiles(directory=settings.papers_pdf_dir),
    name="pdfs",
)
app.mount(
    "/static/gen",
    StaticFiles(directory=settings.paper_gen_images_dir),
    name="gen",
)
app.mount(
    "/static/gen_glm",
    StaticFiles(directory=settings.paper_gen_images_glm_dir),
    name="gen_glm",
)


app.include_router(papers_router)
app.include_router(status_router)
app.include_router(admin_router)
app.include_router(jobs_router)


# Optional: serve the built frontend (Vite dist/) from the same origin.
# This avoids running a separate Vite dev server for local viewing.
try:
    dist_dir = Path(settings.frontend_dist_dir)
    if dist_dir.exists() and dist_dir.is_dir():
        # SPA deep links: serve the same index.html for /admin/*
        try:
            from fastapi.responses import FileResponse

            index_html = dist_dir / "index.html"

            @app.api_route("/admin", methods=["GET", "HEAD"])  # type: ignore
            @app.api_route("/admin/{path:path}", methods=["GET", "HEAD"])  # type: ignore
            def _admin_spa(path: str = ""):
                return FileResponse(str(index_html))

        except Exception:
            pass

        app.mount(
            "/",
            StaticFiles(directory=str(dist_dir), html=True),
            name="frontend",
        )
    else:
        # Fallback landing page when dist is missing.
        from fastapi.responses import HTMLResponse

        app.add_api_route(
            "/",
            lambda: HTMLResponse(
                "<h1>PaperTok backend is running</h1>"
                "<p>Frontend dist not found.</p>"
                "<pre>cd frontend/wikitok/frontend && npm install && npm run build</pre>"
            ),
            methods=["GET"],
        )
except Exception:
    # Don't block API if frontend isn't built.
    pass
