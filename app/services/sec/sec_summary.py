from .sec_embedder import SECEmbedder
from llama_index.llms.llama_cpp import LlamaCPP
from .sec_utils import find_cik


class SECSummaryClient:
    def __init__(self, ticker: str, llm: LlamaCPP, embedder: SECEmbedder):
        self.cik = find_cik(ticker)
        self.llm = llm
        self.embedder = embedder


