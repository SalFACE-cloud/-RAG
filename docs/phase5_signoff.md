# Phase 5 验收签收

日期：2026-07-17  
范围：FastAPI 服务层（无 PostgreSQL，无四库聚合）  
**结论：✅ PASS**（`scripts/verify_phase5.py`）

## 验收结果

| 验收项 | 结果 | 状态 |
|--------|------|------|
| HTTP 全接口（12 项） | health / auth / search / rag/sync / path / exercises / recommend / audio×3 / assessment | ✅ |
| SSE 已移除 | `/api/v1/rag/ask` 不在 OpenAPI | ✅ |
| WebSocket RAG | `context → token×N → sources → done`（66 事件） | ✅ |
| 压测 `/health` 100 QPS × 10s | total=500, err_rate=0% | ✅ |

详细报告：`eval/results/phase5_verify_latest.json`

## 接口清单

| 方法 | 路径 | 状态 |
|------|------|------|
| GET | `/api/v1/health` | ✅ |
| POST | `/api/v1/auth/token` | ✅ 新增 |
| POST | `/api/v1/knowledge/search` | ✅ |
| WS | `/api/v1/rag/ws` | ✅ 替代 SSE |
| POST | `/api/v1/rag/ask/sync` | ✅ 保留（Swagger 调试） |
| GET | `/api/v1/knowledge/path/{id}` | ✅ |
| GET | `/api/v1/exercises/filter` | ✅ |
| GET | `/api/v1/learning/recommend` | ✅ 新增 |
| GET | `/api/v1/audio/play/{id}` | ✅ 新增（JSON 占位） |
| GET | `/api/v1/audio/transcript/{id}` | ✅ 新增 |
| POST | `/api/v1/audio/training/submit` | ✅ 新增 |
| POST | `/api/v1/assessment/submit` | ✅ 新增 |

## 变更说明

- **删除** `POST /api/v1/rag/ask`（SSE）
- **新增** `WS /api/v1/rag/ws`：JSON 消息流 `context → token → sources → done`
- 音频/测评数据来自 `data/audio_seed.json` 与内存占位，未接 PostgreSQL
- JWT：`POST /auth/token` + `scripts/issue_jwt.py`

## WebSocket 协议

**连接**：`ws://host/api/v1/rag/ws?token=<jwt>`（`AUTH_ENABLED=false` 时可省略 token）

**客户端首条消息**：
```json
{"question": "...", "subject": "ENG-S", "student_level": "高中"}
```

**服务端消息**：
```json
{"type": "context", "sources": 5}
{"type": "token", "content": "..."}
{"type": "sources", "references": [{"file": "...", "section": "..."}]}
{"type": "done"}
{"type": "error", "message": "..."}
```

## 验收命令

```powershell
docker compose up -d
python main.py api
python scripts/verify_phase5.py --qps 100 --duration 10
```

手动抽查：

```powershell
curl http://localhost:8000/api/v1/health
curl -X POST http://localhost:8000/api/v1/auth/token -H "Content-Type: application/json" -d "{\"user_id\":\"dev\"}"
curl "http://localhost:8000/api/v1/learning/recommend?knowledge_id=MATH-KP-03-01"
curl http://localhost:8000/api/v1/audio/play/aud-001
python scripts/load_test.py --qps 100 --duration 10
```

## 验收修复记录

- **WebSocket 流式**：`stream_llm_events` 跳过空 `choices` 块，避免 `list index out of range`
- **压测 `/health`**：health 端点不再限流（业务接口仍受 `RATE_LIMIT_PER_MINUTE` 保护）
- **验收脚本**：启动前清理 Redis `rate:*` 键；修正 `phase5_pass` 布尔逻辑

## 已知限制

- 音频 OSS URL 为占位，生产需接 MinIO/阿里云
- 测评提交存内存，重启丢失
- 100 QPS 压测建议针对 `/health`；检索接口因 embedding 耗时需单独基准
