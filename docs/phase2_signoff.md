# Phase 2 验收签收

日期：2026-07-17  
范围：素材处理流水线（格式转换 → 元数据校验 → 索引入库 + RQ 队列）

**结论：✅ PASS**（本地 `verify_phase2.py` / `verify_pipeline_b.py` + 全量索引/图谱）

## 双流水线

| | Pipeline A（本地） | Pipeline B（CI / 分步） |
|---|---|---|
| 编排 | `run_pipeline.py` / `IndexerService` | 5 个独立 CLI |
| 校验 | `metadata_validator.validate_vault()` | `metadata_validator.py --vault-path` |
| 向量 | 真实 BGE-M3 | `--mock-embeddings` |
| 日志 | `eval/results/pipeline_latest.json` | `vault/9_数据流水线/logs/` |

## 验收结果

| 验收项 | 结果 | 状态 |
|--------|------|------|
| Vault YAML 校验 | 11 篇有效（含教材库） | ✅ |
| 路径标准 | `4_题库与试卷/` 结构化目录 | ✅ |
| 增量跟踪 | `file_tracker.py` + `pipeline_state.json` | ✅ |
| RQ 队列 | Redis `pipeline` 队列可连接 | ✅ |
| GitHub Actions | `Edu Knowledge RAG Pipeline` | ✅ 已配置 |

## 命令

```powershell
# Pipeline A — 本地一体化
python main.py pipeline
python scripts/run_pipeline.py --phase2-only --force --skip-docker

# Pipeline B — 分步（与 CI 一致）
python services/pipeline/metadata_validator.py --vault-path ./vault --ignore-path "0_项目文档/**"
python services/pipeline/file_tracker.py --scan-mode full --vault-path ./vault
python services/indexer/chunker.py --vault-path ./vault --chunk-size 512 --chunk-overlap 64
python services/indexer/embedder.py --vault-path ./vault
python services/indexer/meili_indexer.py
python scripts/verify_pipeline_b.py

# RQ 队列模式（Pipeline A）
python main.py enqueue
python main.py worker
python scripts/verify_phase2.py
```

## CI

Push 到 `main` 且变更 `vault/2_教材库/**` 等业务路径时触发 **Pipeline B**：

1. Docker 启动 Qdrant / Postgres / Redis / Meilisearch
2. 元数据校验 → git_diff 跟踪 → 分块 → mock 向量 → Meili 同步
3. 上传 `vault/9_数据流水线/logs/` 为 artifact

**CI 不包含**：Neo4j 图谱、检索评估、真实 BGE-M3 下载。

手动触发：`Actions → Edu Knowledge RAG Pipeline → Run workflow`

报告：`vault/9_数据流水线/logs/pipeline_result.json`、`eval/results/phase2_verify_latest.json`
