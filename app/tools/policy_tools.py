import json

from langchain_core.tools import tool
from qdrant_client import models

from app.config import get_settings
from app.embeddings import embed_query
from app.qdrant_store import get_qdrant_client


@tool
def search_policy(query: str, policy_type: str = "all") -> str:
    """检索公司售后政策知识库。

    Args:
        query: 需要查询的完整业务问题。
        policy_type: 可选范围：refund、warranty、logistics 或 all。
    """

    settings = get_settings()
    client = get_qdrant_client()
    if not client.collection_exists(settings.qdrant_collection):
        return json.dumps(
            {
                "found": False,
                "message": "政策知识库尚未初始化，请先运行知识导入脚本。",
            },
            ensure_ascii=False,
        )

    must_conditions = [
        models.FieldCondition(
            key="is_active",
            match=models.MatchValue(value=True),
        )
    ]
    normalized_type = policy_type.strip().lower()
    if normalized_type and normalized_type != "all":
        must_conditions.append(
            models.FieldCondition(
                key="policy_type",
                match=models.MatchValue(value=normalized_type),
            )
        )

    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=embed_query(query),
        query_filter=models.Filter(must=must_conditions),
        limit=4,
        with_payload=True,
        score_threshold=0.25,
    )

    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            {
                "text": payload.get("text", ""),
                "source": payload.get("source", ""),
                "title": payload.get("title", ""),
                "policy_type": payload.get("policy_type", ""),
                "version": payload.get("version", ""),
                "effective_date": payload.get("effective_date", ""),
                "score": round(float(point.score), 4),
            }
        )

    return json.dumps(
        {"found": bool(results), "results": results},
        ensure_ascii=False,
    )


POLICY_TOOLS = [search_policy]
