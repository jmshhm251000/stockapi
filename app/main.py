from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from aioprometheus import Registry, Counter, Histogram
from aioprometheus.asgi.starlette import metrics

from app.api.routes import api_router
from .setup import construct_db_llm
from .services.sec.sec_downloader import SecDownloader
from .services.sec.sec_embedder import SecEmbedder

from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    embed_model, wb_retriever, llm = construct_db_llm()
    app.state.embedding_model = embed_model
    app.state.wb_retriever    = wb_retriever
    app.state.llm             = llm

    app.state.downloader = SecDownloader()
    app.state.embedder   = SecEmbedder(embed_model)


    reg = Registry()
    app.state.counter = Counter("req_total", "requests")
    app.state.latency = Histogram("req_latency", "latency", buckets=[.1,.5,1,1.5,2])
    reg.register(app.state.counter)
    reg.register(app.state.latency)
    app.add_route("/metrics", metrics, include_in_schema=False)

    try:
        yield
    finally:
        await app.state.downloader.aclose()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"])

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return FileResponse("app/static/index.html")