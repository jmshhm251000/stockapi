from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List, Tuple
import aiofiles
import pandas as pd
from llama_index.core import Document
from app.config import settings
from .sec_url import SECFilingClient
from app.services.sec.sec_downloader import SECDownloader
from app.services.sec.sec_embedder import SECEmbedder
from .sec_data_process import clean_data

import logging
logger = logging.getLogger(__name__)


HEADERS = settings.headers


class SECParsingClient(SECFilingClient):
    """
    Parse SEC filings into page-, table-, and chunk-level dataframes and
    push chunk Documents into the shared vector store.

    Heavy HTML → text work is delegated to a ProcessPoolExecutor.
    """

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        ticker: str,
        downloader: SECDownloader,
        embedder: SECEmbedder,
        process_pool: ProcessPoolExecutor,
    ) -> None:
        super().__init__(ticker=ticker)
        self.ticker = ticker
        self.downloader = downloader
        self.embedder = embedder
        self.pool: ProcessPoolExecutor = process_pool

        self.filings: list[dict] = []

        self.chunk_text_df: pd.DataFrame | None = None
        self.text_df: pd.DataFrame | None = None
        self.table_df: pd.DataFrame | None = None
        self.chunk_docs: List[Document] | None = None


    async def ingest(self) -> None:
        """Public entry-point (idempotent)."""
        logger.debug("🚀 ingest-called for %s", self.ticker)
        await self._ingest_if_needed()

    async def _ingest_if_needed(self) -> None:
        if self.embedder._col(self.cik).count() > 0:
            return

        lock = self._locks.setdefault(self.cik, asyncio.Lock())
        async with lock:
            if self.embedder._col(self.cik).count() > 0:
                return

            self._fill_filings()
            urls = [f["url"] for f in self.filings]
            html_paths: List[Path] = await self.downloader.download_many(urls)

            await self.parse_filings(html_paths)
            self.embedder.add(self.cik, self.chunk_docs)


    def _fill_filings(self) -> None:
        if self.filing_metadata.empty:
            raise ValueError("filing_metadata is empty. Fetch it first.")

        for i in range(len(self.filing_metadata)):
            acc_no, doc, form, date = self._get_metadata(i)
            self.filings.append(
                {
                    "index": i,
                    "form": form,
                    "report_date": date,
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(self.cik)}/{acc_no}/{doc}",
                }
            )


    async def parse_filings(self, html_paths: List[Path]) -> None:
        logger.info("📝 parsing %d html files for %s", len(html_paths), self.ticker)
        async def _read(path: Path) -> str:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                return await f.read()

        html_texts: List[str] = await asyncio.gather(*(_read(p) for p in html_paths))

        tasks: List[asyncio.Task] = []
        ticker = self.ticker
        for filing, html in zip(self.filings, html_texts, strict=True):
            assert isinstance(html, str)
            metadata = {
                "company_name": ticker,
                "form_type": filing["form"],
                "report_date": filing["report_date"],
            }
            assert isinstance(metadata, dict)
            tasks.append(self.async_clean_data(html, metadata=metadata, executor=self.pool))

        results: List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]] = await asyncio.gather(*tasks)

        chunk_dfs, text_dfs, table_dfs = zip(*results)
        self.chunk_text_df = pd.concat(chunk_dfs, ignore_index=True)
        self.text_df = pd.concat(text_dfs, ignore_index=True)
        self.table_df = pd.concat(table_dfs, ignore_index=True)

        self.chunk_docs = [
            Document(
                text=row["content_chunk"],
                metadata={
                    "company_name": row["company_name"],
                    "form_type": row["form_type"],
                    "date": row["date"],
                    "page_number": row["page_number"],
                    "chunk_word_count": row.get("chunk_word_count", 0),
                    "chunk_token_count": row.get("chunk_token_count", 0),
                },
            )
            for _, row in self.chunk_text_df.iterrows()
        ]
        logger.info("✅ parsed %s — %d chunks", self.ticker, len(self.chunk_docs))


    async def async_clean_data(
        self,
        html: str,
        metadata: dict,
        executor: ProcessPoolExecutor,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            executor, clean_data, html, metadata, chunk_size, chunk_overlap
        )


    def to_csv(
        self,
        chunk_text_path: str | None = None,
        text_path: str | None = None,
        table_path: str | None = None,
    ) -> None:
        if self.chunk_text_df is None:
            raise RuntimeError("Call `parse_filings` first.")

        self.chunk_text_df.to_csv(chunk_text_path or "chunk_text.csv", index=False)
        self.text_df.to_csv(text_path or "text.csv", index=False)
        self.table_df.to_csv(table_path or "table.csv", index=False)
