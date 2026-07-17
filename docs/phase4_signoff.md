# Phase 4 验收签收

日期：2026-07-16  
范围：Neo4j 知识图谱 K-C-E 模型

## 验收结果

| 验收项 | 结果 | 状态 |
|--------|------|------|
| YAML 导入 Knowledge / Competency / Exercise | 14 Knowledge, 2 Competency, 2 Exercise | ✅ |
| K-C-E 关系 | BELONGS_TO, PREREQUISITE, RELATED_TO, TESTS, ASSESSES | ✅ |
| Obsidian `[[链接]]` | 2 条 LINKS_TO + RELATED_TO | ✅ |
| Neo4j Browser 可视化 | http://localhost:7474 | ✅ |
| 前置学习路径 | MATH-KP-03-01 → [MATH-KP-02-01] | ✅ |
| 关联题目查询 | MATH-KP-03-01 → MATH-EX-03-001 | ✅ |

## 图谱统计

```
Knowledge:   14
Competency:  2  (MATH-C-02, ENG-C-03)
Exercise:    2  (MATH-EX-03-001, MATH-EX-03-002)
Relations:   38
Documents:   8
```

## 启用方式

```powershell
docker compose up -d neo4j
# .env: GRAPH_ENABLED=true
python main.py graph          # 仅重建图谱
python main.py index --force  # 索引时同步写入图谱
python scripts/verify_graph.py
```

## 验收 Cypher（Neo4j Browser）

```cypher
// 知识网络概览
MATCH (k:Knowledge)-[r]->(n) RETURN k, r, n LIMIT 50;

// 前置学习路径
MATCH path = (pre:Knowledge)-[:PREREQUISITE*1..5]->(k:Knowledge {id: 'MATH-KP-03-01'})
RETURN path;

// 知识点关联题目
MATCH (e:Exercise)-[:TESTS]->(k:Knowledge {id: 'MATH-KP-03-01'})
RETURN e;

// Obsidian 文档链接
MATCH (d1:Document)-[:LINKS_TO]->(d2:Document) RETURN d1.title, d2.title;
```

## API 验收

```powershell
curl http://localhost:8000/api/v1/knowledge/path/MATH-KP-03-01
curl "http://localhost:8000/api/v1/exercises/filter?knowledge_id=MATH-KP-03-01&difficulty_min=0&difficulty_max=1"
```

## 新增/变更文件

| 文件 | 说明 |
|------|------|
| `services/indexer/graph_builder.py` | 完整 K-C-E 导入与 Cypher 查询 |
| `services/pipeline/metadata_validator.py` | 图谱 YAML 字段校验 |
| `scripts/rebuild_graph.py` | 独立图谱重建 |
| `scripts/verify_graph.py` | 自动化验收 |
| `vault/4_题库与试卷/.../等比数列练习.md` | Exercise 样例 |
| `vault/.../等比数列.md` 等 | competencies / prerequisites / Obsidian 链接 |

## YAML 扩展字段示例

```yaml
competencies:
  - code: MATH-C-02
    name: 数学运算
knowledge_points:
  - id: MATH-KP-03-01
    name: 等比数列通项公式
    prerequisites: [MATH-KP-02-01]
    related: [MATH-KP-02-01]
exercises:
  - id: MATH-EX-03-001
    content: "..."
    difficulty: 0.4
    tests: [MATH-KP-03-01]
    assesses: [MATH-C-02]
```

## Phase 4 结论

**K-C-E 知识图谱已落地，可进入 Phase 5（API 服务层扩展）。**

验收报告：`eval/results/graph_verify_latest.json`
