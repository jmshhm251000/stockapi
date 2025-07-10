from fastapi import APIRouter, Query, HTTPException, status
from typing import List, Dict, Any
from app.services.yfinance_news import NewsService

router = APIRouter()
news_service = NewsService()

# TODO - entry points to the news from yfinance
#@router.get("/stock_news")