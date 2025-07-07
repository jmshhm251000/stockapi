"""Batch embedder backed by Chroma (disk) or PGVector (optional)."""
from pathlib import Path
from llama_index.vector_stores.chroma import ChromaVectorStore
import pandas as pd, chromadb
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever
from typing import List
from app.config import settings
import uuid


CHROMA_DIR = Path(settings.sec_vector_db)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

class SECEmbedder:
    def __init__(self, embed_model=None):
        self._embed  = embed_model
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))


    def _col(self, cik: str):
        return self._client.get_or_create_collection(f"sec_{cik.zfill(10)}")

 
    def add(self, cik: str, chunk_docs: List[Document]) -> None:
        col = self._col(cik)
        texts = [doc.text for doc in chunk_docs]
        embeddings = self._embed.get_text_embedding_batch(texts)

        metadatas = [doc.metadata for doc in chunk_docs]
        ids = [str(uuid.uuid4()) for _ in chunk_docs]

        col.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def retriever(self, cik: str, k: int = 20):
        vector_store = ChromaVectorStore(chroma_collection=self._col(cik))
        index = VectorStoreIndex.from_vector_store(embed_model=self._embed, vector_store=vector_store)
        return VectorIndexRetriever(index=index, similarity_top_k=k)
        