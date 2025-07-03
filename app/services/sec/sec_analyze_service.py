from app.config import settings
import pandas as pd
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup
import regex as re
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core import Document
from .sec_url import find_cik, SECFilingClient
import asyncio


headers = settings.headers


class SECAnalyzingClient(SECFilingClient):
    def __init__(self, ticker: str, embedding):
        cik, success = find_cik(ticker)
        if not success:
            raise ValueError(cik)
        self.ticker = ticker
        self.cik = cik
        self.filing_metadata = pd.DataFrame()
        self.filings = []
        self.chunk_text_df = pd.DataFrame()
        self.text_df = pd.DataFrame()
        self.table_df = pd.DataFrame()
        self.embedding = embedding
        
    
    def fill_filings(self):
        if self.filing_metadata.empty:
            raise ValueError("filing_metadata is empty. Fetch it first.")
        
        for i in tqdm(range(len(self.filing_metadata)), desc='Fetching Filings'):
            acc_no, doc, form, date = self.get_metadata(i)
            self.filings.append({
                "index": i,
                "form": form,
                "report_date": date,
                "url": f"https://www.sec.gov/Archives/edgar/data/{self.cik}/{acc_no}/{doc}"
            })


    async def clean_text(self, text: str) -> str:
        return text.replace("\n", " ").strip()

    def find_table_title(self, table):
        parent_div = table.find_parent("div")
        if parent_div:
            prev_div = parent_div.find_previous_sibling("div")
            if prev_div:
                title_text = prev_div.get_text(strip=True)
                if title_text:
                    return title_text
                else:
                    prev_div = prev_div.find_previous_sibling("div")
                if prev_div:
                    return prev_div.get_text(strip=True)
        return "No Title Found"

    async def clean_data(self, html: str, company_name: str, form_type: str, report_date: str, chunk_size=512, chunk_overlap=50) -> pd.DataFrame:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        structured_tables = []

        for i, table in enumerate(tables):
            table_title = self.find_table_title(table)

            for x, tr in enumerate(table.find_all("tr")):
                for y, data in enumerate(tr.find_all("td")):
                    structured_tables.append({
                        "company_name": company_name,
                        "form_type": form_type,
                        "date": report_date,
                        "table_number": i,
                        "table_title": table_title,
                        "row": x,
                        "column": y,
                        "data": data.get_text(strip=True)
                    })


        for table in tables:
            for tr in table.find_all("tr"):
                for data in tr.find_all("td"):
                    data.decompose()

        pages_and_texts = []
        page_number = 0
        current_page = []
        text_cleaning_tasks = []

        for element in soup.body.children:
            if element.name == "hr":
                if text_cleaning_tasks:  # Ensure we have tasks to process
                    texts_list = await asyncio.gather(*text_cleaning_tasks)
                    texts = " ".join(texts_list).strip()
                    if texts:  # Ensure texts are not empty
                        pages_and_texts.append({
                            "company_name": company_name,
                            "form_type": form_type,
                            "date": report_date,
                            "page_number": page_number,
                            "page_char_count": len(texts),
                            "page_word_count": len(texts.split()),
                            "page_sentence_count_raw": len(texts.split(". ")),
                            "page_token_count": len(texts) / 4,
                            "content": re.sub(r"\s*\d+\s*$", "", texts.strip())
                        })
                        page_number += 1

                # Reset lists after an HR tag
                current_page = []
                text_cleaning_tasks = []

            else:
                text_content = element.get_text(" ", strip=True)
                if text_content.strip():  # Only process non-empty text
                    text_cleaning_tasks.append(asyncio.create_task(self.clean_text(text_content)))
                    current_page.append(text_content)  # Ensure text is tracked

        # Add the last page if there's remaining content
        if current_page:
            texts = " ".join(await asyncio.gather(*text_cleaning_tasks)).strip()
            pages_and_texts.append({
                "company_name": company_name,
                "form_type": form_type,
                "date": report_date,
                "page_number": page_number,
                "page_char_count": len(texts),
                "page_word_count": len(texts.split()),
                "page_sentence_count_raw": len(texts.split(". ")),
                "page_token_count": len(texts) / 4,
                "content": re.sub(r"\s*\d+\s*$", "", texts.strip())
            })

        text_df = pd.DataFrame(pages_and_texts)
        table_df = pd.DataFrame(structured_tables)

        text_df = text_df.iloc[1:].reset_index(drop=True)
        text_df["content"] = text_df["content"].replace("", None)
        text_df.dropna(subset=["content"], inplace=True)
        text_df.reset_index(drop=True, inplace=True)

        splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        split_content = []
        chunk_processing_tasks = []

        for _, row in text_df.iterrows():
            chunk_processing_tasks.append(asyncio.to_thread(splitter.split_text, row["content"]))

        chunk_results = await asyncio.gather(*chunk_processing_tasks)

        for row, chunks in zip(text_df.iterrows(), chunk_results):
            for chunk in chunks:
                split_content.append({
                    "company_name": company_name,
                    "form_type": form_type,
                    "date": report_date,
                    "page_number": row[1]["page_number"],
                    "chunk_char_count": len(chunk),
                    "chunk_word_count": len(chunk.split()),
                    "chunk_sentence_count_raw": len(chunk.split(". ")),
                    "chunk_token_count": len(chunk) / 4,
                    "content_chunk": chunk
                })

        chunk_text_df = pd.DataFrame(split_content)

        return chunk_text_df, text_df, table_df


    async def parse_filings(self):
        chunk_text = []
        text = []
        table = []
        response = []

        for file in tqdm(self.filings, desc='fetching response from url'):
            data = requests.get(file['url'], headers=headers)
            response.append(data.text)

        for file, html in tqdm(zip(self.filings, response), desc='preprocessing data', total=len(self.filings)):
            chunk_df, t_df, tab_df = await self.clean_data(html, self.ticker, file['form'], file['report_date'])
            chunk_text.append(chunk_df)
            text.append(t_df)
            table.append(tab_df)

        self.chunk_text_df = pd.concat(chunk_text)
        self.text_df = pd.concat(text)
        self.table_df = pd.concat(table)

        documents = []

        for _, row in self.chunk_text_df.iterrows():
            content = row["content_chunk"]
            metadata = {
                "company_name": row.get("company_name", ""),
                "form_type": row.get("form_type", ""),
                "date": row.get("date", ""),
                "page_number": row.get("page_number", 0),
                "chunk_word_count": row.get("chunk_word_count", 0),
                "chunk_token_count": row.get("chunk_token_count", 0)
            }
            doc = Document(text=content, metadata=metadata)
            documents.append(doc)

        self.vector_index = VectorStoreIndex(documents, embed_model=self.embedding)
        self.retriver = VectorIndexRetriever(index=self.vector_index, similarity_top_k = 20)

    
    def to_csv(self, path_for_chunk_text: str = None, path_for_text: str = None, path_table: str = None):
        if not path_for_chunk_text:
            self.chunk_text_df.to_csv(f"{path_for_chunk_text}")
        if not path_for_text:
            self.text_df.to_csv(f"{path_for_text}")
        if not path_table:
            self.table_df.to_csv(f"{path_table}")

        self.chunk_text_df.to_csv("chunk_text.csv")
        self.text_df.to_csv("text.csv")
        self.table_df.to_csv("table.csv")