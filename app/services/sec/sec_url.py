from app.config import settings
import requests
import json
import os
import pandas as pd


headers = settings.headers


class SECFilingClient:
    def __init__(self, ticker: str):
        cik, success = find_cik(ticker)
        if not success:
            raise ValueError(cik)
        self.cik = cik
        self.filing_metadata, self.success= self._fetch_metadata()


    def _fetch_metadata(self, top_doc: int = 4) -> tuple[int | str, int]:
        try:
            url = f'https://data.sec.gov/submissions/CIK{self.cik}.json'
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            filings = response.json()['filings']['recent']

            df = pd.DataFrame.from_dict(filings)
            df = df[df['form'].isin(["10-K", "10-Q", "8-K", "6-K", "4", "DEF 14A"])]
            df = df.sort_values(by=['form', 'filingDate'], ascending=[True, False])
            df = df.groupby('form').head(top_doc).reset_index(drop=True)

            return df, 1
        except requests.exceptions.RequestException as e:
            return f"Failed to fetch filings metadata for CIK {self.cik}: {e}", 0


    def _get_metadata(self, index: int) -> tuple[str, str, str, str]:
        if self.filing_metadata.empty:
            raise ValueError("filing_metadata is empty. Fetch it first.")

        if index >= len(self.filing_metadata) or index < 0:
            raise IndexError(f"Index {index} is out of bounds. Total available filings: {len(self.filing_metadata)}")


        try:
            row = self.filing_metadata.iloc[index]
            acc_no = row['accessionNumber'].replace("-", "")
            primary_doc = row['primaryDocument']
            form_type = row['form']
            report_date = row['reportDate']
            return acc_no, primary_doc, form_type, report_date
        except IndexError:
            raise IndexError("Index out of range.")


def update_company_tickers_json():
    """Update company_tickers.json from SEC"""
    url = "https://www.sec.gov/files/company_tickers.json"
    data_dir = os.path.join("app", "data")
    os.makedirs(data_dir, exist_ok=True)

    local_filename = os.path.join(data_dir, url.split("/")[-1])

    try:
        with requests.get(url=url, headers=headers, stream=True, timeout=10) as r:
            r.raise_for_status()
            data = r.json()
            with open(local_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return local_filename, 1
    except requests.exceptions.RequestException as e:
        return f"Failed to update company_tickers.json: {e}", 0
    

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