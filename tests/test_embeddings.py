import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.embeddings import embed_texts


class EmbeddingBatchTests(unittest.TestCase):
    @patch("app.embeddings.get_embedding_client")
    def test_batches_at_most_ten_texts(self, get_client) -> None:
        client = MagicMock()
        get_client.return_value = client

        def create(**kwargs):
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=index, embedding=[float(index)])
                    for index, _ in enumerate(kwargs["input"])
                ]
            )

        client.embeddings.create.side_effect = create
        result = embed_texts([f"text-{index}" for index in range(23)])

        self.assertEqual(client.embeddings.create.call_count, 3)
        batch_sizes = [
            len(call.kwargs["input"])
            for call in client.embeddings.create.call_args_list
        ]
        self.assertEqual(batch_sizes, [10, 10, 3])
        self.assertEqual(len(result), 23)


if __name__ == "__main__":
    unittest.main()
