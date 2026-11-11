from app.knowledge_ingestion import ingest_knowledge
from app.qdrant_store import close_qdrant_client


def main() -> None:
    try:
        count = ingest_knowledge()
        print(f"知识库导入完成，共写入 {count} 个文本块。")
    finally:
        close_qdrant_client()


if __name__ == "__main__":
    main()
