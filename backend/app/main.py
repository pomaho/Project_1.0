from fastapi import FastAPI

from app.api import api_router

app = FastAPI(title="Photo Keyword Search API")
app.include_router(api_router, prefix="/api")
