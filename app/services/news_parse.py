import feedparser
import time
import json
import os
from typing import List, Dict, Any, Optional
import re
from urllib.parse import quote

class NewsService:
    def __init__(self):
        self.google_url = "https://news.google.com/rss/search?q={query}+stock&hl=en-US&gl=US&ceid=US:en"
        self.sample_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 300  # valid cache duration
    
    
    def get_stock_news(self, symbol: str, limit: int = 10) -> List[Dict[Any, Any]]:
        """
        News regarding the stock symbol
        
        Args:
            symbol: stock symbol (예: AAPL, MSFT)
            limit: # of news returned (기본값: 10)
            
        Returns:
            List[Dict] of News (제목, 링크, 출처, 게시일, 이미지 URL 등 포함)
        """
        # check cache
        current_time = time.time()
        if symbol in self.cache and (current_time - self.cache_time.get(symbol, 0)) < self.cache_duration:
            return self.cache[symbol][:limit]
        
        # generate google rss news url
        query = quote(symbol)
        url = self.google_url.format(query=query)
        
        try:
            # RSS feed parsing
            print(f"Fetching news for {symbol} from {url}")
            feed = feedparser.parse(url)
            
            # debugging
            #print(f"Feed status: {feed.get('status', 'unknown')}")
            #print(f"Feed entries count: {len(feed.entries) if hasattr(feed, 'entries') else 0}")
            
            if not feed.entries:
                print("No entries found in feed")
                return self._get_sample_news(symbol, limit)  # 대체 데이터 반환
            
            news_items = []
            for entry in feed.entries[:limit]:
                item = {
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published,
                    "source": self._extract_source(entry),
                    "image_url": self._extract_image(entry),
                    "summary": self._clean_summary(entry.get("summary", ""))
                }
                news_items.append(item)
            
            # update cache
            self.cache[symbol] = news_items
            self.cache_time[symbol] = current_time
            
            return news_items
        
        except Exception as e:
            print(f"Error fetching news for {symbol}: {str(e)}")
            return self._get_sample_news(symbol, limit)
        
    
    def _extract_source(self, entry: Dict) -> str:
        """뉴스 출처를 추출합니다."""
        if "source" in entry and hasattr(entry.source, "title"):
            return entry.source.title
        
        # 제목에서 출처 추출 시도 (예: "Title - Source")
        if " - " in entry.title:
            return entry.title.split(" - ")[-1]
        
        return "Unknown Source"
    

    def _extract_image(self, entry: Dict) -> Optional[str]:
        """Extract image from news list."""

        if "media_content" in entry:
            for media in entry.media_content:
                if "url" in media:
                    return media["url"]
        
        if "summary" in entry:
            img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
            if img_match:
                return img_match.group(1)
        
        return None
    

    def _clean_summary(self, summary: str) -> str:
        """Remove html tags and return summary."""
        # HTML 태그 제거
        clean_text = re.sub(r'<[^>]+>', '', summary)
        # 여러 공백 제거
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        # 길이 제한
        if len(clean_text) > 200:
            clean_text = clean_text[:197] + "..."
        
        return clean_text
