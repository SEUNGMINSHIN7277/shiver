from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT
from .routers.api import router

app = FastAPI(title="K-Rosetta", version="0.1.0")
app.include_router(router)

FRONTEND = REPO_ROOT / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
