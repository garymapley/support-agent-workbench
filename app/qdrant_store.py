from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient, models

from app.config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    if settings.qdrant_url:
        return QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=settings.qdrant_timeout_seconds,
        )

    Path(settings.qdrant_path).parent.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=settings.qdrant_path)


def close_qdrant_client() -> None:
    if get_qdrant_client.cache_info().currsize == 0:
        return
    get_qdrant_client().close()
    get_qdrant_client.cache_clear()


def rebuild_policy_collection() -> None:
    settings = get_settings()
    client = get_qdrant_client()
    if client.collection_exists(settings.qdrant_collection):
        client.delete_collection(settings.qdrant_collection)

    if client.collection_exists(settings.qdrant_collection):
        raise RuntimeError(
            f"集合 {settings.qdrant_collection} 删除后仍然存在，"
            "很可能有另一个进程正占用 Qdrant 索引目录。"
            "请先停止后端服务，删除 data/qdrant 目录后重新导入。"
        )

    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=models.VectorParams(
            size=settings.embedding_dimensions,
            distance=models.Distance.COSINE,
        ),
    )
