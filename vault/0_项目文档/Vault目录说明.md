# Obsidian Vault 目录说明

本目录为教研人员工作区，与《开发实施指南》附录目录结构对齐。

## 目录用途

| 目录 | 用途 |
|------|------|
| `0_项目文档/` | 项目说明、规范、模板 |
| `1_政策与课标/` | 新课标、考试说明等政策类文档 |
| `2_教材库/` | 各版本教材 Markdown（**当前样例：集合 CH01**） |
| `3_教辅资料/` | 讲义、知识点梳理 |
| `4_题库与试卷/` | 结构化题库与试卷（**标准目录**，含高中/初中） |
| `5_多媒体资源/` | 音频、视频、图片、动画源文件 |
| `6_知识图谱/` | 素养词典、映射表、Dataview 索引 |
| `7_元数据与索引/` | 全局索引、标签规范 |
| `8_外购数据管理/` | 第三方采购资料 |
| `9_数据流水线/` | 流水线说明与待处理队列 |
| `_converted/` | PDF/DOCX 等自动转换后的 Markdown（勿手改） |

## Obsidian 插件建议

- Dataview — 动态索引
- Obsidian Git — 自动同步（5 分钟间隔）
- Excalidraw — 思维导图
- Tag Wrangler — 标签管理

配置模板见 `configs/obsidian/app.json`，首次可在 Obsidian 中打开本 vault 后按需调整。

## 索引命令

**Pipeline A（一体化）：**

```powershell
python main.py index          # 增量
python main.py index --force  # 全量重建
python scripts/rebuild_index.py
python main.py pipeline       # Docker + 索引 + 图谱 + 验收
```

**Pipeline B（分步，与 CI 一致）：**

```powershell
python services/pipeline/metadata_validator.py --vault-path ./vault --ignore-path "0_项目文档/**"
python services/pipeline/file_tracker.py --scan-mode full --vault-path ./vault
python services/indexer/chunker.py --vault-path ./vault
python services/indexer/embedder.py --vault-path ./vault
python services/indexer/meili_indexer.py
```

运行日志写入 `vault/9_数据流水线/logs/`。
