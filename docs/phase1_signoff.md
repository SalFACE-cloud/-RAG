# Phase 1 验收签收

日期：2026-07-17  
范围：Docker 基础设施（Qdrant / Meilisearch / Redis / Neo4j）

## 与 Phase 2 串联

```
Phase 1                    Phase 2
────────                   ────────
docker compose up    →     转换 → 校验 → 索引
健康检查 (verify_phase1) →  图谱 → 检索评估 (verify_phase2)
```

统一入口：

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

`.github/workflows/knowledge-pipeline.yml` 在 CI 中先跑 Phase 1，再跑 Phase 2。
