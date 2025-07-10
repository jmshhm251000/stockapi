from llama_index.core.node_parser import TokenTextSplitter
from bs4 import BeautifulSoup
from typing import Tuple
import pandas as pd
import regex as re


def clean_data(
        html: str,
        metadata: dict,
        chunk_size: int = 512,
        chunk_overlap: int = 20,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    def make_page(text: str, page_no: int) -> dict:
        return {
            "company_name": metadata["company_name"],
            "form_type":    metadata["form_type"],
            "date":         metadata["report_date"],
            "page_number":  page_no,
            "page_char_count":      len(text),
            "page_word_count":      len(text.split()),
            "page_sentence_count_raw": len(text.split(". ")),
            "page_token_count":     len(text) // 4,
            "content":      text,
        }

    def find_table_title(table) -> str:
        parent_div = table.find_parent("div")
        while parent_div:
            prev_div = parent_div.find_previous_sibling("div")
            if prev_div:
                title = prev_div.get_text(strip=True)
                if title:
                    return title
                parent_div = prev_div
            else:
                break
        return "No Title Found"

    structured_tables: list[dict] = []
    for i, table in enumerate(tables):
        title = find_table_title(table)
        for x, tr in enumerate(table.find_all("tr")):
            for y, data in enumerate(tr.find_all("td")):
                structured_tables.append(
                    {
                        "company_name": metadata["company_name"],
                        "form_type": metadata["form_type"],
                        "date": metadata["report_date"],
                        "table_number": i,
                        "table_title": title,
                        "row": x,
                        "column": y,
                        "data": data.get_text(strip=True),
                    }
                )


    pages_and_texts: list[dict] = []
    current_page: list[str] = []
    page_number = 0

    for element in soup.stripped_strings:
        if re.match(r"^Page\s+\d+$", element, flags=re.IGNORECASE):
            if current_page:
                text = " ".join(current_page)
                pages_and_texts.append(make_page(text, page_number))
                current_page = []
            page_number += 1
        else:
            current_page.append(element)

    if current_page:
            text = " ".join(current_page)
            pages_and_texts.append(make_page(text, page_number))

    text_df = pd.DataFrame(pages_and_texts)
    table_df = pd.DataFrame(structured_tables)

    text_df["content"].replace("", pd.NA, inplace=True)
    text_df.dropna(subset=["content"], inplace=True)
    text_df.reset_index(drop=True, inplace=True)


    splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    split_content: list[dict] = []

    for _, row in text_df.iterrows():
        for chunk in splitter.split_text(row["content"]):
            split_content.append(
                {
                    "company_name": metadata["company_name"],
                    "form_type": metadata["form_type"],
                    "date": metadata["report_date"],
                    "page_number": row["page_number"],
                    "chunk_char_count": len(chunk),
                    "chunk_word_count": len(chunk.split()),
                    "chunk_sentence_count_raw": len(chunk.split(". ")),
                    "chunk_token_count": len(chunk) // 4,
                    "content_chunk": chunk,
                }
            )

    chunk_text_df = pd.DataFrame(split_content)
    return chunk_text_df, text_df, table_df