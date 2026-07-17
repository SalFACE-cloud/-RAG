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

3. 打开仓库 **Actions** 页，手动运行 **Knowledge Pipeline**（workflow_dispatch）或再 push 一次触发

## 方式 B：GitHub CLI

```powershell
winget install GitHub.cli
gh auth login
gh repo create edu-knowledge-base --private --source=. --remote=origin --push
```

## CI 说明

`.github/workflows/knowledge-pipeline.yml` 会在 push `vault/**` 时：

- 校验 YAML 元数据（快速）
- 启动 Docker 服务并全量索引 + 图谱 + 检索评估（约 15–30 分钟，含 BGE-M3 下载）

首次 CI 较慢属正常。可在 Actions 页查看各 job 日志。

## 本地 Phase 2 验收

```powershell
docker compose up -d redis qdrant meilisearch neo4j
python scripts/verify_phase2.py
python main.py enqueue
python main.py worker --burst
```
