# services/cleaner.py

from bs4 import BeautifulSoup
import pandas as pd, re
from llama_index.core.node_parser import TokenTextSplitter
import asyncio
from concurrent.futures import ProcessPoolExecutor

def sync_clean_data(html: str, metadata: dict, chunk_size=512, chunk_overlap=50):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    structured_tables = []
    for i, table in enumerate(tables):
        title = find_table_title(table)
        for x, tr in enumerate(table.find_all("tr")):
            for y, data in enumerate(tr.find_all("td")):
                structured_tables.append({
                    "company_name": metadata["company_name"],
                    "form_type": metadata["form_type"],
                    "date": metadata["report_date"],
                    "table_number": i,
                    "table_title": title,
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

    for element in soup.body.children:
        if element.name == "hr":
            if current_page:
                text = " ".join(current_page).replace("\n", " ").strip()
                pages_and_texts.append(make_page(text, metadata, page_number))
                page_number += 1
            current_page = []
        else:
            text = element.get_text(" ", strip=True)
            if text.strip():
                current_page.append(text)

    if current_page:
        text = " ".join(current_page).replace("\n", " ").strip()
        pages_and_texts.append(make_page(text, metadata, page_number))

    text_df = pd.DataFrame(pages_and_texts)
    table_df = pd.DataFrame(structured_tables)

    text_df = text_df.iloc[1:].reset_index(drop=True)
    text_df["content"] = text_df["content"].replace("", None)
    text_df.dropna(subset=["content"], inplace=True)
    text_df.reset_index(drop=True, inplace=True)

    splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    split_content = []

    for _, row in text_df.iterrows():
        chunks = splitter.split_text(row["content"])
        for chunk in chunks:
            split_content.append({
                "company_name": metadata["company_name"],
                "form_type": metadata["form_type"],
                "date": metadata["report_date"],
                "page_number": row["page_number"],
                "chunk_char_count": len(chunk),
                "chunk_word_count": len(chunk.split()),
                "chunk_sentence_count_raw": len(chunk.split(". ")),
                "chunk_token_count": len(chunk) / 4,
                "content_chunk": chunk
            })

    chunk_text_df = pd.DataFrame(split_content)
    return chunk_text_df, text_df, table_df

def make_page(text: str, metadata: dict, page_number: int) -> dict:
    return {
        "company_name": metadata["company_name"],
        "form_type": metadata["form_type"],
        "date": metadata["report_date"],
        "page_number": page_number,
        "page_char_count": len(text),
        "page_word_count": len(text.split()),
        "page_sentence_count_raw": len(text.split(". ")),
        "page_token_count": len(text) / 4,
        "content": re.sub(r"\s*\d+\s*$", "", text.strip())
    }

def find_table_title(table):
    parent_div = table.find_parent("div")
    if parent_div:
        prev_div = parent_div.find_previous_sibling("div")
        if prev_div:
            title = prev_div.get_text(strip=True)
            if title:
                return title
            prev_div = prev_div.find_previous_sibling("div")
            if prev_div:
                return prev_div.get_text(strip=True)
    return "No Title Found"


_executor = ProcessPoolExecutor(max_workers=4)

async def async_clean_data(html: str, metadata: dict, chunk_size=512, chunk_overlap=50):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, sync_clean_data, html, metadata, chunk_size, chunk_overlap
    )
