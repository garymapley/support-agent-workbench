import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.knowledge_ingestion import ingest_knowledge

MINIMAL_POLICY = """---
title: 测试用政策
policy_type: refund
version: "1.0"
effective_date: "2026-01-01"
is_active: true
---

## 一、适用范围

用于验证导入护栏的最小文档。

## 二、判定

正文内容仅用于单元测试。

## 三、处理

不做任何真实处理。

## 四、责任

无。
"""


class IngestionGuardTests(unittest.TestCase):
    def test_detects_points_left_over_from_previous_index(self) -> None:
        client = MagicMock()
        client.count.return_value = MagicMock(count=2)

        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_dir = Path(tmp_dir)
            (policy_dir / "test_policy.md").write_text(
                MINIMAL_POLICY, encoding="utf-8"
            )

            with (
                patch("app.knowledge_ingestion.embed_texts", return_value=[[0.1, 0.2]]),
                patch("app.knowledge_ingestion.get_qdrant_client", return_value=client),
                patch("app.knowledge_ingestion.rebuild_policy_collection"),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    ingest_knowledge(policy_dir)

        self.assertIn("索引点数校验失败", str(ctx.exception))

    def test_passes_when_point_count_matches(self) -> None:
        client = MagicMock()
        client.count.return_value = MagicMock(count=1)

        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_dir = Path(tmp_dir)
            (policy_dir / "test_policy.md").write_text(
                MINIMAL_POLICY, encoding="utf-8"
            )

            with (
                patch("app.knowledge_ingestion.embed_texts", return_value=[[0.1, 0.2]]),
                patch("app.knowledge_ingestion.get_qdrant_client", return_value=client),
                patch("app.knowledge_ingestion.rebuild_policy_collection"),
            ):
                written = ingest_knowledge(policy_dir)

        self.assertEqual(written, 1)


if __name__ == "__main__":
    unittest.main()
