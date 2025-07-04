"""Batch embedder backed by Chroma (disk) or PGVector (optional)."""
from pathlib import Path
from llama_index.vector_stores.chroma import ChromaVectorStore
import pandas as pd, chromadb
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever
from app.config import settings


CHROMA_DIR = Path(settings.sec_vector_db)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

class SecEmbedder:
    def __init__(self, embed_model=None):
        self._embed  = embed_model
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # ------------ helpers ------------
    def _col(self, cik: str):
        return self._client.get_or_create_collection(f"sec_{cik.zfill(10)}")

    # ------------ public -------------
    # TODO - ingestion logic needs modification
    def ingest_dataframe(self, cik: str, df: pd.DataFrame) -> None:
        col = self._col(cik)
        docs = [
            Document(
                text=row["content_chunk"],
                metadata={
                    "ticker":      df.iloc[0]["company_name"],
                    "form":        row["form_type"],
                    "date":        row["date"],
                    "page":        row["page_number"],
                    "chunk_words": row["chunk_word_count"]
                }
            )
            for _, row in df.itertuples()
        ]
        VectorStoreIndex.from_documents(docs, embed_model=self._embed, store=col)

    def retriever(self, cik: str, k: int = 20):
        vector_store = ChromaVectorStore(chroma_collection=self._col(cik))
        index     = VectorStoreIndex.from_vector_store(embed_model=self._embed, vector_store=vector_store)
        sec_retriever = VectorIndexRetriever(index=index, similarity_top_k=5)
        return VectorStoreIndex.from_collection(self._col(cik)).as_retriever(k)
