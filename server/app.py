import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from persistence.store import ensure_dirs, store
from routers.characters import router as characters_router
from routers.export import router as export_router
from routers.generation import router as generation_router
from routers.health import router as health_router
from routers.canonical_base import router as canonical_base_router
from routers.library import router as library_router
from routers.templates import router as templates_router
from services.errors import install_error_handlers


def configure_logging() -> None:
    ensure_dirs()
    logger = logging.getLogger("pixelator")
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    log_file = config.DATA_DIR / "logs" / "pixelator.log"
    try:
        file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.exception("Could not open log file %s", log_file)
    logger.propagate = False
    logging.getLogger("pixelator.generation").setLevel(logging.INFO)
    logging.getLogger("pixelator.jobs").setLevel(logging.INFO)
    logging.getLogger("pixelator.paths").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    ensure_dirs()
    store.seed_if_empty()
    yield


configure_logging()
app = FastAPI(title="Pixelator", version="2.1.0", lifespan=lifespan)
install_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(characters_router)
app.include_router(generation_router)
app.include_router(export_router)
app.include_router(templates_router)
app.include_router(library_router)
app.include_router(canonical_base_router)
ensure_dirs()
app.mount("/data", StaticFiles(directory=str(config.DATA_DIR)), name="data")
