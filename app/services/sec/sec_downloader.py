"""
As-a-service bulk downloader for SEC filings.
Designed to be called from FastAPI *or* a scheduled worker.
"""
from pathlib import Path
from typing import List
import asyncio, httpx, backoff, aiofiles
from app.config import settings
from aiolimiter import AsyncLimiter

import logging
logger = logging.getLogger(__name__)


CACHE_DIR = Path(settings.sec_cache_dir)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class SECDownloader:
    """Download once, serve forever (until you invalidate the cache)."""
    def __init__(self, max_rate = 5, time_period = 1, max_concurrency = 12):
        #self.sem   = asyncio.Semaphore(max_concurrency)
        self.hdrs  = settings.headers
        self.limiter = AsyncLimiter(max_rate, time_period)
        self._client: httpx.AsyncClient | None = None
        self._limits = httpx.Limits(
            max_connections=max_concurrency,
            max_keepalive_connections=max_concurrency,
        )


    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            # http2=True keeps fewer TCP sockets but multiplexes nicely
            self._client = httpx.AsyncClient(http2=True, timeout=30, headers=self.hdrs, limits=self._limits, follow_redirects=True)
        return self._client


    @backoff.on_exception(backoff.expo, httpx.HTTPStatusError, max_time=60, jitter=backoff.full_jitter)
    async def _fetch(self, url: str) -> bytes:
        client = await self._ensure_client()
        async with self.limiter:
            r = await client.get(url)
            if r.status_code in (403, 429):
                retry = int(r.headers.get("Retry-After", "1"))
                logger.warning("⏳ %s — %s. Sleeping %ss",
                            r.status_code, url, retry)
                await asyncio.sleep(retry)
                # raise to trigger backoff retry
                r.raise_for_status()
            r.raise_for_status()
            return r.content


    async def _save(self, url: str, data: bytes) -> Path:
        path = CACHE_DIR / url.split("/")[-1]
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return path


    async def download(self, url: str) -> Path:
        path = CACHE_DIR / url.split("/")[-1]
        if path.exists():
            logger.debug("🔄  cache-hit %s", path.name)
            return path

        logger.info("⬇️  fetching %s", url)
        content = await self._fetch(url)
        return await self._save(url, content)


    async def download_many(self, urls: List[str]) -> List[Path]:
        return await asyncio.gather(*(self.download(u) for u in urls))


    async def aclose(self):
        if self._client:
            await self._client.aclose()