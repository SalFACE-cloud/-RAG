import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.routes import api_router
from services.indexer.hybrid_retriever import HybridRetriever

app = FastAPI(title="教育知识库 RAG API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = HybridRetriever()
app.include_router(api_router)
