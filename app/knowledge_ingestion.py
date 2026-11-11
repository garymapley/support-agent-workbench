from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import models

from app.config import get_settings
from app.embeddings import embed_texts
from app.knowledge_loader import load_knowledge_chunks
from app.qdrant_store import get_qdrant_client, rebuild_policy_collection


def ingest_knowledge(knowledge_dir: Path = Path("knowledge")) -> int:
    chunks = load_knowledge_chunks(knowledge_dir)
    if not chunks:
        raise RuntimeError(f"在 {knowledge_dir} 中没有找到可导入的 Markdown 文档。")

    vectors = embed_texts([chunk.text for chunk in chunks])
    rebuild_policy_collection()

    settings = get_settings()
    points = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        point_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{chunk.source}:{chunk.chunk_index}:{chunk.text}",
            )
        )
        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "text": chunk.text,
                    "source": chunk.source,
                    "title": chunk.title,
                    "policy_type": chunk.policy_type,
                    "version": chunk.version,
                    "effective_date": chunk.effective_date,
                    "is_active": chunk.is_active,
                    "chunk_index": chunk.chunk_index,
                },
            )
        )

    get_qdrant_client().upsert(
        collection_name=settings.qdrant_collection,
        points=points,
        wait=True,
    )
    return len(points)
