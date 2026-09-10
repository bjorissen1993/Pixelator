from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from persistence.store import ensure_dirs, store
from routers.characters import router as characters_router
from routers.export import router as export_router
from routers.generation import router as generation_router
from routers.health import router as health_router
from routers.templates import router as templates_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    store.seed_if_empty()
    yield


app = FastAPI(title="Pixelator", version="2.0.0", lifespan=lifespan)
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
ensure_dirs()
app.mount("/data", StaticFiles(directory=str(config.DATA_DIR)), name="data")
