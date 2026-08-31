"""Bounded extraction of readable text from public article URLs."""

from dataclasses import dataclass
from ipaddress import ip_address
import socket
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from ingestion.pdf_parser import extract_pdf
from ingestion.text_parser import normalize_text


_MAX_REDIRECTS = 4
_MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
_USER_AGENT = "AIWeekInReviewBot/0.1 (research ingestion; human-reviewed output)"


@dataclass(frozen=True)
class ExtractedWebDocument:
    url: str
    title: str
    text: str
    content_type: str
    links: tuple[str, ...]


def _is_public_host(hostname: str) -> bool:
    """Reject local, private, loopback, reserved, and link-local destinations."""
    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve article host: {hostname}") from exc
    return bool(addresses) and all(ip_address(address).is_global for address in addresses)


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Article URL must use HTTP or HTTPS.")
    if not parsed.hostname or not _is_public_host(parsed.hostname):
        raise ValueError("Article URL must resolve to a public Internet host.")
    return url


def _download(url: str, *, timeout_seconds: float) -> tuple[requests.Response, bytes]:
    session = requests.Session()
    current_url = validate_public_url(url)

    for _ in range(_MAX_REDIRECTS + 1):
        response = session.get(
            current_url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/pdf"},
            timeout=timeout_seconds,
            allow_redirects=False,
            stream=True,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ValueError("Article redirect did not include a destination.")
            current_url = validate_public_url(urljoin(current_url, location))
            continue

        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_DOWNLOAD_BYTES:
            response.close()
            raise ValueError("Article exceeds the maximum download size.")

        content = bytearray()
        for block in response.iter_content(chunk_size=64 * 1024):
            content.extend(block)
            if len(content) > _MAX_DOWNLOAD_BYTES:
                response.close()
                raise ValueError("Article exceeds the maximum download size.")
        return response, bytes(content)

    raise ValueError("Article exceeded the maximum number of redirects.")


def extract_web_document(url: str, *, timeout_seconds: float = 15.0) -> ExtractedWebDocument:
    """Download and extract one public HTML page or text-based PDF."""
    response, content = _download(url, timeout_seconds=timeout_seconds)
    final_url = response.url
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()

    if content_type == "application/pdf" or content.startswith(b"%PDF"):
        parsed_pdf = extract_pdf(content, filename=urlparse(final_url).path.rsplit("/", 1)[-1])
        return ExtractedWebDocument(
            url=final_url,
            title=parsed_pdf.filename,
            text=parsed_pdf.text,
            content_type="application/pdf",
            links=parsed_pdf.links,
        )

    if content_type and content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
        raise ValueError(f"Unsupported article content type: {content_type}")

    decoded = content.decode(response.encoding or "utf-8", errors="replace")
    if content_type == "text/plain":
        return ExtractedWebDocument(
            url=final_url,
            title=urlparse(final_url).path.rsplit("/", 1)[-1] or final_url,
            text=normalize_text(decoded),
            content_type="text/plain",
            links=(),
        )

    soup = BeautifulSoup(decoded, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    heading = soup.find("h1")
    if heading and heading.get_text(" ", strip=True):
        title = heading.get_text(" ", strip=True)

    for element in soup.select(
        "script, style, noscript, svg, nav, footer, header, form, aside, [aria-hidden='true']"
    ):
        element.decompose()
    container = soup.find("article") or soup.find("main") or soup.body
    if container is None:
        raise ValueError("Article page contains no readable body.")

    paragraphs = [
        element.get_text(" ", strip=True)
        for element in container.find_all(["h1", "h2", "h3", "p", "li"])
        if element.get_text(" ", strip=True)
    ]
    text = normalize_text("\n\n".join(paragraphs))
    if len(text) < 200:
        raise ValueError("Article page contains too little readable text.")

    links = tuple(
        dict.fromkeys(
            urljoin(final_url, href)
            for anchor in container.find_all("a", href=True)
            if (href := anchor.get("href")) and urlparse(urljoin(final_url, href)).scheme in {"http", "https"}
        )
    )
    return ExtractedWebDocument(
        url=final_url,
        title=title or final_url,
        text=text,
        content_type="text/html",
        links=links,
    )

