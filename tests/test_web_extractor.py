"""HTML extraction tests using a mocked HTTP download."""

import unittest
from unittest.mock import patch

from ingestion.web_extractor import extract_web_document, validate_public_url


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "text/html") -> None:
        self.body = body
        self.url = "https://example.com/story"
        self.encoding = "utf-8"
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(body))}
        self.is_redirect = False
        self.is_permanent_redirect = False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield self.body

    def close(self) -> None:
        return None


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, *args: object, **kwargs: object) -> FakeResponse:
        return self.response


class WebExtractorTests(unittest.TestCase):
    def test_rejects_localhost(self) -> None:
        with self.assertRaisesRegex(ValueError, "public Internet host"):
            validate_public_url("http://localhost/private")

    @patch("ingestion.web_extractor.validate_public_url", return_value="https://example.com/story")
    @patch("ingestion.web_extractor.requests.Session")
    def test_extracts_article_and_removes_navigation(self, session_class, _validate) -> None:
        body = b"""
        <html><head><title>Page title</title></head><body>
        <nav>Navigation that should disappear</nav>
        <article><h1>Important AI Launch</h1>
        <p>This is a detailed opening paragraph about a significant artificial
        intelligence launch and the users who will benefit from the release.</p>
        <p>The second paragraph explains practical implications, availability,
        limitations, and enough additional context for grounded editorial work.</p>
        <a href="/source">Original source</a></article>
        </body></html>
        """
        session_class.return_value = FakeSession(FakeResponse(body))
        result = extract_web_document("https://example.com/story")
        self.assertEqual(result.title, "Important AI Launch")
        self.assertNotIn("Navigation", result.text)
        self.assertIn("practical implications", result.text)
        self.assertEqual(result.links, ("https://example.com/source",))


if __name__ == "__main__":
    unittest.main()

