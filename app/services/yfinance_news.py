import yfinance as yf


class NewsClient:
    def __init__(self, ticker: str):
        self.yf_ticker = yf.Ticker(ticker=ticker)
        news = self.yf_ticker.get_news(count=20)

        news_list = []

        for n in news:
            content = n.get("content")
            url = content.get("canonicalUrl").get("url")
            summary = content.get("summary")

            if url and summary:
                news_list.append({
                    "summary": summary,
                    "url": url
                })

        self.news_data = news_list
        #self.sector_news = yf.Search("", news_count = 10)