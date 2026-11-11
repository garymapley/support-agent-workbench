from langchain_openai import ChatOpenAI

from app.config import get_settings


def get_chat_model() -> ChatOpenAI:
    """创建一个使用百炼 OpenAI 兼容接口的聊天模型客户端。"""

    settings = get_settings()
    if (
        not settings.dashscope_api_key
        or settings.dashscope_api_key == "sk-your-key-here"
    ):
        raise RuntimeError(
            "未找到 DASHSCOPE_API_KEY。请将 .env.example 复制为 .env，"
            "然后填入阿里云百炼 API Key。"
        )

    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        temperature=0,
        timeout=settings.model_timeout_seconds,
        max_retries=max(0, settings.external_read_attempts - 1),
    )

