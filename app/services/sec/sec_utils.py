import os
import pandas as pd
from fastapi import Depends, Request
from .sec_parse import SECParsingClient
from .sec_summary import SECSummaryClient


def load_ticker_json():
    filepath = os.path.join("app", "data", "company_tickers.json")

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            "company_tickers.json file not found. Please run update first."
        )

    df = pd.read_json(filepath, orient="index")

    return df


def find_cik(ticker: str) -> str:
    """Find and return the CIK number for the given ticker symbol from saved SEC JSON"""
    try:
        df = load_ticker_json()

        df['cik_str'] = df['cik_str'].astype(str).str.zfill(10)

        ticker = ticker.upper()

        result = df[df["ticker"] == ticker]["cik_str"]

        if not result.empty:
            CIK = str(result.iloc[0])
            return CIK, 1
        else:
            error = f"Ticker '{ticker}' not found in the data."
            return error, 0

    except (ValueError, KeyError) as e:
        error = f"Error loading or parsing company_tickers.json: {e}"
        return error, 0
    

def get_downloader(request: Request):
    return request.app.state.downloader

def get_embedder(request: Request):
    return request.app.state.embedder

def get_embed_model(request: Request):
    return request.app.state.embedding_model

def get_llm(request: Request):
    return request.app.state.llm

def get_wb_retriever(request: Request):
    return request.app.state.wb_retriever

def get_process_pool(request: Request):
    return request.app.state.process_pool

def parsing_client_factory(
    ticker: str,
    downloader = Depends(get_downloader),
    embedder   = Depends(get_embedder),
    process_pool = Depends(get_process_pool)
    ) -> SECParsingClient:
    return SECParsingClient(ticker, downloader, embedder, process_pool)

def summary_client_factory(
    ticker: str,
    llm = Depends(get_llm),
    embedder = Depends(get_embedder)
    ) -> SECSummaryClient:
    return SECSummaryClient(ticker, llm, embedder)