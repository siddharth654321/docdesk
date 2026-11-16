# app/main.py
from fastapi import FastAPI

from app.config import get_settings
from app.routers import tickets

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(tickets.router)


@app.get("/health")
def health():
    return {"status": "ok"}
