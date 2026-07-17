# Phase 1 验收签收

日期：2026-07-17  
范围：Docker 基础设施（Qdrant / Meilisearch / Redis / Neo4j）

## 与 Phase 2 串联

**本地（Pipeline A）：**

```
Phase 1                    Phase 2
────────                   ────────
docker compose up    →     转换 → 校验 → 索引
verify_phase1.py     →     图谱 → 检索评估 (verify_phase2)
```

**GitHub Actions（Pipeline B）：**

```
docker compose up (qdrant/postgres/redis/meilisearch)
  → curl 健康等待
  → metadata_validator → file_tracker → chunker → embedder(mock) → meili
```

统一本地入口：

```powershell
python main.py pipeline
python scripts/run_pipeline.py
```

## 验收命令

```powershell
docker compose up -d qdrant meilisearch redis neo4j
python scripts/verify_phase1.py
```

## 服务地址

| 服务 | 地址 |
|------|------|
| Qdrant | http://localhost:6333 |
| Meilisearch | http://localhost:7700 |
| Redis | localhost:6379 |
| Neo4j Browser | http://localhost:7474 |
| MinIO（可选） | http://localhost:9001 |
| RQ Dashboard（可选） | http://localhost:9181 |

## GitHub Actions

Workflow 名称：**Edu Knowledge RAG Pipeline**（`.github/workflows/knowledge-pipeline.yml`）。

CI 启动 Docker 并等待 HTTP 就绪，**不运行** `verify_phase1.py`；本地验收请手动执行上述命令。
