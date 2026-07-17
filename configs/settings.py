import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# 避免本机 Docker 服务被系统代理拦截（502 Bad Gateway）
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

VAULT_DIR = os.getenv("VAULT_DIR", str(BASE_DIR / "vault"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
MEILI_URL = os.getenv("MEILI_URL", "http://127.0.0.1:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "edu_meili_dev_2026")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
USE_FP16 = os.getenv("USE_FP16", "true").lower() == "true"
USE_RERANK = os.getenv("USE_RERANK", "false").lower() == "true"

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "edu_knowledge")
MEILI_INDEX = os.getenv("MEILI_INDEX", COLLECTION_NAME)
VECTOR_SIZE = 1024

CHUNK_MIN_CHARS = int(os.getenv("CHUNK_MIN_CHARS", "200"))
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_SIZE", os.getenv("CHUNK_MAX_CHARS", "800")))
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP", os.getenv("CHUNK_OVERLAP_CHARS", "80")))

LLM_API_BASE = os.getenv("LLM_API_BASE", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
DEV_TOKEN_ENABLED = os.getenv("DEV_TOKEN_ENABLED", "false").lower() == "true"
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
AUDIO_SEED_PATH = os.getenv("AUDIO_SEED_PATH", str(BASE_DIR / "data" / "audio_seed.json"))

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "edu_neo4j_2026")
GRAPH_ENABLED = os.getenv("GRAPH_ENABLED", "false").lower() == "true"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "edu_kb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "edu_admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "edu_dev_2026")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://127.0.0.1:9000")
MINIO_USER = os.getenv("MINIO_USER", "edu_minio")
MINIO_PASSWORD = os.getenv("MINIO_PASSWORD", "edu_minio_2026")

PIPELINE_USE_RQ = os.getenv("PIPELINE_USE_RQ", "false").lower() == "true"
RQ_JOB_TIMEOUT = int(os.getenv("RQ_JOB_TIMEOUT", "600"))
RQ_MAX_RETRIES = int(os.getenv("RQ_MAX_RETRIES", "3"))

CONVERTED_DIR = os.getenv("CONVERTED_DIR", str(Path(VAULT_DIR) / "_converted"))
