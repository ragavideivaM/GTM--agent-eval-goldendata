"""Tests for OpenAI embedding generation without live API calls."""

import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from config import Settings
from research.embeddings import OpenAIEmbedder


@dataclass
class FakeEmbedding:
    index: int
    embedding: list[float]


class FakeEmbeddingsResource:
    def __init__(self, dimensions: int, *, reverse_results: bool = False) -> None:
        self.dimensions = dimensions
        self.reverse_results = reverse_results
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        inputs = kwargs["input"]
        assert isinstance(inputs, list)
        data = [
            FakeEmbedding(index=index, embedding=[float(index + 1)] * self.dimensions)
            for index, _ in enumerate(inputs)
        ]
        if self.reverse_results:
            data.reverse()
        return SimpleNamespace(
            data=data,
            usage=SimpleNamespace(total_tokens=len(inputs) * 10),
        )


class FakeClient:
    def __init__(self, resource: FakeEmbeddingsResource) -> None:
        self.embeddings = resource


def test_settings(dimensions: int = 4) -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_embedding_model="test-embedding-model",
        openai_embedding_dimensions=dimensions,
    )


class OpenAIEmbedderTests(unittest.TestCase):
    def test_empty_collection_requires_no_api_call(self) -> None:
        resource = FakeEmbeddingsResource(4)
        embedder = OpenAIEmbedder(test_settings(), client=FakeClient(resource))
        result = embedder.embed_texts([])
        self.assertEqual(result.vectors, [])
        self.assertEqual(resource.calls, [])

    def test_rejects_blank_input(self) -> None:
        resource = FakeEmbeddingsResource(4)
        embedder = OpenAIEmbedder(test_settings(), client=FakeClient(resource))
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            embedder.embed_texts(["valid", "  "])

    def test_batches_inputs_and_accumulates_usage(self) -> None:
        resource = FakeEmbeddingsResource(4)
        embedder = OpenAIEmbedder(
            test_settings(), client=FakeClient(resource), batch_size=2
        )
        result = embedder.embed_texts(["one", "two", "three", "four", "five"])
        self.assertEqual([len(call["input"]) for call in resource.calls], [2, 2, 1])
        self.assertEqual(len(result.vectors), 5)
        self.assertEqual(result.total_tokens, 50)

    def test_restores_api_results_to_input_order(self) -> None:
        resource = FakeEmbeddingsResource(4, reverse_results=True)
        embedder = OpenAIEmbedder(test_settings(), client=FakeClient(resource))
        result = embedder.embed_texts(["first", "second"])
        self.assertEqual(result.vectors[0], [1.0] * 4)
        self.assertEqual(result.vectors[1], [2.0] * 4)

    def test_query_returns_one_vector(self) -> None:
        resource = FakeEmbeddingsResource(4)
        embedder = OpenAIEmbedder(test_settings(), client=FakeClient(resource))
        self.assertEqual(embedder.embed_query("AI launches this week"), [1.0] * 4)

    def test_rejects_unexpected_vector_dimension(self) -> None:
        resource = FakeEmbeddingsResource(3)
        embedder = OpenAIEmbedder(test_settings(4), client=FakeClient(resource))
        with self.assertRaisesRegex(RuntimeError, "unexpected dimension"):
            embedder.embed_texts(["text"])


if __name__ == "__main__":
    unittest.main()

