# 教育知识库 RAG（微信小程序后端）

初高中教育知识库 RAG 系统，支持 Markdown / DOCX / PDF 文档分块、向量检索、全文检索、混合检索与 RAG 问答。

## 快速开始

### 1. 启动基础设施

```powershell
cd D:\微信小程序RAG
docker compose up -d
```

服务包括 Qdrant、Meilisearch、Redis、Neo4j、PostgreSQL、MinIO、RQ Dashboard。

| 服务 | 地址 |
|------|------|
| Qdrant | http://localhost:6333 |
| Meilisearch | http://localhost:7700 |
| Neo4j Browser | http://localhost:7474（用户 `neo4j` / 密码见 `.env`） |
| PostgreSQL | localhost:5432 |
| MinIO Console | http://localhost:9001 |
| RQ Dashboard | http://localhost:9181 |

### 2. 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```powershell
copy .env.example .env
# 编辑 .env，填写 LLM_API_KEY（可选，用于 RAG 生成）
# 若本机有代理，请保留 NO_PROXY=127.0.0.1,localhost
# Reranker 需额外下载模型，默认 USE_RERANK=false
# 生产环境可设置 AUTH_ENABLED=true 并配置 JWT_SECRET_KEY
# 知识图谱: GRAPH_ENABLED=true + NEO4J_URI/NEO4J_PASSWORD
```

### 4. 索引文档

```powershell
python main.py index --force
```

支持 `vault/` 下的 `.md`、`.docx`、`.pdf`（后两者需安装 [Pandoc](https://pandoc.org/installing.html)）。非 Markdown 文件转换后写入 `vault/_converted/`。

### 5. 启动 API

```powershell
python main.py api
```

访问 Swagger: http://localhost:8000/docs

## 常用命令

| 命令 | 说明 |
|------|------|
| `python scripts/verify_phase2.py` | Phase 2 流水线验收（元数据 + RQ） |
| `python main.py worker` | 启动 RQ Worker 消费任务队列 |
| `python main.py enqueue` | 将待处理 vault 文件入队 |
| `python scripts/rebuild_index.py` | 全量重建索引（同 `index --force`） |
| `python scripts/eval_rag.py` | RAG 评估（同 `main.py eval`） |
| `python main.py index` | 增量索引 vault 中变更文件 |
| `python main.py index --force` | 全量重建索引 |
| `python main.py convert` | 仅运行格式转换（不索引） |
| `python main.py manifest` | 生成 chunk 映射表 |
| `python main.py eval` | 运行黄金评估集（检索 + LLM 生成，约 56 次 API 调用） |
| `python main.py eval --retrieval-only` | 仅检索指标，不消耗 LLM token |
| `python main.py eval --split test` | 只跑 test 集（held-out） |
| `python scripts/benchmark_embed.py` | 测量 BGE-M3 向量化吞吐（目标 >50 chunks/min） |
| `python scripts/compare_retrieval.py` | 对比 vector / keyword / RRF / hybrid 检索效果 |
| `python scripts/load_test.py` | HTTP 压测（默认 health 100 QPS） |
| `python scripts/issue_jwt.py` | 生成 JWT 测试令牌 |
| `python main.py graph` | 重建 Neo4j 知识图谱（需 GRAPH_ENABLED=true） |
| `python scripts/verify_graph.py` | Phase 4 图谱验收查询 |
| `python main.py api` | 启动 FastAPI |

## 黄金评估集

默认使用 `eval/golden_set_v2.jsonl`（56 条，dev=43 / test=13），覆盖 ENG-S / MATH-S 概念题、变体问法、改错计算与负样本。

```powershell
# 1. 索引后生成 manifest（标注 chunk_id 时使用）
python main.py index --force
python main.py manifest

# 2. 快速检索回归（不调用 LLM）
python main.py eval --retrieval-only

# 3. 完整 RAG 评估（需在 .env 配置 LLM_API_KEY）
python main.py eval

# 4. 调试：只跑前 5 条
python main.py eval --limit 5
```

评估结果写入 `eval/results/eval_latest.json`，包含：
- 检索：Recall@k、MRR、负样本通过率
- 生成：`point_coverage`、`forbidden_hit_rate`（基于归一化子串匹配 + `|` 同义表述，对真实 LLM 输出打分）

`must_include_points` 支持用 `|` 分隔同义表述（任一命中即算该要点覆盖）。可用离线重评分跳过重跑 LLM：

```powershell
python scripts/rescore_eval.py
```

辅助脚本：
- `python scripts/scaffold_golden_cases.py` — 从 manifest 生成标注模板
- `python scripts/build_golden_set_v2.py` — 重建 golden_set_v2.jsonl

## API 示例

### 健康检查

```powershell
curl http://localhost:8000/api/v1/health
```

### 混合检索

```powershell
curl -X POST http://localhost:8000/api/v1/knowledge/search `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"虚拟语气与现在事实相反\",\"subject\":\"ENG-S\"}"
```

### RAG 问答（WebSocket）

连接 `ws://localhost:8000/api/v1/rag/ws`（`AUTH_ENABLED=true` 时加 `?token=<jwt>`），连接后发送 JSON：

```json
{"question": "虚拟语气怎么用？", "subject": "ENG-S", "student_level": "高中"}
```

消息类型：`context` → `token`（多次）→ `sources` → `done`

```powershell
python scripts/issue_jwt.py --user dev_user
# 小程序: wx.connectSocket({ url: 'ws://.../api/v1/rag/ws?token=...' })
```

### RAG 问答（同步 JSON，Swagger 调试）

```powershell
curl -X POST http://localhost:8000/api/v1/rag/ask/sync `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"虚拟语气怎么用？\",\"subject\":\"ENG-S\"}"
```

### 鉴权

```powershell
curl -X POST http://localhost:8000/api/v1/auth/token -H "Content-Type: application/json" -d "{\"user_id\":\"dev_user\"}"
python scripts/issue_jwt.py --user dev_user
curl -H "Authorization: Bearer <your_jwt>" http://localhost:8000/api/v1/health
```

### 学习推荐 / 音频 / 测评

```powershell
curl "http://localhost:8000/api/v1/learning/recommend?knowledge_id=MATH-KP-03-01"
curl http://localhost:8000/api/v1/audio/play/aud-001
curl http://localhost:8000/api/v1/audio/transcript/aud-001
curl -X POST http://localhost:8000/api/v1/assessment/submit -H "Content-Type: application/json" -d "{\"answers\":[]}"
```

## 项目结构

与《开发实施指南》附录对齐，并保留 Phase 3–5 扩展（`eval/`、`services/rag/` 等）。

```
微信小程序RAG/
├── docker-compose.yml              # 基础设施（PG/Qdrant/Meili/Neo4j/Redis/MinIO/RQ）
├── .env / .env.example
├── main.py                         # CLI 入口
├── requirements.txt                # 聚合三模块依赖
├── .github/workflows/knowledge-pipeline.yml
├── configs/
│   ├── postgres/init.sql           # 数据库初始化
│   ├── obsidian/app.json           # Obsidian 配置模板
│   ├── settings.py / prompts.py
│   └── pipeline_state.json         # 增量索引状态（gitignore）
├── services/
│   ├── pipeline/                   # 素材处理 + requirements.txt
│   ├── indexer/                    # 分块/向量/检索/图谱 + requirements.txt
│   ├── api/                        # FastAPI + ws/ + requirements.txt
│   └── rag/                        # RAG 答案生成
├── vault/                          # Obsidian Vault（0–9 目录骨架）
│   ├── 3_教辅资料/                 # 当前样例文档
│   ├── 4_题库/                     # 已索引历史目录（勿重命名）
│   ├── 4_题库与试卷/               # 指南标准命名（新题放此）
│   └── _converted/                 # 格式转换输出
├── eval/                           # 黄金评估集 + run_eval.py
├── scripts/                        # init_all / rebuild_index / eval_rag + 验收脚本
├── data/                           # audio_seed.json 等占位数据
└── docs/
    ├── dev_guide.md                # 完整开发实施指南
    └── phase3/4/5_signoff.md       # 阶段验收记录
```

完整指南见 [docs/dev_guide.md](docs/dev_guide.md)。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `AUTH_ENABLED` | `false` | 是否启用 JWT 鉴权 |
| `JWT_SECRET_KEY` | 空 | JWT 签名密钥 |
| `JWT_EXPIRE_HOURS` | `24` | JWT 有效期（小时） |
| `AUDIO_SEED_PATH` | `data/audio_seed.json` | 音频元数据占位文件 |
| `RATE_LIMIT_PER_MINUTE` | `60` | 每 IP 每分钟请求上限 |
| `GRAPH_ENABLED` | `true` | 是否写入 Neo4j 知识图谱 |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Neo4j 连接 |
| `NEO4J_PASSWORD` | `edu_neo4j_2026` | Neo4j 密码 |
| `POSTGRES_*` | 见 `.env.example` | PostgreSQL（Phase 6+ 持久化） |
| `MINIO_*` | 见 `.env.example` | 对象存储（音频/文件） |

## 注意事项

- 首次运行会下载 BGE-M3 模型，体积较大
- 无 GPU 时推理较慢，建议先验证索引流程
- 评估前需运行 `manifest` 并将 `eval/golden_set_v1.jsonl` 中的 `TODO_CHUNK` 替换为真实 chunk_id
- Redis 不可用时限流自动降级，不影响正常请求
- Pandoc 未安装时 DOCX/PDF 转换会返回明确错误
- Meilisearch 索引需 `primaryKey=chunk_id`；若全文检索无结果，请 `python main.py index --force` 重建
- Phase 2 流水线验收见 [docs/phase2_signoff.md](docs/phase2_signoff.md)；GitHub 推送见 [docs/github_setup.md](docs/github_setup.md)
- Phase 3 验收详情见 [docs/phase3_signoff.md](docs/phase3_signoff.md)
- Phase 4 知识图谱：`GRAPH_ENABLED=true` 后运行 `python main.py graph`；验收见 [docs/phase4_signoff.md](docs/phase4_signoff.md)
- Phase 5 API：RAG 使用 WebSocket `/api/v1/rag/ws`；验收见 [docs/phase5_signoff.md](docs/phase5_signoff.md)
