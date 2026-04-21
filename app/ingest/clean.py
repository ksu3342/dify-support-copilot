import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

NOISE_TAGS = ("script", "style", "noscript", "nav", "footer", "aside", "svg", "form", "button")
NOISE_SELECTORS = (
    "[aria-hidden='true']",
    "[hidden]",
    ".sr-only",
    "#page-context-menu",
    ".feedback-toolbar",
    "#pagination",
    "[class*='sidebar']",
    "[class*='toc']",
    "[class*='breadcrumb']",
    "[class*='pagination']",
    "[class*='feedback']",
)
PRIMARY_CONTENT_SELECTORS = (
    "#content-area #content",
    "#content-area .mdx-content.prose",
    "#content-area .prose",
    "article .prose",
    ".prose",
    "article",
    "main",
)
INVISIBLE_CHAR_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")
SYMBOL_ONLY_PATTERN = re.compile(r"^[^\w]+$")
MIN_PRIMARY_CONTENT_CHARS = 200


def _normalize_whitespace(value: str) -> str:
    value = INVISIBLE_CHAR_PATTERN.sub("", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_title_and_clean_text(html: str) -> Tuple[Optional[str], str]:
    soup = BeautifulSoup(html, "html.parser")

    title = None
    if soup.title and soup.title.string:
        title = _normalize_whitespace(soup.title.get_text(" ", strip=True))

    content_root = _find_primary_content_root(soup)
    body_lines = _extract_lines_from_root(content_root)
    if _joined_length(body_lines) < MIN_PRIMARY_CONTENT_CHARS:
        content_root = _find_fallback_content_root(soup)
        body_lines = _extract_lines_from_root(content_root)

    cleaned_lines: List[str] = []
    page_title = _extract_page_title(soup)
    page_lead = _extract_page_lead(soup)

    _append_unique(cleaned_lines, page_title)
    _append_unique(cleaned_lines, page_lead)
    for line in body_lines:
        _append_unique(cleaned_lines, line)

    return title, "\n".join(cleaned_lines)


def _find_primary_content_root(soup: BeautifulSoup) -> Tag:
    for selector in PRIMARY_CONTENT_SELECTORS:
        nodes = [node for node in soup.select(selector) if isinstance(node, Tag)]
        if nodes:
            return max(nodes, key=lambda node: len(node.get_text(" ", strip=True)))
    return soup.body or soup


def _find_fallback_content_root(soup: BeautifulSoup) -> Tag:
    return soup.find("main") or soup.find("article") or soup.body or soup


def _extract_page_title(soup: BeautifulSoup) -> Optional[str]:
    title_node = soup.select_one("#content-area #page-title") or soup.select_one("#content-area header h1")
    if title_node is None:
        return None
    return _normalize_whitespace(title_node.get_text(" ", strip=True))


def _extract_page_lead(soup: BeautifulSoup) -> Optional[str]:
    header = soup.select_one("#content-area > header")
    if header is None:
        return None
    lead_node = header.select_one(".text-lg p") or header.select_one(".text-lg")
    if lead_node is None:
        return None
    lead_text = _normalize_whitespace(lead_node.get_text(" ", strip=True))
    if not lead_text or lead_text == _extract_page_title(soup):
        return None
    return lead_text


def _extract_lines_from_root(root: Tag) -> List[str]:
    working_root = BeautifulSoup(str(root), "html.parser")
    _prune_noise(working_root)
    raw_text = working_root.get_text("\n", strip=True)
    lines = [_normalize_whitespace(line) for line in raw_text.splitlines()]
    return [line for line in lines if _keep_line(line)]


def _prune_noise(root: BeautifulSoup) -> None:
    for tag_name in NOISE_TAGS:
        for node in root.find_all(tag_name):
            node.decompose()
    for selector in NOISE_SELECTORS:
        for node in root.select(selector):
            node.decompose()


def _keep_line(line: str) -> bool:
    if not line:
        return False
    if line == "Copy page":
        return False
    if SYMBOL_ONLY_PATTERN.fullmatch(line):
        return False
    return True


def _append_unique(lines: List[str], candidate: Optional[str]) -> None:
    if not candidate:
        return
    if lines and lines[-1] == candidate:
        return
    if candidate in lines[:2]:
        return
    lines.append(candidate)


def _joined_length(lines: List[str]) -> int:
    return sum(len(line) for line in lines)
