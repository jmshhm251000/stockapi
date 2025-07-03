"""
As-a-service bulk downloader for SEC filings.
Designed to be called from FastAPI *or* a scheduled worker.
"""
from pathlib import Path
from typing import List
import asyncio, httpx, backoff, aiofiles
from app.config import settings

CACHE_DIR = Path(settings.sec_cache_dir)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class SecDownloader:
    """Download once, serve forever (until you invalidate the cache)."""
    def __init__(self, max_concurrency: int = 12):
        self.sem   = asyncio.Semaphore(max_concurrency)
        self.hdrs  = settings.headers
        self._client: httpx.AsyncClient | None = None  # lazily created

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            # http2=True keeps fewer TCP sockets but multiplexes nicely
            self._client = httpx.AsyncClient(http2=True, timeout=30, headers=self.hdrs)
        return self._client

    @backoff.on_exception(backoff.expo, httpx.HTTPStatusError, max_time=60)
    async def _fetch(self, url: str) -> bytes:
        client = await self._ensure_client()
        async with self.sem:
            r = await client.get(url)
            r.raise_for_status()
            return r.content

    async def _save(self, url: str, data: bytes) -> Path:
        path = CACHE_DIR / url.split("/")[-1]
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return path

    # ---------- public ----------
    async def download(self, url: str) -> Path:
        path = CACHE_DIR / url.split("/")[-1]
        return path if path.exists() else await self._save(url, await self._fetch(url))

    async def download_many(self, urls: List[str]) -> List[Path]:
        return await asyncio.gather(*(self.download(u) for u in urls))

    # graceful shutdown
    async def aclose(self):
        if self._client:
            await self._client.aclose()