"""FastAPI app for the Log Analysis AI HITL dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from api.state import state

_STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.load()
    yield


app = FastAPI(title="Log Analysis AI", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=_STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "alerts_loaded": state.loaded}
