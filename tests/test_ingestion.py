"""Unit tests for local ingestion behavior."""

import unittest
from datetime import date
from io import BytesIO
from unittest.mock import patch

from openpyxl import Workbook

from ingestion.chunker import ChunkingConfig, chunk_source, chunk_text
from ingestion.excel_parser import extract_excel
from ingestion.service import IngestionInput, ingest_excel, ingest_text, ingest_web_candidate
from ingestion.text_parser import normalize_text
from ingestion.web_extractor import ExtractedWebDocument
from models.research import NewsCandidate
from models.source import SourceType


class TextParserTests(unittest.TestCase):
    def test_normalize_text_preserves_paragraphs(self) -> None:
        raw = "  First   sentence.\r\n\r\n\r\n Second\tparagraph.  "
        self.assertEqual(normalize_text(raw), "First sentence.\n\nSecond paragraph.")

    def test_normalize_text_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            normalize_text("  \n  ")


class ExcelParserTests(unittest.TestCase):
    @staticmethod
    def workbook_bytes() -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "AI News"
        sheet.append(["Headline", "Source", "Published"])
        sheet.append(
            ["Example launch", "https://example.com/story", "2026-08-25"]
        )
        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()
        return buffer.getvalue()

    def test_extracts_sheet_rows_as_searchable_text(self) -> None:
        parsed = extract_excel(self.workbook_bytes(), "news.xlsx")
        self.assertEqual(parsed.sheet_names, ("AI News",))
        self.assertEqual(parsed.row_count, 2)
        self.assertIn("https://example.com/story", parsed.text)

    def test_ingest_excel_creates_evidence_chunks(self) -> None:
        metadata = IngestionInput(title="Weekly sources", week_id="2026-W35")
        source, chunks, parsed = ingest_excel(
            self.workbook_bytes(), metadata, filename="news.xlsx"
        )
        self.assertEqual(source.week_id, "2026-W35")
        self.assertEqual(parsed.filename, "news.xlsx")
        self.assertGreaterEqual(len(chunks), 1)


class ChunkerTests(unittest.TestCase):
    def test_chunks_respect_limit_for_regular_text(self) -> None:
        text = "\n\n".join(["word " * 45 for _ in range(5)])
        chunks = chunk_text(text, ChunkingConfig(max_characters=300, overlap_characters=40))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 300 for chunk in chunks))

    def test_chunk_ids_are_stable_and_ordered(self) -> None:
        metadata = IngestionInput(
            title="AI launch",
            week_id="2026-W35",
            source_type=SourceType.OFFICIAL,
            published_at=date(2026, 8, 25),
        )
        source, chunks = ingest_text("A useful announcement. " * 80, metadata)
        repeated = chunk_source(source)
        self.assertEqual([chunk.chunk_id for chunk in chunks], [chunk.chunk_id for chunk in repeated])
        self.assertEqual(chunks[0].chunk_id, f"{source.document_id}#chunk-0000")


class IngestionServiceTests(unittest.TestCase):
    def test_ingest_text_populates_source_metadata(self) -> None:
        metadata = IngestionInput(
            title="Example story",
            week_id="2026-W35",
            url="https://example.com/story",
            publisher="Example",
        )
        source, chunks = ingest_text("Important AI news with practical implications.", metadata)
        self.assertEqual(source.week_id, "2026-W35")
        self.assertEqual(str(source.url), "https://example.com/story")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].document_id, source.document_id)

    @patch("ingestion.service.extract_web_document")
    def test_ingest_web_candidate_preserves_discovery_metadata(self, extract) -> None:
        extract.return_value = ExtractedWebDocument(
            url="https://example.com/final-story",
            title="Page title",
            text="Detailed source text about an important AI announcement. " * 10,
            content_type="text/html",
            links=("https://example.com/source",),
        )
        candidate = NewsCandidate(
            headline="Important AI announcement",
            url="https://example.com/story",
            publisher="Example",
            published_at=date(2026, 8, 25),
            summary="A new AI capability was announced.",
            why_it_matters="It affects product teams.",
            category="feature",
            source_type="official",
            confidence="high",
        )
        source, chunks, extracted = ingest_web_candidate(candidate, "2026-W35")
        self.assertEqual(str(source.url), "https://example.com/final-story")
        self.assertEqual(source.topic, "feature")
        self.assertEqual(source.source_type, SourceType.OFFICIAL)
        self.assertEqual(source.week_id, "2026-W35")
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(extracted.links, ("https://example.com/source",))


if __name__ == "__main__":
    unittest.main()
