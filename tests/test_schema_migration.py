import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect, text

import app.database as database


class LegacySchemaMigrationTest(unittest.TestCase):
    """验证旧库缺列时自动补齐，避免升级后查询直接报错。"""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self._temp_dir.name) / "legacy.db"
        self._url = f"sqlite:///{database_path.as_posix()}"
        self._engine = create_engine(self._url)
        self._original_settings = database.settings
        self._original_engine = database.engine
        database.settings = SimpleNamespace(database_url=self._url)
        database.engine = self._engine

    def tearDown(self) -> None:
        database.settings = self._original_settings
        database.engine = self._original_engine
        self._engine.dispose()
        self._temp_dir.cleanup()

    def test_legacy_ticket_table_gains_thread_id(self) -> None:
        # 这张旧表没有 approval_requests 配套，迁移函数也不应提前返回。
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE support_tickets ("
                    "id INTEGER PRIMARY KEY, ticket_id VARCHAR(40))"
                )
            )

        database._migrate_existing_sqlite_schema()

        column_names = {
            column["name"]
            for column in inspect(self._engine).get_columns("support_tickets")
        }
        self.assertIn("thread_id", column_names)
