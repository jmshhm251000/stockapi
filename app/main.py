from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse

from app.api.routes import api_router

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

app = FastAPI(
    title="Financial Analysis Platform",
    description="A platform for financial analysis and forecasting",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return FileResponse("app/static/index.html")


@app.get("/portfolio")
async def portfolio():
    return FileResponse("app/static/portfolio.html")
