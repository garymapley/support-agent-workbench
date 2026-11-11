import unittest
from pathlib import Path

from app.knowledge_loader import load_knowledge_chunks


class KnowledgeLoaderTests(unittest.TestCase):
    def test_loads_demo_policies_with_metadata(self) -> None:
        knowledge_dir = Path("knowledge")
        documents = sorted(knowledge_dir.glob("*.md"))
        chunks = load_knowledge_chunks(knowledge_dir)

        self.assertGreaterEqual(len(documents), 15)
        self.assertLessEqual(len(documents), 20)
        for document in documents:
            content = document.read_text(encoding="utf-8")
            self.assertGreater(len(content), 1000, document.name)
            self.assertGreaterEqual(content.count("\n## "), 4, document.name)

        self.assertGreaterEqual(len(chunks), len(documents))
        self.assertEqual(
            {chunk.policy_type for chunk in chunks},
            {"refund", "warranty", "logistics"},
        )
        self.assertTrue(all(chunk.source.endswith(".md") for chunk in chunks))
        self.assertTrue(any(chunk.is_active for chunk in chunks))
        self.assertTrue(any(not chunk.is_active for chunk in chunks))
        inactive_sources = {
            chunk.source for chunk in chunks if not chunk.is_active
        }
        self.assertEqual(inactive_sources, {"legacy_refund_policy.md"})


if __name__ == "__main__":
    unittest.main()
