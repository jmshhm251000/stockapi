from llama_index.llms.llama_cpp import LlamaCPP
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.prompts import PromptTemplate
from .sec_embedder import SECEmbedder
from .sec_url import find_cik
from llama_index.core.vector_stores import MetadataFilter, FilterOperator
from asyncio import Semaphore, get_running_loop
import uuid


sec_template = PromptTemplate(
"""You are a senior buy-side equity analyst renowned for concise, fact-driven notes.
You have access to SEC filings of the target company **and** selected excerpts from
Warren Buffett’s investment writings.

The filings supplied may include:

╭─ Filing cheat-sheet ───────────────────────────────────────────────╮
│ 10-K   – annual report (full audited financials, strategy, risk)  │
│ 10-Q   – quarterly update (recent performance, liquidity)         │
│ 8-K    – unscheduled material events (M&A, management changes)    │
│ 6-K    – foreign issuer update (equivalent to 8-K / 10-Q)         │
│ Form 4 – insider buy/sell transactions                            │
│ DEF 14A – proxy statement (governance, comp, shareholder matters) │
╰────────────────────────────────────────────────────────────────────╯

**Task**

1. Read the filings AND the Buffett passages in *context_str* below.  
2. Synthesise a forward-looking view of the business—not a bullet-point
   regurgitation.  
3. Link every fact or claim to **precise citations** in brackets:
   `[FORM-TYPE YYYY, "Item 1A-Risk Factors"]` or  
   `[BUFFETT, Owner’s Manual §3]`.

--------------------  Documents  --------------------
{context_str}
-----------------------------------------------------

User question:
{query_str}

--------------------  Response format  --------------
**Executive Summary**  (≤ 120 words)  
• …

**Financial Trends & Quality**  
• …

**Key Risks & Mitigations**  
• …

**Insider Activity & Governance**  
• …

**Outlook & Valuation Hooks**  
• …

Citations must follow each bullet or sentence. Do **not** invent data or cite
documents not in the context block.
"""
)


class SECSummaryClient:
    def __init__(self, ticker: str, llm: LlamaCPP, embedder: SECEmbedder, wb_retriever: VectorIndexRetriever, semaphore: Semaphore):
        self.cik = find_cik(ticker)
        self.llm = llm
        self.embedder = embedder
        self.wb = wb_retriever
        self.synthesizer = get_response_synthesizer(llm=self.llm, text_qa_template=sec_template, verbose=False)
        self.sem = semaphore

    async def summarize(self, query: str = "Give me the key risks, opportunities and macro outlook."):
        col = self.embedder._col(self.cik)

        kv = col.get(
            where={"meta_type": "sec_summary", "query": query},
            include=["documents"]
        )

        if kv["count"] > 0:
            return kv["documents"][0]
        
        async with self.sem:
            loop = get_running_loop()
            summary = await loop.run_in_executor(
                None,
                self._summarize(),
                query
            )

        col.add(
            documents=[summary],
            metadatas=[{"meta_type": "sec_summary", "query": query}],
            ids=[str(uuid.uuid4())]
        )
        return summary


    # TODO - need to review model's output to adjust the top_k value and context window
    def _summarize(self, query: str):
        retriever = self.embedder.retriever(self.cik, k=30)
        nodes = retriever.retrieve(query)
        return self.synthesizer.synthesize(query, nodes)