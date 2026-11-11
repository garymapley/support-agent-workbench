from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 数据模型基类。"""


def _prepare_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return

    database_path = database_url.removeprefix(prefix)
    if database_path == ":memory:":
        return

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_prepare_sqlite_directory(settings.database_url)

connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_database() -> None:
    # 导入模型后，SQLAlchemy metadata 才包含对应数据表。
    from app import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_existing_sqlite_schema()


def _migrate_existing_sqlite_schema() -> None:
    """为已有演示数据库执行向后兼容的小型迁移。"""

    if not settings.database_url.startswith("sqlite"):
        return

    table_names = set(inspect(engine).get_table_names())

    if "approval_requests" in table_names:
        column_names = {
            column["name"]
            for column in inspect(engine).get_columns("approval_requests")
        }
        if "thread_id" not in column_names:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE approval_requests "
                        "ADD COLUMN thread_id VARCHAR(160)"
                    )
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_approval_requests_thread_id "
                    "ON approval_requests (thread_id)"
                )
            )

    if "agent_runs" in table_names:
        run_columns = {
            column["name"]
            for column in inspect(engine).get_columns("agent_runs")
        }
        if "run_scope" not in run_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE agent_runs ADD COLUMN "
                        "run_scope VARCHAR(20) NOT NULL DEFAULT 'runtime'"
                    )
                )
                connection.execute(
                    text(
                        "UPDATE agent_runs SET run_scope='evaluation' "
                        "WHERE thread_id LIKE 'agent:eval-%'"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_agent_runs_run_scope "
                        "ON agent_runs (run_scope)"
                    )
                )

    if "support_tickets" in table_names:
        ticket_columns = {
            column["name"]
            for column in inspect(engine).get_columns("support_tickets")
        }
        if "thread_id" not in ticket_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE support_tickets "
                        "ADD COLUMN thread_id VARCHAR(160)"
                    )
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_support_tickets_thread_id "
                    "ON support_tickets (thread_id)"
                )
            )

