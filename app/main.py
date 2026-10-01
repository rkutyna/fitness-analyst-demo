"""Read-only API and static host for the pre-generated demo bundle.

There is no model, no database and no write path here. At startup every bundle
file is validated with `bundle_schema.load_bundle` (an invalid bundle stops the
process with a clear error), then each API response is serialised once and held
in memory together with its ETag. The static frontend in `web/` is held the
same way.
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .bundle_schema import Bundle, BundleError, load_bundle

log = logging.getLogger("demo")

DEFAULT_BUNDLE_DIR = "/app/bundle"
DEFAULT_WEB_DIR = str(Path(__file__).resolve().parent.parent / "web")
DEFAULT_MAX_AGE = 300

# No inline script or style anywhere: every script and stylesheet is a file
# served from this origin, and the frontend never sets a style attribute.
CSP = "; ".join([
    "default-src 'none'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "font-src 'self'",
    "manifest-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'none'",
])

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}

_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
}


@dataclass(frozen=True)
class Asset:
    body: bytes
    content_type: str
    etag: str


def _asset(body: bytes, content_type: str) -> Asset:
    digest = hashlib.sha256(body).hexdigest()[:32]
    return Asset(body, content_type, f'W/"{digest}"')


def _api_payloads(bundle: Bundle) -> dict[str, Asset]:
    """Every API path mapped to its serialised response."""
    def enc(model) -> Asset:
        return _asset(model.model_dump_json().encode("utf-8"), "application/json")

    out = {"/api/manifest": enc(bundle.manifest), "/api/tree": enc(bundle.tree)}
    for pid, overview in bundle.overviews.items():
        out[f"/api/people/{pid}/overview"] = enc(overview)
    for pid, qa in bundle.person_qa.items():
        out[f"/api/people/{pid}/qa"] = enc(qa)
    for gid, interview in bundle.interviews.items():
        out[f"/api/goals/{gid}/interview"] = enc(interview)
    for gid, plan in bundle.plans.items():
        out[f"/api/goals/{gid}/plan"] = enc(plan)
    for gid, qa in bundle.goal_qa.items():
        out[f"/api/goals/{gid}/qa"] = enc(qa)
    # Optional per goal: present only for a goal whose file is in the bundle.
    for gid, today in bundle.today.items():
        out[f"/api/goals/{gid}/today"] = enc(today)
    for gid, briefs in bundle.briefs.items():
        out[f"/api/goals/{gid}/briefs"] = enc(briefs)
    return out


def _load_web(web_dir: Path) -> dict[str, Asset]:
    if not (web_dir / "index.html").is_file():
        raise RuntimeError(f"Frontend not found: {web_dir}/index.html is missing")
    files: dict[str, Asset] = {}
    for path in sorted(web_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        ctype = _TYPES.get(suffix) or mimetypes.guess_type(path.name)[0] \
            or "application/octet-stream"
        files[path.relative_to(web_dir).as_posix()] = _asset(path.read_bytes(), ctype)
    return files


def _not_modified(request: Request, etag: str) -> bool:
    header = request.headers.get("if-none-match")
    if not header:
        return False
    if header.strip() == "*":
        return True
    wanted = etag.removeprefix("W/")
    return any(tag.strip().removeprefix("W/") == wanted for tag in header.split(","))


def create_app(bundle_dir: str | os.PathLike | None = None,
               web_dir: str | os.PathLike | None = None,
               max_age: int | None = None) -> FastAPI:
    bundle_path = Path(bundle_dir or os.environ.get("BUNDLE_DIR", DEFAULT_BUNDLE_DIR))
    web_path = Path(web_dir or os.environ.get("WEB_DIR", DEFAULT_WEB_DIR))
    if max_age is None:
        max_age = int(os.environ.get("CACHE_MAX_AGE", DEFAULT_MAX_AGE))
    cache_control = f"public, max-age={max_age}"
    # Development only (`make dev`): re-read web/ on every request so edits show
    # up without a restart. Off by default; the container never sets it.
    web_live = os.environ.get("WEB_LIVE") == "1"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            bundle = load_bundle(bundle_path)
        except BundleError as exc:
            for problem in exc.problems:
                log.error("bundle problem: %s", problem)
            raise RuntimeError(
                f"Refusing to start: the bundle at {bundle_path} is invalid "
                f"({len(exc.problems)} problem(s)): " + "; ".join(exc.problems)
            ) from exc
        app.state.bundle = bundle
        app.state.api = _api_payloads(bundle)
        app.state.static = _load_web(web_path)
        log.info("bundle loaded from %s: %d API routes, %d static files",
                 bundle_path, len(app.state.api), len(app.state.static))
        yield

    app = FastAPI(title="fitness-analyst-demo", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    def respond(request: Request, asset: Asset) -> Response:
        headers = {"ETag": asset.etag, "Cache-Control": cache_control}
        if _not_modified(request, asset.etag):
            return Response(status_code=304, headers=headers)
        return Response(asset.body, media_type=asset.content_type, headers=headers)

    def api(request: Request) -> Response:
        payloads = getattr(request.app.state, "api", None)
        if payloads is None:
            raise HTTPException(503, "bundle not loaded")
        asset = payloads.get(request.url.path)
        if asset is None:
            raise HTTPException(404, "not found")
        return respond(request, asset)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(request: Request):
        if getattr(request.app.state, "api", None) is None:
            return JSONResponse({"status": "loading"}, status_code=503)
        return {"status": "ready", "routes": len(request.app.state.api)}

    @app.get("/api/manifest")
    async def manifest(request: Request):
        return api(request)

    @app.get("/api/tree")
    async def tree(request: Request):
        return api(request)

    @app.get("/api/people/{pid}/overview")
    async def person_overview(pid: str, request: Request):
        return api(request)

    @app.get("/api/people/{pid}/qa")
    async def person_qa(pid: str, request: Request):
        return api(request)

    @app.get("/api/goals/{gid}/today")
    async def goal_today(gid: str, request: Request):
        return api(request)

    @app.get("/api/goals/{gid}/briefs")
    async def goal_briefs(gid: str, request: Request):
        return api(request)

    @app.get("/api/goals/{gid}/interview")
    async def goal_interview(gid: str, request: Request):
        return api(request)

    @app.get("/api/goals/{gid}/plan")
    async def goal_plan(gid: str, request: Request):
        return api(request)

    @app.get("/api/goals/{gid}/qa")
    async def goal_qa(gid: str, request: Request):
        return api(request)

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str, request: Request):
        files = _load_web(web_path) if web_live else getattr(request.app.state, "static", None)
        if files is None:
            raise HTTPException(503, "frontend not loaded")
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "not found")
        asset = files.get(path or "index.html")
        if asset is None:
            # A path with a file extension is a missing file; anything else is
            # a client-side route, so hand back the app shell.
            if Path(path).suffix:
                raise HTTPException(404, "not found")
            asset = files["index.html"]
        return respond(request, asset)

    return app


app = create_app()
