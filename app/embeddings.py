from functools import lru_cache

from openai import OpenAI

from app.config import get_settings


@lru_cache
def get_embedding_client() -> OpenAI:
    settings = get_settings()
    if (
        not settings.dashscope_api_key
        or settings.dashscope_api_key == "sk-your-key-here"
    ):
        raise RuntimeError("DASHSCOPE_API_KEY 未配置，无法生成 Embedding。")

    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    response = get_embedding_client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
        encoding_format="float",
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
