from fastapi import FastAPI

from app.api.v1.router import router as v1_router

app = FastAPI(title="deepaudio API", version="1.0.0")

app.include_router(v1_router, prefix="/api/v1")
