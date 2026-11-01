from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from panoctagon.api.database import get_read_engine
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from panoctagon.api.server import app as api

FRONTEND_DIRECTORY = Path(__file__).parents[2] / "frontend" / "dist"
HASHED_ASSET = re.compile(r"-[A-Za-z0-9_-]{8,}\.(?:js|css|woff2?|svg|png|jpe?g|webp)$")


class FrontendFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code < 400:
            immutable = path.startswith("assets/") and HASHED_ASSET.search(Path(path).name)
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable" if immutable else "no-cache"
            )
        return response


def create_app(frontend_directory: Path = FRONTEND_DIRECTORY) -> FastAPI:
    app = FastAPI(title="Panoctagon", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        if not (frontend_directory / "index.html").is_file():
            raise HTTPException(status_code=503, detail="Frontend build unavailable")
        try:
            engine = get_read_engine()
            with engine.connect() as connection:
                connection.execute(text("select count(*) from ufc_events"))
            engine.dispose()
        except Exception:
            raise HTTPException(status_code=503, detail="Database unavailable")
        return {"status": "ready"}

    app.mount("/api", api)
    app.mount("/", FrontendFiles(directory=frontend_directory, html=True, check_dir=False))
    return app


app = create_app()
