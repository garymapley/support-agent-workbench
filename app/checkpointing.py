import sqlite3
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import get_settings


_connection: sqlite3.Connection | None = None


@lru_cache
def get_checkpointer() -> SqliteSaver:
    """为主 Agent 与审批子流程提供同一个 SQLite 检查点存储。"""

    global _connection
    checkpoint_path = Path(get_settings().checkpoint_database_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    _connection = sqlite3.connect(
        checkpoint_path,
        check_same_thread=False,
    )
    return SqliteSaver(_connection)


def close_checkpointer() -> None:
    global _connection
    if _connection is None:
        return
    _connection.close()
    _connection = None
    get_checkpointer.cache_clear()
