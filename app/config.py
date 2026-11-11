from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从 .env 读取项目配置。"""

    dashscope_api_key: str = ""
    dashscope_base_url: str = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    chat_model: str = "deepseek-v4.1-flash"
    embedding_model: str = "qwen3.7-text-embedding-flash"
    embedding_dimensions: int = 1024
    database_url: str = "sqlite:///./data/app.db"
    qdrant_path: str = "./data/qdrant"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "support_policies"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

