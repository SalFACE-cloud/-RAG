# GitHub 仓库推送指南

项目已在本地初始化 Git（`main` 分支），`.env` 不会提交。

## 方式 A：GitHub 网页 + HTTPS

1. 在 GitHub 新建空仓库，例如 `edu-knowledge-base`（不要勾选 README）
2. 在项目目录执行：

```powershell
cd D:\微信小程序RAG
git remote add origin https://github.com/<你的用户名>/edu-knowledge-base.git
git push -u origin main
```

3. 打开仓库 **Actions** 页，手动运行 **Edu Knowledge RAG Pipeline**（workflow_dispatch）或 push `vault/` 变更触发

## 方式 B：GitHub CLI

```powershell
winget install GitHub.cli
gh auth login
gh repo create edu-knowledge-base --private --source=. --remote=origin --push
```

## CI 说明

`.github/workflows/knowledge-pipeline.yml`（**Edu Knowledge RAG Pipeline**）在 push 以下路径时触发：

- `vault/1_政策与课标/**`、`2_教材库/**`、`3_教辅资料/**`、`4_题库与试卷/**` 等
- `services/pipeline/**`、`services/indexer/**`、workflow 自身

CI 步骤（Pipeline B，约 3–8 分钟）：

1. 元数据校验（`metadata_validator.py`）
2. Git diff 增量跟踪（`file_tracker.py`）
3. 分块 + **mock 向量**写入 Qdrant + Meili 同步
4. 上传 `vault/9_数据流水线/logs/` 日志

**CI 不下载 BGE-M3**，不跑图谱与检索评估。本地真实索引请用 `python main.py pipeline`。

## 本地验收

```powershell
# Pipeline A
docker compose up -d redis qdrant meilisearch neo4j
python scripts/verify_phase2.py

# Pipeline B（与 CI 一致，mock 向量）
python scripts/verify_pipeline_b.py
```
