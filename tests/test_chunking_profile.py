"""Tests for corpus-tied chunking profile reports."""

import tempfile
import unittest
from pathlib import Path

from evaluations.chunking import load_corpus, profile_chunking, render_markdown_report
from ingestion.chunker import ChunkingConfig


class ChunkingProfileTests(unittest.TestCase):
    def test_profiles_source_visible_corpus_across_configurations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "launch.md").write_text(
                "Launch summary. " * 140 + "\n\n" + "Practical details. " * 100,
                encoding="utf-8",
            )
            (root / "research.txt").write_text(
                "Research finding. " * 180,
                encoding="utf-8",
            )
            documents = load_corpus(root)
            small = profile_chunking(documents, ChunkingConfig(600, 75))
            large = profile_chunking(documents, ChunkingConfig(1_200, 150))
            report = render_markdown_report(documents, [small, large])

        self.assertEqual(len(documents), 2)
        self.assertGreater(small.chunk_count, large.chunk_count)
        self.assertLessEqual(small.chunk_characters_max, 600)
        self.assertLessEqual(large.chunk_characters_max, 1_200)
        self.assertIn("launch.md", report)
        self.assertIn(documents[0].content_hash, report)
        self.assertIn("Configuration comparison", report)

    def test_empty_corpus_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No supported corpus"):
                load_corpus(directory)


if __name__ == "__main__":
    unittest.main()
