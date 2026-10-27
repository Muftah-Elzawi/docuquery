from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import admin, auth, documents

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="DocuQuery",
    description="Multi-tenant document Q&A (RAG) and field extraction for business documents.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
