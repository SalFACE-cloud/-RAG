"""教育知识库 RAG 项目入口。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def print_help():
    print("""
教育知识库 RAG - 常用命令

  python main.py index          # 增量索引 vault（.md / .docx / .pdf）
  python main.py index --force  # 强制全量重建索引
  python main.py convert        # 仅转换非 Markdown 文件到 vault/_converted/
  python main.py manifest       # 生成 chunk manifest（供评估集标注）
  python main.py eval           # 运行黄金评估集（检索+LLM 生成，消耗 token）
  python main.py eval --retrieval-only  # 仅检索指标，不调用 LLM
  python main.py eval --split test      # 只跑 test 集
  python main.py graph          # 重建 Neo4j 知识图谱（需 GRAPH_ENABLED=true）
  python main.py pipeline       # Phase1 基础设施 + Phase2 流水线（一键）
  python main.py worker         # 启动 RQ Worker（Phase 2 任务队列）
  python main.py enqueue        # 将待处理文件入队
  python main.py retry-failed   # 列出/重试失败任务（可加 --retry）
  python main.py api            # 启动 FastAPI 服务

API: Swagger http://localhost:8000/docs
RAG: WebSocket ws://localhost:8000/api/v1/rag/ws

前置步骤:
  1. docker compose up -d
  2. pip install -r requirements.txt
  3. 复制 .env.example 为 .env 并配置 LLM（可选）
  4. DOCX/PDF 转换需安装 Pandoc: https://pandoc.org/installing.html
  5. 知识图谱需设置 GRAPH_ENABLED=true 并启动 Neo4j 容器
""")


def main():
    if len(sys.argv) < 2:
        print_help()
        return

    cmd = sys.argv[1]
    if cmd == "index":
        from services.pipeline.main import run_batch
        run_batch(force="--force" in sys.argv)
    elif cmd == "convert":
        from services.pipeline.main import run_convert_only
        run_convert_only()
    elif cmd == "manifest":
        from scripts.generate_manifest import main as gen_main
        gen_main()
    elif cmd == "eval":
        from eval.run_eval import main as eval_main
        raise SystemExit(eval_main(sys.argv[2:]))
    elif cmd == "api":
        import uvicorn
        uvicorn.run("services.api.app:app", host="0.0.0.0", port=8000, reload=True)
    elif cmd == "graph":
        from scripts.rebuild_graph import main as graph_main
        raise SystemExit(graph_main())
    elif cmd == "pipeline":
        from scripts.run_pipeline import main as pipeline_main
        raise SystemExit(pipeline_main(sys.argv[2:]))
    elif cmd == "worker":
        from services.pipeline.main import run_worker
        run_worker(burst="--burst" in sys.argv)
    elif cmd == "enqueue":
        from services.pipeline.main import enqueue_changed_files

        job_ids = enqueue_changed_files()
        print(f"已入队 {len(job_ids)} 个任务")
    elif cmd == "retry-failed":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from scripts.retry_failed import main as retry_main

        raise SystemExit(retry_main())
    else:
        print(f"未知命令: {cmd}")
        print_help()


if __name__ == "__main__":
    main()
