import unittest
from pathlib import Path

from app.knowledge_loader import load_knowledge_chunks


class KnowledgeLoaderTests(unittest.TestCase):
    def test_loads_demo_policies_with_metadata(self) -> None:
        chunks = load_knowledge_chunks(Path("knowledge"))

        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(
            {chunk.policy_type for chunk in chunks},
            {"refund", "warranty", "logistics"},
        )
        self.assertTrue(all(chunk.source.endswith(".md") for chunk in chunks))
        self.assertTrue(all(chunk.is_active for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
