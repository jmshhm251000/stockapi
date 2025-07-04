from fastapi import APIRouter, status, Query
from fastapi.responses import JSONResponse
from typing import List, Dict
from app.services.sec.sec_url import update_company_tickers_json, find_cik, SECFilingClient


router = APIRouter()


@router.get("/update_tickers")
async def update_tickers_json():
    msg, error_code = update_company_tickers_json()

    message = "Update successful" if error_code == 1 else f"Update failed: {msg}"
    code = status.HTTP_200_OK if error_code == 1 else status.HTTP_500_INTERNAL_SERVER_ERROR

    return JSONResponse(content={"message": message}, status_code=code)


@router.get("/cik")
async def get_cik(ticker: str):
    result, error_code = find_cik(ticker=ticker)

    code = status.HTTP_200_OK if error_code == 1 else status.HTTP_500_INTERNAL_SERVER_ERROR

    return JSONResponse(content={"ticker": ticker.upper(), "result": result}, status_code=code)


@router.get("/sec_doc_urls")
def get_sec_doc_urls(
    ticker: str,
    top: int = Query(4, ge=1, le=10, description="How many top filings to consider")
):
    cik, success = find_cik(ticker)
    if not success:
        return JSONResponse(
            content={"error": cik},
            status_code=status.HTTP_404_NOT_FOUND
        )

    try:
        client = SECFilingClient(ticker)
        meta, meta_ok = client.fetch_metadata(top)
        if meta_ok == 0:
            return JSONResponse(
                content={"error": meta},
                status_code=status.HTTP_502_BAD_GATEWAY
            )

        filings: List[Dict] = []
        for i in range(len(client.filing_metadata)):
            acc_no, doc, form, date = client.get_metadata(i)
            filings.append({
                "index": i,
                "form": form,
                "report_date": date,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(client.cik)}/{acc_no}/{doc}"
            })

        return {
            "ticker": ticker.upper(),
            "cik": client.cik,
            "filings": filings
        }

    except (IndexError, ValueError) as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=status.HTTP_400_BAD_REQUEST
        )
