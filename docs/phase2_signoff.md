# Phase 2 验收签收

日期：2026-07-17  
范围：素材处理流水线（格式转换 → 元数据校验 → 索引入库 + RQ 队列）

**结论：✅ PASS**（本地 `scripts/verify_phase2.py` + 全量索引/图谱/检索评估）

## 本地流水线结果（2026-07-17）

| 步骤 | 结果 |
|------|------|
| `validate_vault.py` | 8 valid / 0 invalid |
| `rebuild_index.py` | 8 文件 indexed |
| `main.py graph` | 8 imported, 14 Knowledge / 2 Exercise |
| `eval_rag.py --retrieval-only` | recall@5=87.5%, MRR=0.748 |
| Redis RQ 队列 | 连接正常 |

## 验收结果

| 验收项 | 结果 | 状态 |
|--------|------|------|
| Vault YAML 校验 | 8 篇有效文档，0 失败 | ✅ |
| 路径迁移 | `4_题库/` → `4_题库与试卷/结构化题库/高中/数学/数列/` | ✅ |
| 增量跟踪 | `file_tracker.py` + `pipeline_state.json` | ✅ |
| RQ 队列 | Redis `pipeline` 队列可连接 | ✅ |
| GitHub Actions | `.github/workflows/knowledge-pipeline.yml` | ✅ 已配置 |

## 命令

```powershell
# 一键串联 Phase 1 + Phase 2
python main.py pipeline
python scripts/run_pipeline.py

# 分步
docker compose up -d qdrant meilisearch redis neo4j
python scripts/verify_phase1.py
python scripts/validate_vault.py
python scripts/run_pipeline.py --phase2-only --force --skip-docker

# RQ 队列模式
python main.py enqueue
python main.py worker
python scripts/verify_phase2.py
```

## CI

Push 到 GitHub `main` 后自动运行 **Phase 1 → Phase 2** 串联流水线：

1. **Phase 1**：Docker 启动 Qdrant/Meili/Redis/Neo4j → `verify_phase1.py`
2. **Phase 2**：元数据校验 →（有 vault 变更或手动触发时）`run_pipeline.py --ci`

手动全量跑：`Actions → Knowledge Pipeline → Run workflow`

本地等价命令：

```powershell
python main.py pipeline
python scripts/run_pipeline.py --phase2-only --force --skip-docker
```

报告：`eval/results/pipeline_latest.json`、`eval/results/phase2_verify_latest.json`
