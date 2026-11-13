"""Point d'entrée de l'API BiblioTrack (application factory)."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api import admin, auth, catalog, circulation, users
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.domain.errors import BusinessRuleError, NotFoundError, PermissionDeniedError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("biblio")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"
# La documentation Swagger charge ses ressources depuis un CDN : CSP dédiée.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
)


def init_database() -> None:
    import app.models  # noqa: F401  (enregistre les tables)

    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    if settings.seed_on_startup:
        from app.seed import seed

        with SessionLocal() as db:
            seed(db)
    from app.services.circulation import run_maintenance

    with SessionLocal() as db:
        run_maintenance(db)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().init_on_startup:
        init_database()
    yield


def _error(code: int, detail: str, rule: str | None = None) -> JSONResponse:
    body = {"detail": detail}
    if rule:
        body["code"] = rule
    return JSONResponse(status_code=code, content=body)


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessRuleError)
    async def _business(_: Request, exc: BusinessRuleError) -> JSONResponse:
        return _error(status.HTTP_409_CONFLICT, exc.message, exc.code)

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return _error(status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(PermissionDeniedError)
    async def _forbidden(_: Request, exc: PermissionDeniedError) -> JSONResponse:
        return _error(status.HTTP_403_FORBIDDEN, str(exc))

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        log.warning("Conflit d'intégrité rejeté par la base : %s", exc.orig.__class__.__name__)
        return _error(
            status.HTTP_409_CONFLICT,
            "Opération concurrente ou doublon détecté : rien n'a été enregistré.",
            "INTEGRITE",
        )

    @app.exception_handler(OperationalError)
    async def _db_down(_: Request, exc: OperationalError) -> JSONResponse:
        log.error("Base de données indisponible : %s", exc.__class__.__name__)
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Service temporairement indisponible, réessayez dans un instant.",
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Erreur inattendue", exc_info=exc)
        return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "Erreur interne.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="1.0.0",
        description="Gestion de médiathèque — projet qualité logicielle ISO/IEC 25010",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_and_timing(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        is_docs = request.url.path in ("/api/docs", "/api/openapi.json")
        response.headers["Content-Security-Policy"] = DOCS_CSP if is_docs else API_CSP
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        return response

    register_handlers(app)
    for router in (
        auth.router,
        users.router,
        catalog.router,
        circulation.router,
        admin.router,
        admin.health_router,
    ):
        app.include_router(router)
    return app


app = create_app()
