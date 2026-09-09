import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import get_settings
from .auth import router as auth_router
from .routes import router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
app = FastAPI(
    title="Folio Private Terminal", docs_url=None, redoc_url=None, openapi_url=None
)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=get_settings().allowed_hosts.split(",")
)


@app.middleware("http")
async def security(request: Request, call_next):
    if request.url.path.startswith("/api") and request.method not in {
        "GET",
        "HEAD",
        "OPTIONS",
    }:
        origin = request.headers.get("origin")
        if origin != get_settings().app_origin:
            return JSONResponse({"detail": "Untrusted request origin"}, status_code=403)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 100000):
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "JSON requests required"}, status_code=415)
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if get_settings().secure_cookies:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    logging.getLogger("app").error(
        "request_failed method=%s error_type=%s", request.method, type(exc).__name__
    )
    return JSONResponse(
        {"detail": "Unexpected server error. Please retry; stored data is preserved."},
        status_code=500,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(router)
dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(dist / "favicon.svg")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return FileResponse(dist / "index.html")
