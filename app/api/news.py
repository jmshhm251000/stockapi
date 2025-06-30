from fastapi import APIRouter, Query, HTTPException, status
from typing import List, Dict, Any
from app.services.news_service import NewsService

router = APIRouter()
news_service = NewsService()

@router.get("/stock_news")
async def get_stock_news(
    ticker: str = Query(..., description="Stock symbol (ex: AAPL, MSFT)"),
    limit: int = Query(10, ge=1, le=20, description="# of returned news")
):
    try:
        news_items = news_service.get_stock_news(ticker.upper(), limit)
        return {
            "ticker": ticker.upper(),
            "count": len(news_items),
            "news": news_items
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while retrieving the news: {str(e)}"
        )
