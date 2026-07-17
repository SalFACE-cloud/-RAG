# 教育知识库与 RAG 向量数据库 — 从零到一开发实施指南

> **基于方案文档分析，输出可落地的分阶段开发步骤**
> **日期**：2026-07-14
> **适用项目**：初高中全科教育产品知识库 + RAG 系统

---

## 目录

- [第一部分：方案分析与关键决策](#第一部分方案分析与关键决策)
- [第二部分：技术栈选型与依据](#第二部分技术栈选型与依据)
- [第三部分：分阶段开发实施步骤](#第三部分分阶段开发实施步骤)
  - [Phase 1: 基础设施搭建](#phase-1-基础设施搭建)
  - [Phase 2: 素材处理流水线](#phase-2-素材处理流水线)
  - [Phase 3: RAG 向量检索核心](#phase-3-rag-向量检索核心)
  - [Phase 4: 知识图谱构建](#phase-4-知识图谱构建)
  - [Phase 5: API 服务层](#phase-5-api-服务层)
  - [Phase 6: 小程序集成与部署](#phase-6-小程序集成与部署)
- [第四部分：关键技术难点与解决方案](#第四部分关键技术难点与解决方案)
- [第五部分：风险清单与应对策略](#第五部分风险清单与应对策略)
- [附录：项目目录结构](#附录项目目录结构)

---

## 第一部分：方案分析与关键决策

### 1.1 方案优势分析

你的 v3.0 方案在架构设计上已经相当成熟，核心优势：

| 维度 | 评价 | 说明 |
|:---|:---|:---|
| **教研友好性** | 优秀 | Obsidian 所见即所得，教研人员只需"放文件→填标签→保存" |
| **LLM Wiki 规范** | 前瞻 | 原子化内容 + 元数据前置 + 分块友好结构，天然适配 RAG |
| **多模态处理** | 完整 | PDF/DOCX/PPT/音频/视频/图片全覆盖，Pipeline 设计合理 |
| **四库协同** | 专业 | Meilisearch(全文) + Qdrant(向量) + Neo4j(图谱) + PostgreSQL(结构化) 各司其职 |
| **双轨制设计** | 科学 | 轨道A(文档库) + 轨道B(结构化题库) 分离管理，兼顾灵活与精确 |

### 1.2 需要补充的关键决策

方案文档在"做什么"层面已经很清晰，但"怎么做"层面有以下需要补齐的：

| 缺口 | 影响 | 本指南补充 |
|:---|:---|:---|
| **文档分块策略缺失** | RAG 检索质量取决于分块粒度 | Phase 3 详细设计分块算法 |
| **Embedding 模型未选型** | 中英混合教育内容的向量质量 | Phase 3 给出模型对比与推荐 |
| **Reranking 方案缺失** | 召回多但排序不准，影响最终回答质量 | Phase 3 设计 Cross-Encoder 重排 |
| **增量更新机制不清** | 全量重建索引不可持续 | Phase 2 设计文件指纹 + 增量索引 |
| **错误处理与重试缺失** | Pipeline 某环节失败导致数据不一致 | Phase 2 设计任务队列 + 死信重试 |
| **成本估算缺失** | Whisper large + Embedding API 费用不可忽视 | 各阶段标注成本 |
| **测试评估方案缺失** | RAG 效果无法量化 | Phase 3 设计评估指标 |

### 1.3 核心技术决策摘要

```
语言/框架:     Python 3.11+ / FastAPI
向量数据库:    Qdrant (自建, Docker)
全文检索:      Meilisearch (自建, Docker)
图数据库:      Neo4j Community (自建, Docker)
结构化存储:    PostgreSQL 16 (自建, Docker)
消息队列:      Redis + RQ (轻量任务队列)
对象存储:      MinIO (自建) 或 阿里云 OSS
容器编排:      Docker Compose (开发) → K8s (生产)
Embedding:     BGE-M3 (中英双语, 本地部署)
Reranker:      BGE-Reranker-v2-m3 (本地部署)
LLM:           DeepSeek-V3 / Qwen2.5-72B (API 调用)
音频转写:      Whisper large-v3 (本地 GPU 部署)
OCR:           PaddleOCR (本地部署)
格式转换:      Pandoc + 自定义后处理
CI/CD:         GitHub Actions / Gitea Actions
```

---

## 第二部分：技术栈选型与依据

### 2.1 为什么选 Qdrant 而非 Milvus/Pinecone

| 对比项 | Qdrant | Milvus | Pinecone |
|:---|:---|:---|:---|
| 部署复杂度 | 低 (单容器) | 高 (多组件) | SaaS 无需部署 |
| 本地开发 | 原生支持 | 依赖 etcd/MinIO | 不支持 |
| Payload 过滤 | 强 (结构化过滤) | 支持 | 支持 |
| 中文社区 | 活跃 | 活跃 | 一般 |
| 成本 | 开源自建 | 开源自建 | 按量付费 |
| 适合阶段 | MVP → 生产 | 大规模生产 | 快速验证 |

**结论**：Qdrant 在开发期和生产初期最友好，单容器部署、内置 Payload 过滤（可按学科/难度/学段过滤向量检索结果），完美匹配教育知识库的元数据过滤需求。

### 2.2 为什么选 BGE-M3 做 Embedding

| 模型 | 维度 | 多语言 | 中文效果 | 本地部署 | 成本 |
|:---|:---|:---|:---|:---|:---|
| **BGE-M3** | 1024 | 100+语言 | 优秀 | 可以 | 免费 |
| text-embedding-3-large | 3072 | 优秀 | 良好 | 不行 | $0.13/M tokens |
| m3e-base | 768 | 中英 | 良好 | 可以 | 免费 |
| bge-large-zh-v1.5 | 1024 | 仅中文 | 优秀 | 可以 | 免费 |

**结论**：BGE-M3 支持中英双语（教育内容常含英文术语）、支持稠密+稀疏+多向量混合检索、本地部署零成本，是教育知识库的最优选择。

### 2.3 为什么用 RQ 而非 Celery

| 对比项 | RQ (Redis Queue) | Celery |
|:---|:---|:---|
| 学习曲线 | 低 | 高 |
| 依赖 | 仅 Redis | Redis/RabbitMQ + 额外组件 |
| 任务监控 | Flower/RQ Dashboard | Flower |
| 适合规模 | 中小型 | 大型分布式 |
| 代码侵入 | 低 | 中 |

**结论**：教育知识库的 Pipeline 任务量中等（日均数百文件），RQ 足够且更易维护。

---

## 第三部分：分阶段开发实施步骤

### Phase 1: 基础设施搭建（1-2 周）

#### 1.1 目标

- Docker Compose 一键启动所有基础设施
- Obsidian Vault 目录骨架就绪
- Git 仓库 + Webhook 基础 CI/CD

#### 1.2 步骤

**Step 1: 创建项目骨架**

```bash
mkdir edu-knowledge-base && cd edu-knowledge-base
git init

# 创建目录结构
mkdir -p docker services scripts configs docs
mkdir -p services/pipeline services/api services/indexer
```

**Step 2: 编写 docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"

services:
  # 结构化存储
  postgres:
    image: postgres:16-alpine
    container_name: edu_postgres
    environment:
      POSTGRES_DB: edu_kb
      POSTGRES_USER: edu_admin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-edu_dev_2026}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./configs/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U edu_admin"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 向量数据库
  qdrant:
    image: qdrant/qdrant:latest
    container_name: edu_qdrant
    ports:
      - "6333:6333"  # REST API
      - "6334:6334"  # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 全文检索
  meilisearch:
    image: getmeili/meilisearch:v1.9
    container_name: edu_meili
    environment:
      MEILI_MASTER_KEY: ${MEILI_MASTER_KEY:-edu_meili_dev_2026}
      MEILI_ENV: development
    ports:
      - "7700:7700"
    volumes:
      - meili_data:/meili_data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7700/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 知识图谱
  neo4j:
    image: neo4j:5.20-community
    container_name: edu_neo4j
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-edu_neo4j_2026}
      NEO4J_PLUGINS: '["apoc"]'
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  # 消息队列
  redis:
    image: redis:7-alpine
    container_name: edu_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  # 对象存储 (开发环境用 MinIO)
  minio:
    image: minio/minio:latest
    container_name: edu_minio
    environment:
      MINIO_ROOT_USER: ${MINIO_USER:-edu_minio}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD:-edu_minio_2026}
    ports:
      - "9000:9000"  # API
      - "9001:9001"  # Console
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

  # RQ Dashboard (任务监控)
  rq-dashboard:
    image: cjting/rq-dashboard:latest
    container_name: edu_rq_dashboard
    ports:
      - "9181:9181"
    environment:
      RQ_DASHBOARD_REDIS_URL: redis://redis:6379
    depends_on:
      - redis

volumes:
  postgres_data:
  qdrant_data:
  meili_data:
  neo4j_data:
  neo4j_logs:
  redis_data:
  minio_data:
```

**Step 3: 启动并验证**

```bash
docker compose up -d

# 验证各服务
curl http://localhost:6333/healthz        # Qdrant
curl http://localhost:7700/health          # Meilisearch
curl http://localhost:7474                 # Neo4j Browser
curl http://localhost:9001                 # MinIO Console
```

**Step 4: 创建 Obsidian Vault 目录骨架**

```bash
# 这是教研人员的工作目录，也是 Git 仓库
mkdir -p vault/{0_项目文档,1_政策与课标,2_教材库,3_教辅资料}
mkdir -p vault/4_题库与试卷/{结构化题库,高中,初中}
mkdir -p vault/5_多媒体资源/{音频,视频,图片,动画}
mkdir -p vault/6_知识图谱/{学科素养词典,素养-知识点映射表,Dataview_动态索引,双轨关联}
mkdir -p vault/7_元数据与索引
mkdir -p vault/8_外购数据管理
mkdir -p vault/9_数据流水线
```

**Step 5: 配置 Obsidian 插件**

在 `vault/.obsidian/` 下配置：
- Dataview（动态索引）
- Obsidian Git（自动同步，5分钟间隔）
- Excalidraw（思维导图）
- Tag Wrangler（标签管理）

**Step 6: GitHub Actions 基础 CI/CD**

```yaml
# .github/workflows/knowledge-pipeline.yml
name: Knowledge Pipeline
on:
  push:
    paths:
      - "vault/2_教材库/**"
      - "vault/3_教辅资料/**"
      - "vault/4_题库与试卷/**"
      - "vault/5_多媒体资源/**"

jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      changed_files: ${{ steps.changed.outputs.all }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2
      - id: changed
        run: |
          FILES=$(git diff --name-only HEAD^ HEAD -- 'vault/' | jq -R . | jq -s .)
          echo "all=$FILES" >> $GITHUB_OUTPUT

  process:
    needs: detect-changes
    if: ${{ needs.detect-changes.outputs.changed_files != '[]' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r services/pipeline/requirements.txt
      - name: Run pipeline
        env:
          CHANGED_FILES: ${{ needs.detect-changes.outputs.changed_files }}
          QDRANT_URL: ${{ secrets.QDRANT_URL }}
          MEILI_URL: ${{ secrets.MEILI_URL }}
          NEO4J_URI: ${{ secrets.NEO4J_URI }}
        run: python services/pipeline/main.py
```

#### 1.3 Phase 1 验收标准

- [ ] `docker compose up -d` 一键启动所有服务，健康检查全部通过
- [ ] Obsidian 可打开 vault 目录，插件正常工作
- [ ] Git Push 后 GitHub Actions 能检测到文件变更
- [ ] RQ Dashboard 可访问，任务队列就绪

---

### Phase 2: 素材处理流水线（2-3 周）

#### 2.1 目标

- 多格式素材自动转换为标准 .md
- YAML 元数据校验
- 增量处理（只处理变更文件）
- 任务队列 + 错误重试

#### 2.2 架构设计

```
Git Push → Webhook → 任务入队(RQ) → 分发器 → 格式转换器 → 元数据校验器 → 索引入库器
                              ↓ 失败
                          死信队列(重试3次)
```

#### 2.3 步骤

**Step 1: 定义文件指纹与增量机制**

```python
# services/pipeline/file_tracker.py
import hashlib
import json
from pathlib import Path
from datetime import datetime

class FileTracker:
    """基于文件内容哈希的增量处理跟踪器"""

    def __init__(self, state_file: str = "configs/pipeline_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {}

    def _save_state(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get_hash(self, file_path: str) -> str:
        """计算文件内容 SHA256"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def is_changed(self, file_path: str) -> bool:
        """判断文件是否变更（新增或修改）"""
        abs_path = str(Path(file_path).resolve())
        current_hash = self.get_hash(file_path)
        stored_hash = self.state.get(abs_path, {}).get("hash")
        return current_hash != stored_hash

    def mark_processed(self, file_path: str, status: str = "success"):
        """标记文件已处理"""
        abs_path = str(Path(file_path).resolve())
        self.state[abs_path] = {
            "hash": self.get_hash(file_path),
            "status": status,
            "processed_at": datetime.now().isoformat()
        }
        self._save_state()

    def get_pending_files(self, directory: str) -> list[str]:
        """获取目录下所有待处理文件"""
        dir_path = Path(directory)
        pending = []
        for f in dir_path.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                if self.is_changed(str(f)):
                    pending.append(str(f))
        return pending
```

**Step 2: 格式转换器**

```python
# services/pipeline/converters.py
import subprocess
import shutil
from pathlib import Path
from typing import Optional

class FormatConverter:
    """多格式素材统一转换为 Markdown"""

    # 格式 → 转换策略映射
    STRATEGIES = {
        ".pdf": "pandoc_pdf",
        ".docx": "pandoc_doc",
        ".doc": "pandoc_doc",
        ".pptx": "pandoc_ppt",
        ".mp3": "whisper",
        ".wav": "whisper",
        ".m4a": "whisper",
        ".mp4": "ffmpeg_whisper",
        ".mov": "ffmpeg_whisper",
        ".png": "paddle_ocr",
        ".jpg": "paddle_ocr",
        ".jpeg": "paddle_ocr",
        ".webp": "paddle_ocr",
        ".md": "direct",
    }

    def convert(self, file_path: str, output_dir: str) -> dict:
        """转换文件，返回结果信息"""
        ext = Path(file_path).suffix.lower()
        strategy = self.STRATEGIES.get(ext)

        if strategy is None:
            return {"success": False, "error": f"不支持的格式: {ext}"}

        handler = getattr(self, f"_convert_{strategy}", None)
        if handler is None:
            return {"success": False, "error": f"无转换处理器: {strategy}"}

        return handler(file_path, output_dir)

    def _convert_pandoc_pdf(self, file_path: str, output_dir: str) -> dict:
        """PDF → MD (Pandoc)"""
        output_file = Path(output_dir) / (Path(file_path).stem + ".md")
        try:
            # Pandoc 转换，保留元数据
            cmd = [
                "pandoc", file_path,
                "-f", "pdf",
                "-t", "gfm",  # GitHub Flavored Markdown
                "-o", str(output_file),
                "--wrap=none",
                "--extract-media", str(Path(output_dir) / "media"),
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return {
                "success": True,
                "output": str(output_file),
                "converter": "pandoc"
            }
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr}

    def _convert_pandoc_doc(self, file_path: str, output_dir: str) -> dict:
        """DOCX/DOC → MD"""
        output_file = Path(output_dir) / (Path(file_path).stem + ".md")
        try:
            cmd = [
                "pandoc", file_path,
                "-f", "docx",
                "-t", "gfm",
                "-o", str(output_file),
                "--wrap=none",
                "--extract-media", str(Path(output_dir) / "media"),
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return {"success": True, "output": str(output_file), "converter": "pandoc"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": e.stderr}

    def _convert_whisper(self, file_path: str, output_dir: str) -> dict:
        """音频 → 文字稿 MD + SRT 字幕"""
        try:
            import whisper
            model = whisper.load_model("large-v3")
            result = model.transcribe(
                file_path,
                language="en",  # 英语听力；中文音频改为 "zh"
                word_timestamps=True
            )

            # 生成文字稿 MD
            md_file = Path(output_dir) / (Path(file_path).stem + "_文字稿.md")
            md_content = "# 听力原文\n\n"
            for seg in result["segments"]:
                start = self._format_time(seg["start"])
                end = self._format_time(seg["end"])
                md_content += f"> {start} - {end}\n\n{seg['text']}\n\n---\n\n"
            md_file.write_text(md_content, encoding="utf-8")

            # 生成 SRT 字幕
            srt_file = Path(output_dir) / (Path(file_path).stem + ".srt")
            with open(srt_file, "w", encoding="utf-8") as f:
                for i, seg in enumerate(result["segments"], 1):
                    f.write(f"{i}\n")
                    f.write(f"{self._format_srt_time(seg['start'])} --> "
                            f"{self._format_srt_time(seg['end'])}\n")
                    f.write(f"{seg['text']}\n\n")

            return {
                "success": True,
                "output": str(md_file),
                "srt": str(srt_file),
                "segments": result["segments"],
                "converter": "whisper"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _convert_paddle_ocr(self, file_path: str, output_dir: str) -> dict:
        """图片 → OCR 文字 MD"""
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang="ch")
            result = ocr.ocr(file_path, cls=True)

            md_file = Path(output_dir) / (Path(file_path).stem + "_OCR.md")
            md_content = f"# {Path(file_path).stem} OCR 结果\n\n"
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                md_content += f"- {text} (置信度: {confidence:.2f})\n"

            md_file.write_text(md_content, encoding="utf-8")
            return {"success": True, "output": str(md_file), "converter": "paddle_ocr"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _convert_direct(self, file_path: str, output_dir: str) -> dict:
        """MD 文件直接通过（仅做校验）"""
        return {"success": True, "output": file_path, "converter": "direct"}

    @staticmethod
    def _format_time(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}"

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
```

**Step 3: 元数据校验器**

```python
# services/pipeline/metadata_validator.py
import yaml
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    metadata: Optional[dict]
    content: str

class MetadataValidator:
    """YAML Front Matter 元数据校验器"""

    # 必填字段
    REQUIRED_FIELDS = ["subject", "type"]

    # 学科代码白名单
    VALID_SUBJECTS = {
        "ENG-S", "MATH-S", "PHY-S", "CHE-S", "BIO-S",
        "CHN-S", "HIS-S", "GEO-S", "POL-S",
        "ENG-J", "MATH-J", "PHY-J", "CHE-J", "BIO-J",
        "CHN-J", "HIS-J", "GEO-J", "POL-J",
    }

    # 文档类型白名单
    VALID_TYPES = {
        "textbook", "jiangyi", "exercise", "exam",
        "audio_exercise", "video", "diagram",
        "policy", "standard", "summary"
    }

    def validate(self, file_path: str) -> ValidationResult:
        """校验 .md 文件的 YAML Front Matter"""
        content = Path(file_path).read_text(encoding="utf-8")
        errors = []

        # 提取 YAML Front Matter
        yaml_match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
        if not yaml_match:
            return ValidationResult(
                valid=False,
                errors=["缺少 YAML Front Matter (--- 包围的元数据块)"],
                metadata=None,
                content=content
            )

        yaml_str = yaml_match.group(1)
        body = yaml_match.group(2)

        try:
            metadata = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            return ValidationResult(
                valid=False,
                errors=[f"YAML 解析错误: {e}"],
                metadata=None,
                content=content
            )

        if not isinstance(metadata, dict):
            errors.append("YAML 元数据必须是键值对结构")

        # 校验必填字段
        for field in self.REQUIRED_FIELDS:
            if field not in metadata:
                errors.append(f"缺少必填字段: {field}")

        # 校验学科代码
        if "subject" in metadata:
            if metadata["subject"] not in self.VALID_SUBJECTS:
                errors.append(
                    f"无效学科代码: {metadata['subject']}, "
                    f"有效值: {', '.join(sorted(self.VALID_SUBJECTS))}"
                )

        # 校验文档类型
        if "type" in metadata:
            if metadata["type"] not in self.VALID_TYPES:
                errors.append(
                    f"无效文档类型: {metadata['type']}, "
                    f"有效值: {', '.join(sorted(self.VALID_TYPES))}"
                )

        # 校验知识点编号格式 (如 ENG-KP-03-01)
        if "knowledge_points" in metadata and metadata["knowledge_points"]:
            for kp in metadata["knowledge_points"]:
                kp_id = kp.get("id", "") if isinstance(kp, dict) else kp
                if not re.match(r"^[A-Z]{3}-KP-\d{2}-\d{2}$", str(kp_id)):
                    errors.append(f"知识点编号格式错误: {kp_id} (应为 XXX-KP-XX-XX)")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            metadata=metadata,
            content=body
        )
```

**Step 4: 任务队列 Pipeline 主流程**

```python
# services/pipeline/main.py
import os
import json
import logging
from pathlib import Path
from rq import Queue, Worker
from redis import Redis
from file_tracker import FileTracker
from converters import FormatConverter
from metadata_validator import MetadataValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Redis 连接
redis_conn = Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379)
queue = Queue("pipeline", connection=redis_conn)

# 初始化组件
tracker = FileTracker()
converter = FormatConverter()
validator = MetadataValidator()


def process_file(file_path: str):
    """处理单个文件：格式转换 → 元数据校验 → 标记完成"""
    logger.info(f"开始处理: {file_path}")

    # 1. 格式转换
    output_dir = Path(file_path).parent / "_converted"
    output_dir.mkdir(exist_ok=True)
    result = converter.convert(file_path, str(output_dir))

    if not result["success"]:
        logger.error(f"格式转换失败: {file_path} - {result['error']}")
        tracker.mark_processed(file_path, status="convert_failed")
        return {"success": False, "stage": "convert", "error": result["error"]}

    md_file = result["output"]

    # 2. 元数据校验
    validation = validator.validate(md_file)
    if not validation.valid:
        logger.warning(f"元数据校验失败: {md_file} - {validation.errors}")
        # 校验失败仍入库，但标记为 needs_review
        tracker.mark_processed(file_path, status="metadata_warning")
        return {
            "success": True,
            "stage": "metadata_warning",
            "warnings": validation.errors,
            "md_file": md_file,
            "metadata": validation.metadata,
            "content": validation.content
        }

    # 3. 标记成功
    tracker.mark_processed(file_path, status="success")
    logger.info(f"处理完成: {file_path} → {md_file}")

    return {
        "success": True,
        "stage": "ready_for_index",
        "md_file": md_file,
        "metadata": validation.metadata,
        "content": validation.content
    }


def enqueue_changed_files(vault_dir: str = "vault"):
    """扫描 Vault，将变更文件加入处理队列"""
    pending = tracker.get_pending_files(vault_dir)
    logger.info(f"发现 {len(pending)} 个待处理文件")

    for file_path in pending:
        queue.enqueue(process_file, file_path, timeout=600)  # 10分钟超时


if __name__ == "__main__":
    changed_files = json.loads(os.getenv("CHANGED_FILES", "[]"))
    if changed_files:
        # CI/CD 模式：处理指定的变更文件
        for f in changed_files:
            queue.enqueue(process_file, f, timeout=600)
    else:
        # 本地模式：全量扫描
        enqueue_changed_files()

    # 启动 Worker (开发模式)
    worker = Worker([queue], connection=redis_conn)
    worker.work()
```

#### 2.4 Phase 2 验收标准

- [ ] 放入 PDF/DOCX 到 vault 对应目录，Push 后自动转换为 .md
- [ ] 放入 MP3，Whisper 自动转写生成文字稿 + SRT 字幕
- [ ] 放入图片，PaddleOCR 自动提取文字
- [ ] YAML 元数据缺失或格式错误时，给出明确的错误提示
- [ ] 修改已有文件后，只重新处理变更文件（增量）
- [ ] RQ Dashboard 可查看任务执行状态

---

### Phase 3: RAG 向量检索核心（2-3 周）

这是整个系统技术含量最高的部分。

#### 3.1 目标

- 文档智能分块
- Embedding 向量化 + Qdrant 入库
- 混合检索（向量 + 全文）
- Reranking 精排
- RAG 评估指标

#### 3.2 文档分块策略

分块质量直接决定 RAG 检索质量。教育内容有其特殊性——需要按知识结构分块，而非简单按字数切割。

```python
# services/indexer/chunker.py
import re
from dataclasses import dataclass
from typing import Optional
import hashlib

@dataclass
class Chunk:
    chunk_id: str
    content: str
    metadata: dict
    source_file: str
    section_title: str
    token_count: int  # 预估 token 数

class EduDocumentChunker:
    """
    教育文档专用分块器
    策略：按 Markdown 标题层次分块，保持知识完整性
    """

    def __init__(self, min_chunk_size: int = 200, max_chunk_size: int = 800):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk(self, content: str, source_file: str, metadata: dict) -> list[Chunk]:
        """主分块入口"""
        # Step 1: 按标题切分为 Section
        sections = self._split_by_headers(content)

        chunks = []
        for section in sections:
            title = section["title"]
            text = section["content"]
            level = section["level"]

            # Step 2: 判断 Section 大小
            if len(text) <= self.max_chunk_size:
                # Section 不超过上限，直接作为一个 chunk
                if len(text) >= self.min_chunk_size:
                    chunks.append(self._make_chunk(
                        text, source_file, metadata, title
                    ))
                else:
                    # 太小，标记为短块（仍保留，可能与其他合并）
                    chunks.append(self._make_chunk(
                        text, source_file, metadata, title
                    ))
            else:
                # Step 3: Section 过大，按段落二次切分
                sub_chunks = self._split_large_section(
                    text, source_file, metadata, title
                )
                chunks.extend(sub_chunks)

        # Step 4: 合并过短的 chunk（相邻同 section 的）
        chunks = self._merge_short_chunks(chunks)

        return chunks

    def _split_by_headers(self, content: str) -> list[dict]:
        """按 Markdown 标题切分为 Section"""
        lines = content.split("\n")
        sections = []
        current_title = ""
        current_level = 0
        current_content = []

        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if header_match:
                # 保存前一个 section
                if current_content:
                    sections.append({
                        "title": current_title,
                        "level": current_level,
                        "content": "\n".join(current_content).strip()
                    })
                current_level = len(header_match.group(1))
                current_title = header_match.group(2)
                current_content = []
            else:
                current_content.append(line)

        # 保存最后一个 section
        if current_content:
            sections.append({
                "title": current_title,
                "level": current_level,
                "content": "\n".join(current_content).strip()
            })

        return sections

    def _split_large_section(
        self, text: str, source_file: str,
        metadata: dict, section_title: str
    ) -> list[Chunk]:
        """对过大的 section 按段落二次切分"""
        paragraphs = re.split(r"\n\n+", text)
        chunks = []
        buffer = ""

        for para in paragraphs:
            if len(buffer) + len(para) <= self.max_chunk_size:
                buffer += para + "\n\n"
            else:
                if buffer:
                    chunks.append(self._make_chunk(
                        buffer.strip(), source_file, metadata, section_title
                    ))
                buffer = para + "\n\n"

        if buffer:
            chunks.append(self._make_chunk(
                buffer.strip(), source_file, metadata, section_title
            ))

        return chunks

    def _merge_short_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """合并过短的相邻 chunk"""
        if len(chunks) <= 1:
            return chunks

        merged = []
        i = 0
        while i < len(chunks):
            current = chunks[i]
            # 如果当前 chunk 太短且还有下一个
            while (current.token_count < self.min_chunk_size
                   and i + 1 < len(chunks)
                   and chunks[i + 1].section_title == current.section_title):
                i += 1
                next_chunk = chunks[i]
                current = Chunk(
                    chunk_id=current.chunk_id,  # 保留 ID
                    content=current.content + "\n\n" + next_chunk.content,
                    metadata=current.metadata,
                    source_file=current.source_file,
                    section_title=current.section_title,
                    token_count=current.token_count + next_chunk.token_count
                )
            merged.append(current)
            i += 1

        return merged

    def _make_chunk(
        self, content: str, source_file: str,
        metadata: dict, section_title: str
    ) -> Chunk:
        """创建一个 Chunk 对象"""
        chunk_id = hashlib.md5(
            f"{source_file}:{section_title}:{content[:50]}".encode()
        ).hexdigest()[:16]

        # 预估 token 数 (中英混合: ~1.5 字符/token)
        token_count = int(len(content) / 1.5)

        return Chunk(
            chunk_id=chunk_id,
            content=content,
            metadata={**metadata, "section": section_title},
            source_file=source_file,
            section_title=section_title,
            token_count=token_count
        )
```

#### 3.3 Embedding + Qdrant 入库

```python
# services/indexer/embedder.py
import os
import logging
from typing import Optional
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)

logger = logging.getLogger(__name__)

class QdrantIndexer:
    """Qdrant 向量索引管理器"""

    COLLECTION_NAME = "edu_knowledge"
    VECTOR_SIZE = 1024  # BGE-M3 输出维度

    def __init__(self):
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333")
        )
        self._embedder = None  # 延迟加载

    @property
    def embedder(self):
        """延迟加载 BGE-M3 模型"""
        if self._embedder is None:
            from FlagEmbedding import BGEM3FlagModel
            self._embedder = BGEM3FlagModel(
                "BAAI/bge-m3",
                use_fp16=True  # 半精度加速
            )
        return self._embedder

    def init_collection(self):
        """初始化 Qdrant Collection"""
        collections = self.client.get_collections().collections
        existing = [c.name for c in collections]

        if self.COLLECTION_NAME not in existing:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"创建 Qdrant Collection: {self.COLLECTION_NAME}")

            # 创建 Payload 索引（加速过滤）
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="metadata.subject",
                field_schema="keyword"
            )
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="metadata.type",
                field_schema="keyword"
            )
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="metadata.difficulty",
                field_schema="float"
            )

    def embed_text(self, text: str) -> np.ndarray:
        """使用 BGE-M3 生成向量"""
        embeddings = self.embedder.encode(
            [text],
            batch_size=1,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False
        )
        return embeddings["dense_vecs"][0]

    def upsert_chunks(self, chunks: list) -> int:
        """将 Chunk 列表向量化并入库"""
        points = []
        texts = [c.content for c in chunks]

        # 批量向量化
        embeddings = self.embedder.encode(
            texts,
            batch_size=min(32, len(texts)),
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False
        )

        for chunk, vector in zip(chunks, embeddings["dense_vecs"]):
            point = PointStruct(
                id=chunk.chunk_id,
                vector=vector.tolist(),
                payload={
                    "content": chunk.content,
                    "source_file": chunk.source_file,
                    "section_title": chunk.section_title,
                    "metadata": chunk.metadata,
                    "token_count": chunk.token_count
                }
            )
            points.append(point)

        # 批量 upsert
        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=points
        )
        logger.info(f"向 Qdrant 入库 {len(points)} 个 chunk")
        return len(points)

    def search(
        self,
        query: str,
        subject: Optional[str] = None,
        doc_type: Optional[str] = None,
        difficulty_max: Optional[float] = None,
        top_k: int = 20
    ) -> list[dict]:
        """向量检索"""

        # 构建 Payload 过滤条件
        conditions = []
        if subject:
            conditions.append(
                FieldCondition(key="metadata.subject", match=MatchValue(value=subject))
            )
        if doc_type:
            conditions.append(
                FieldCondition(key="metadata.type", match=MatchValue(value=doc_type))
            )
        if difficulty_max:
            conditions.append(
                FieldCondition(
                    key="metadata.difficulty",
                    range={"lte": difficulty_max}
                )
            )

        query_filter = Filter(must=conditions) if conditions else None

        # 生成查询向量
        query_vector = self.embed_text(query)

        # 检索
        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_vector.tolist(),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        )

        return [
            {
                "chunk_id": r.id,
                "score": r.score,
                "content": r.payload["content"],
                "source_file": r.payload["source_file"],
                "section_title": r.payload["section_title"],
                "metadata": r.payload["metadata"]
            }
            for r in results
        ]
```

#### 3.4 混合检索 + Reranking

```python
# services/indexer/hybrid_retriever.py
import os
import logging
from typing import Optional
import requests
from qdrant_indexer import QdrantIndexer

logger = logging.getLogger(__name__)

class HybridRetriever:
    """混合检索：向量 + 全文 + 图谱增强 + 重排序"""

    def __init__(self):
        self.qdrant = QdrantIndexer()
        self.meili_url = os.getenv("MEILI_URL", "http://localhost:7700")
        self.meili_key = os.getenv("MEILI_MASTER_KEY", "")
        self._reranker = None

    @property
    def reranker(self):
        """延迟加载 BGE-Reranker"""
        if self._reranker is None:
            from FlagEmbedding import FlagReranker
            self._reranker = FlagReranker(
                "BAAI/bge-reranker-v2-m3",
                use_fp16=True
            )
        return self._reranker

    def search_meilisearch(
        self, query: str, subject: Optional[str] = None,
        limit: int = 20
    ) -> list[dict]:
        """Meilisearch 全文检索"""
        headers = {"Authorization": f"Bearer {self.meili_key}"}
        filter_str = ""
        if subject:
            filter_str = f'subject = "{subject}"'

        resp = requests.post(
            f"{self.meili_url}/indexes/edu_knowledge/search",
            headers=headers,
            json={
                "q": query,
                "limit": limit,
                "filter": filter_str if filter_str else None
            }
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        return [
            {
                "chunk_id": h.get("chunk_id"),
                "score": 1.0 - h.get("_rankingScore", 0.5),  # BM25 相关性
                "content": h.get("content"),
                "source_file": h.get("source_file"),
                "section_title": h.get("section_title"),
                "metadata": h.get("metadata", {})
            }
            for h in hits
        ]

    def reciprocal_rank_fusion(
        self, vector_results: list[dict],
        keyword_results: list[dict],
        k: int = 60
    ) -> list[dict]:
        """RRF 融合两路检索结果"""
        rrf_scores = {}

        for rank, result in enumerate(vector_results):
            chunk_id = result["chunk_id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1.0 / (k + rank + 1)
            if chunk_id not in rrf_scores or "content" not in rrf_scores.get(chunk_id, {}):
                rrf_scores[chunk_id] = {
                    "rrf_score": rrf_scores.get(chunk_id, 0),
                    **result
                }

        for rank, result in enumerate(keyword_results):
            chunk_id = result["chunk_id"]
            score = 1.0 / (k + rank + 1)
            if chunk_id in rrf_scores and isinstance(rrf_scores[chunk_id], dict):
                rrf_scores[chunk_id]["rrf_score"] += score
            else:
                rrf_scores[chunk_id] = {
                    "rrf_score": score,
                    **result
                }

        # 按 RRF 分数排序
        merged = [v for v in rrf_scores.values() if isinstance(v, dict)]
        merged.sort(key=lambda x: x["rrf_score"], reverse=True)
        return merged

    def rerank(
        self, query: str, candidates: list[dict], top_n: int = 5
    ) -> list[dict]:
        """Cross-Encoder 重排序"""
        if not candidates:
            return []

        pairs = [[query, c["content"]] for c in candidates]
        scores = self.reranker.compute_score(pairs, normalize=True)

        if isinstance(scores, float):
            scores = [scores]

        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_n]

    def hybrid_search(
        self, query: str,
        subject: Optional[str] = None,
        doc_type: Optional[str] = None,
        difficulty_max: Optional[float] = None,
        top_k: int = 20,
        top_n: int = 5
    ) -> list[dict]:
        """完整混合检索流程"""

        # 1. 向量检索
        vector_results = self.qdrant.search(
            query, subject=subject, doc_type=doc_type,
            difficulty_max=difficulty_max, top_k=top_k
        )

        # 2. 全文检索
        keyword_results = self.search_meilisearch(
            query, subject=subject, limit=top_k
        )

        # 3. RRF 融合
        merged = self.reciprocal_rank_fusion(vector_results, keyword_results)

        # 4. Reranking 精排
        reranked = self.rerank(query, merged, top_n=top_n)

        return reranked
```

#### 3.5 RAG 评估指标

```python
# services/indexer/evaluator.py
"""
RAG 系统评估框架
评估三个层面：
1. 检索质量 (Retrieval Metrics)
2. 生成质量 (Generation Metrics)
3. 端到端效果 (End-to-End)
"""

class RAGEvaluator:
    """RAG 系统评估器"""

    def evaluate_retrieval(
        self, retrieved_ids: list[str],
        relevant_ids: list[str]
    ) -> dict:
        """评估检索质量"""
        # Recall@K
        k_values = [1, 3, 5, 10]
        results = {}
        for k in k_values:
            top_k = retrieved_ids[:k]
            hits = len(set(top_k) & set(relevant_ids))
            results[f"recall@{k}"] = hits / len(relevant_ids) if relevant_ids else 0

        # MRR (Mean Reciprocal Rank)
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                results["mrr"] = 1.0 / (i + 1)
                break
        else:
            results["mrr"] = 0

        return results

    def evaluate_generation(
        self, answer: str, ground_truth: str,
        retrieved_context: str
    ) -> dict:
        """评估生成质量（使用 LLM 辅助评估）"""
        # 实际实现中调用 LLM 评估以下维度：
        # 1. Faithfulness (忠实度): 回答是否基于检索到的上下文
        # 2. Answer Relevance (答案相关性): 回答是否切题
        # 3. Context Precision (上下文精度): 检索到的上下文是否相关
        # 4. Context Recall (上下文召回): 是否检索到了回答问题所需的信息

        # 简化版：基于文本重叠的初步评估
        answer_words = set(answer.split())
        truth_words = set(ground_truth.split())
        overlap = len(answer_words & truth_words)
        results = {
            "word_overlap": overlap / len(truth_words) if truth_words else 0,
            "answer_length": len(answer),
            "has_citation": "[" in answer and "]" in answer
        }
        return results
```

#### 3.6 Phase 3 验收标准

- [ ] 一篇 .md 文档能正确分块（按标题层次，200-800字/chunk）
- [ ] BGE-M3 本地推理正常，向量化速度 > 50 chunks/分钟
- [ ] Qdrant 入库后，向量检索能命中相关内容
- [ ] Meilisearch 全文检索正常工作
- [ ] RRF 融合后，检索结果优于单路检索
- [ ] Reranking 精排后，Top-5 准确率 > 80%
- [ ] 评估脚本可运行，输出 Recall@K / MRR 指标

---

### Phase 4: 知识图谱构建（2 周）

#### 4.1 目标

- K-C-E 三层数据模型在 Neo4j 中落地
- 从 YAML 元数据自动导入节点和边
- Obsidian 双向链接同步到图谱
- Cypher 查询接口

#### 4.2 K-C-E 数据模型

```
K = Knowledge (知识点)
C = Competency (核心素养)
E = Exercise/Exam (题目/试卷)

关系类型:
  (:Knowledge)-[:BELONGS_TO]->(:Competency)    知识点归属素养
  (:Knowledge)-[:PREREQUISITE]->(:Knowledge)   前置知识
  (:Knowledge)-[:RELATED_TO]->(:Knowledge)     关联知识
  (:Exercise)-[:TESTS]->(:Knowledge)           题目考察知识点
  (:Exercise)-[:ASSESSES]->(:Competency)       题目评估素养
```

#### 4.3 步骤

**Step 1: Neo4j 数据导入器**

```python
# services/indexer/graph_builder.py
import os
import logging
from neo4j import GraphDatabase
from metadata_validator import MetadataValidator

logger = logging.getLogger(__name__)

class KnowledgeGraphBuilder:
    """从 YAML 元数据构建 Neo4j 知识图谱"""

    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=("neo4j", os.getenv("NEO4J_PASSWORD", "edu_neo4j_2026"))
        )

    def close(self):
        self.driver.close()

    def init_constraints(self):
        """创建唯一约束"""
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS "
                "FOR (k:Knowledge) REQUIRE k.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS "
                "FOR (c:Competency) REQUIRE c.code IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS "
                "FOR (e:Exercise) REQUIRE e.id IS UNIQUE"
            )

    def import_from_metadata(self, file_path: str, metadata: dict):
        """从文档元数据导入图谱节点和关系"""
        with self.driver.session() as session:
            # 1. 导入知识点节点
            if "knowledge_points" in metadata:
                for kp in metadata["knowledge_points"]:
                    kp_id = kp.get("id") if isinstance(kp, dict) else kp
                    kp_name = kp.get("name", "") if isinstance(kp, dict) else ""
                    session.run(
                        "MERGE (k:Knowledge {id: $id}) "
                        "SET k.name = $name",
                        id=kp_id, name=kp_name
                    )

                    # 关联到文档
                    session.run(
                        "MATCH (k:Knowledge {id: $kid}) "
                        "MERGE (d:Document {path: $path}) "
                        "MERGE (d)-[:COVERS]->(k)",
                        kid=kp_id, path=file_path
                    )

            # 2. 导入素养节点 + K→C 关系
            if "competencies" in metadata:
                for comp in metadata["competencies"]:
                    code = comp.get("code", "")
                    name = comp.get("name", "")
                    session.run(
                        "MERGE (c:Competency {code: $code}) "
                        "SET c.name = $name",
                        code=code, name=name
                    )

                    # 知识点 → 素养
                    if "knowledge_points" in metadata:
                        for kp in metadata["knowledge_points"]:
                            kp_id = kp.get("id") if isinstance(kp, dict) else kp
                            session.run(
                                "MATCH (k:Knowledge {id: $kid}), "
                                "(c:Competency {code: $code}) "
                                "MERGE (k)-[:BELONGS_TO]->(c)",
                                kid=kp_id, code=code
                            )

    def import_obsidian_links(self, file_path: str, content: str):
        """从 Obsidian [[双向链接]] 导入知识点关联"""
        import re
        links = re.findall(r"\[\[([^\]]+)\]\]", content)

        if not links:
            return

        source_name = os.path.splitext(os.path.basename(file_path))[0]

        with self.driver.session() as session:
            # 创建文档节点
            session.run(
                "MERGE (d:Document {name: $name, path: $path})",
                name=source_name, path=file_path
            )

            for link in links:
                # 清理链接文本
                link_clean = link.split("|")[0].split("#")[0].strip()

                # 创建关联文档节点
                session.run(
                    "MERGE (d2:Document {name: $name})",
                    name=link_clean
                )

                # 创建双向关联
                session.run(
                    "MATCH (d1:Document {name: $src}), "
                    "(d2:Document {name: $tgt}) "
                    "MERGE (d1)-[:REFERENCES]->(d2)",
                    src=source_name, tgt=link_clean
                )

    def get_learning_path(self, knowledge_id: str) -> list[dict]:
        """查询某个知识点的前置学习路径"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = (k:Knowledge {id: $kid})<-[:PREREQUISITE*1..5]-(prereq)
                RETURN [node in nodes(path) | {
                    id: node.id,
                    name: node.name,
                    labels: labels(node)
                }] as learning_path
                ORDER BY length(path)
                """,
                kid=knowledge_id
            )
            return [r["learning_path"] for r in result]

    def get_exercises_for_knowledge(
        self, knowledge_id: str, difficulty_range: tuple = (0, 1)
    ) -> list[dict]:
        """查询考察某知识点的题目"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Exercise)-[:TESTS]->(k:Knowledge {id: $kid})
                WHERE e.difficulty >= $min_d AND e.difficulty <= $max_d
                RETURN e.id as id, e.content as content,
                       e.difficulty as difficulty, e.type as type
                ORDER BY e.difficulty
                """,
                kid=knowledge_id,
                min_d=difficulty_range[0],
                max_d=difficulty_range[1]
            )
            return [dict(r) for r in result]
```

#### 4.4 Phase 4 验收标准

- [ ] YAML 元数据中的知识点/素养/题目自动导入 Neo4j
- [ ] Obsidian 中的 `[[双向链接]]` 同步为图谱边
- [ ] Neo4j Browser 可可视化查看知识网络
- [ ] Cypher 查询：给定知识点，返回前置学习路径
- [ ] Cypher 查询：给定知识点，返回关联题目

---

### Phase 5: API 服务层（2 周）

#### 5.1 目标

- FastAPI 统一接口，聚合四库检索能力
- RAG 问答 Pipeline
- 流媒体音频分发
- 鉴权与限流

#### 5.2 步骤

**Step 1: FastAPI 应用骨架**

```python
# services/api/app.py
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import os
import json
import time

from hybrid_retriever import HybridRetriever
from graph_builder import KnowledgeGraphBuilder

app = FastAPI(title="教育知识库 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为小程序域名
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = HybridRetriever()
graph = KnowledgeGraphBuilder()


# ========== 数据模型 ==========

class SearchRequest(BaseModel):
    query: str
    subject: Optional[str] = None
    doc_type: Optional[str] = None
    difficulty_max: Optional[float] = None
    top_k: int = 20
    top_n: int = 5

class RAGRequest(BaseModel):
    question: str
    subject: Optional[str] = None
    student_level: Optional[str] = None  # 初中/高中
    conversation_history: Optional[list[dict]] = None


# ========== 接口 ==========

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/api/v1/knowledge/search")
async def knowledge_search(req: SearchRequest):
    """混合检索接口"""
    results = retriever.hybrid_search(
        query=req.query,
        subject=req.subject,
        doc_type=req.doc_type,
        difficulty_max=req.difficulty_max,
        top_k=req.top_k,
        top_n=req.top_n
    )
    return {
        "query": req.query,
        "total": len(results),
        "results": results
    }


@app.post("/api/v1/rag/ask")
async def rag_ask(req: RAGRequest):
    """RAG 问答接口"""
    # 1. 检索
    context_results = retriever.hybrid_search(
        query=req.question,
        subject=req.subject,
        top_k=20,
        top_n=5
    )

    # 2. 组装上下文
    context_text = "\n\n---\n\n".join([
        f"[来源: {r['source_file']} > {r['section_title']}]\n{r['content']}"
        for r in context_results
    ])

    # 3. 构建提示词
    system_prompt = """你是一个专业的初高中教育辅导老师。请基于以下检索到的知识库内容回答学生的问题。

要求：
1. 只使用提供的上下文信息回答，不要编造
2. 如果上下文中没有相关信息，请明确告知
3. 回答要清晰、准确，适合学生理解
4. 在回答末尾标注引用的知识来源
5. 如果适合，推荐相关练习题"""

    user_prompt = f"""参考知识：
{context_text}

学生问题：{req.question}
学生年级：{req.student_level or '未指定'}

请回答："""

    # 4. 调用 LLM (流式)
    async def generate():
        # 实际实现中调用 DeepSeek / Qwen API
        # 这里展示流式输出结构
        yield f"data: {json.dumps({'type': 'context', 'sources': len(context_results)})}\n\n"

        # 模拟流式回答
        answer = "根据知识库内容，虚拟语气在条件句中的用法如下..."
        for char in answer:
            yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"

        # 返回引用来源
        yield f"data: {json.dumps({
            'type': 'sources',
            'references': [{'file': r['source_file'], 'section': r['section_title']}
                          for r in context_results]
        })}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/v1/knowledge/path/{knowledge_id}")
async def get_learning_path(knowledge_id: str):
    """获取知识点学习路径"""
    path = graph.get_learning_path(knowledge_id)
    return {"knowledge_id": knowledge_id, "path": path}


@app.get("/api/v1/audio/play/{audio_id}")
async def get_audio(audio_id: str):
    """获取音频播放信息（OSS 直链 + 字幕）"""
    # 从 PostgreSQL 查询音频元数据
    # 返回 OSS 直链 + 分段字幕 + 关联题目
    return {
        "audio_url": f"https://oss.example.com/audio/{audio_id}.mp3",
        "transcript_url": f"/api/v1/audio/transcript/{audio_id}",
        "segments": [],
        "questions": []
    }


@app.post("/api/v1/assessment/submit")
async def submit_assessment(request: Request):
    """提交作答"""
    data = await request.json()
    # 存入 PostgreSQL
    # 触发 AI 评分
    return {"status": "received", "assessment_id": "temp_id"}
```

**Step 2: 鉴权中间件**

```python
# services/api/auth.py
from fastapi import Request, HTTPException
from functools import wraps
import jwt
import time

SECRET_KEY = "your-secret-key"  # 生产环境从环境变量读取

def verify_token(request: Request):
    """验证 JWT Token"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    token = auth_header[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="令牌已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效令牌")


def rate_limit(max_requests: int = 60, window: int = 60):
    """简单限流装饰器（Redis 实现）"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # 从 Redis 获取请求计数
            # 超限返回 429
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

#### 5.3 API 接口清单

| 方法 | 路径 | 功能 |
|:---|:---|:---|
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/knowledge/search` | 混合检索 |
| POST | `/api/v1/rag/ask` | RAG 问答（流式） |
| GET | `/api/v1/knowledge/path/{id}` | 知识点学习路径 |
| GET | `/api/v1/audio/play/{id}` | 音频播放信息 |
| GET | `/api/v1/audio/transcript/{id}` | 音频文字稿 |
| POST | `/api/v1/audio/training/submit` | 听力训练提交 |
| POST | `/api/v1/assessment/submit` | 测评提交 |
| GET | `/api/v1/learning/recommend` | 学习推荐 |
| GET | `/api/v1/exercises/filter` | 题目筛选 |

#### 5.4 Phase 5 验收标准

- [ ] FastAPI 服务启动，Swagger 文档可访问
- [ ] `/knowledge/search` 返回混合检索结果
- [ ] `/rag/ask` 流式返回 RAG 回答
- [ ] `/knowledge/path/{id}` 返回学习路径
- [ ] JWT 鉴权正常工作
- [ ] 并发压测 100 QPS 无错误

---

### Phase 6: 小程序集成与部署（2 周）

#### 6.1 小程序端核心集成

```javascript
// 小程序端 RAG 问答调用
Page({
  data: {
    question: '',
    answer: '',
    sources: [],
    isStreaming: false
  },

  async askQuestion() {
    const wx = this;
    wx.setData({ isStreaming: true, answer: '' });

    // 使用 WebSocket 接收流式回答
    const socket = wx.connectSocket({
      url: 'wss://api.example.com/api/v1/rag/ask',
      header: { 'Authorization': `Bearer ${wx.token}` }
    });

    socket.onMessage((msg) => {
      const data = JSON.parse(msg.data);
      if (data.type === 'token') {
        wx.setData({ answer: wx.data.answer + data.content });
      } else if (data.type === 'sources') {
        wx.setData({ sources: data.references });
      } else if (data.type === 'done') {
        wx.setData({ isStreaming: false });
      }
    });

    socket.onOpen(() => {
      socket.send({
        data: JSON.stringify({
          question: wx.data.question,
          subject: 'ENG-S'
        })
      });
    });
  }
});
```

#### 6.2 部署架构

```
                    ┌─────────────────┐
                    │   Nginx 反向代理  │
                    │   (SSL + 负载均衡) │
                    └───────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
        │ FastAPI   │ │ FastAPI │ │ Pipeline  │
        │ 实例 1    │ │ 实例 2  │ │ Worker    │
        └─────┬─────┘ └────┬────┘ └─────┬─────┘
              │             │             │
        ┌─────┴─────────────┴─────────────┘
        │           共享数据层
        │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
        │  │Postgr│ │Qdrant│ │ Meili│ │ Neo4j│
        │  └──────┘ └──────┘ └──────┘ └──────┘
        │  ┌──────┐ ┌──────┐
        │  │ Redis│ │ MinIO│
        │  └──────┘ └──────┘
```

#### 6.3 Phase 6 验收标准

- [ ] 小程序可调用所有 API 接口
- [ ] RAG 问答流式输出正常
- [ ] 听力训练音频播放 + 字幕同步
- [ ] Nginx SSL 配置完成，HTTPS 正常
- [ ] 日志收集与告警就绪

---

## 第四部分：关键技术难点与解决方案

### 4.1 PDF 排版还原（最大难点）

**问题**：Pandoc 对 PDF 的转换效果不稳定，尤其是数学公式、表格、图文混排的教材。

**解决方案**：

```
方案 A (推荐): PDF → 图片 → PaddleOCR + 公式识别
  适合：扫描版教材、复杂排版教材
  工具链: PyMuPDF (PDF转图片) → PaddleOCR (文字) → LaTeX-OCR (公式)

方案 B: PDF → Markdown (marker/ml 工具)
  适合：数字版 PDF (非扫描)
  工具链: marker (基于 NLP 的 PDF 转 MD 工具，支持公式)

方案 C: 人工标注 + 模板
  适合：高频使用的核心教材
  流程: 机器初转 → 教研人员校对 → 入库
```

### 4.2 Whisper 本地部署的 GPU 需求

**问题**：Whisper large-v3 需要 GPU 才能达到实用速度。

**解决方案**：

| 方案 | 显存需求 | 速度 | 质量 | 成本 |
|:---|:---|:---|:---|:---|
| Whisper large-v3 (FP16) | 10GB+ | 慢 | 最佳 | GPU 服务器 |
| Whisper large-v3 (INT8) | 6GB | 中 | 优秀 | 中等 |
| Whisper medium | 5GB | 快 | 良好 | 低 |
| faster-whisper | 3GB | 很快 | 优秀 | 低 |
| **faster-whisper large-v3** | **4GB** | **快** | **优秀** | **推荐** |

**推荐**：使用 `faster-whisper` 库，基于 CTranslate2 加速，4GB 显存即可运行 large-v3，速度提升 4 倍。

### 4.3 教育内容的 RAG 特殊处理

**问题**：教育内容有大量公式、图表、代码片段，标准 Embedding 效果差。

**解决方案**：

```python
# 教育内容预处理：公式/图表保留

def preprocess_for_embedding(content: str) -> str:
    """Embedding 前的特殊预处理"""

    # 1. 保留 LaTeX 公式，但标记类型
    content = re.sub(
        r'\$\$(.+?)\$\$',
        r'[数学公式] \1 [/数学公式]',
        content, flags=re.DOTALL
    )

    # 2. 保留行内公式
    content = re.sub(r'\$(.+?)\$', r'[公式] \1 [/公式]', content)

    # 3. 表格保留为结构化文本
    # 4. 代码块标记语言类型
    content = re.sub(
        r'```(\w+)',
        lambda m: f'[代码:{m.group(1)}]',
        content
    )

    # 5. 添加章节上下文（解决chunk丢失标题上下文问题）
    # 在每个 chunk 前添加面包屑路径
    # 如: "英语 > 语法 > 虚拟语气 > 与现在事实相反"

    return content
```

### 4.4 增量索引一致性

**问题**：文件修改后，旧 chunk 残留在 Qdrant 中。

**解决方案**：

```python
# 删除策略：文件更新时，先删除该文件的所有旧 chunk，再插入新 chunk

def reindex_file(file_path: str, new_chunks: list):
    """重新索引文件：先删旧 → 再插新"""
    # 1. 删除该文件的所有旧 chunk
    client.delete(
        collection_name="edu_knowledge",
        points_selector=Filter(
            must=[FieldCondition(
                key="source_file",
                match=MatchValue(value=file_path)
            )]
        )
    )
    # 2. 插入新 chunk
    indexer.upsert_chunks(new_chunks)
```

---

## 第五部分：风险清单与应对策略

| # | 风险 | 概率 | 影响 | 应对策略 |
|:---|:---|:---|:---|:---|
| 1 | PDF 转换质量差，教研需大量手动校对 | 高 | 中 | 优先处理 .md 原始文件，PDF 使用 marker 工具 + 人工校对模板 |
| 2 | Whisper GPU 资源不足 | 中 | 高 | 使用 faster-whisper，或先使用 API 转写、后期迁回本地 |
| 3 | BGE-M3 显存不足 | 中 | 中 | 使用 ONNX 量化版，或回退到 m3e-base (768维) |
| 4 | RAG 回答出现幻觉 | 高 | 高 | Prompt 强约束 + 引用来源 + 后置校验（检查回答是否在上下文中） |
| 5 | 知识图谱与文档不同步 | 中 | 中 | CI/CD 流水线中增加图谱同步步骤，定期全量校验 |
| 6 | 小程序并发承载能力 | 中 | 高 | FastAPI 多实例 + Nginx 负载均衡 + Redis 缓存热点查询 |
| 7 | 教研人员 YAML 填写不规范 | 高 | 中 | 开发 Obsidian 模板插件，提供 YAML 字段自动补全和校验 |
| 8 | 数据安全与合规 | 中 | 高 | 学生数据脱敏存储、日志不记录敏感信息、OSS 访问签名 |

---

## 附录：项目目录结构

```
edu-knowledge-base/
├── docker-compose.yml              # 基础设施编排
├── .env                            # 环境变量
├── .github/
│   └── workflows/
│       └── knowledge-pipeline.yml  # CI/CD 流水线
├── configs/
│   ├── postgres/
│   │   └── init.sql                # 数据库初始化
│   ├── pipeline_state.json         # 文件处理状态
│   └── obsidian/
│       └── app.json                # Obsidian 配置
├── services/
│   ├── pipeline/                   # 素材处理流水线
│   │   ├── main.py
│   │   ├── file_tracker.py         # 增量跟踪
│   │   ├── converters.py           # 格式转换
│   │   ├── metadata_validator.py   # 元数据校验
│   │   └── requirements.txt
│   ├── indexer/                    # 索引构建
│   │   ├── chunker.py              # 文档分块
│   │   ├── embedder.py             # BGE-M3 向量化
│   │   ├── qdrant_indexer.py       # Qdrant 管理
│   │   ├── meili_indexer.py        # Meilisearch 管理
│   │   ├── graph_builder.py        # Neo4j 图谱
│   │   ├── hybrid_retriever.py     # 混合检索
│   │   ├── evaluator.py            # RAG 评估
│   │   └── requirements.txt
│   └── api/                        # API 服务
│       ├── app.py                  # FastAPI 主应用
│       ├── auth.py                 # 鉴权中间件
│       ├── routes/                 # 路由模块
│       └── requirements.txt
├── vault/                          # Obsidian Vault (教研工作区)
│   ├── .obsidian/
│   ├── 0_项目文档/
│   ├── 1_政策与课标/
│   ├── 2_教材库/
│   ├── 3_教辅资料/
│   ├── 4_题库与试卷/
│   ├── 5_多媒体资源/
│   ├── 6_知识图谱/
│   ├── 7_元数据与索引/
│   ├── 8_外购数据管理/
│   └── 9_数据流水线/
├── scripts/                        # 运维脚本
│   ├── init_all.py                 # 初始化所有服务
│   ├── rebuild_index.py            # 重建索引
│   └── eval_rag.py                 # RAG 评估
└── docs/                           # 项目文档
    └── dev_guide.md                # 本文档
```

---

## 开发优先级建议

如果资源有限，建议按以下优先级分批落地：

**MVP（最小可用版本）— 4 周**：
1. Phase 1 基础设施（精简版：仅 Qdrant + PostgreSQL + Redis）
2. Phase 2 仅支持 .md 直接编辑（暂不做 PDF/音频自动转换）
3. Phase 3 RAG 核心（BGE-M3 + Qdrant + 简单 Prompt）
4. Phase 5 精简 API（仅检索 + RAG 问答）

**V1.0 — 8 周**：
5. Phase 2 完整流水线（Pandoc + Whisper + OCR）
6. Phase 4 知识图谱
7. Phase 5 完整 API
8. Phase 6 小程序集成

**V2.0 — 12 周**：
9. Reranking 精排
10. 学习路径推荐算法
11. 听力训练完整功能
12. 监控告警与性能优化
