from fastapi import APIRouter
from app.api import sec, news


api_router = APIRouter()


api_router.include_router(sec.router, prefix="/sec", tags=["sec"])
api_router.include_router(news.router, prefix="/news", tags=["news"])