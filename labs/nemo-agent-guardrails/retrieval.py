"""Tiny keyword retriever over the NovaBank knowledge base (data/kb/*.md).

Deliberately simple — the lesson in this lab is what happens to retrieved
content *after* retrieval, not vector search. Each markdown file is one
chunk; documents are scored by query-term overlap.

CHUNK_SEPARATOR must match the constant in
guardrails/config/retrieval_rails/actions.py — the retrieval rails split the
combined context back into chunks on it.
"""

import re
from dataclasses import dataclass
from pathlib import Path

KB_DIR = Path(__file__).parent / "data" / "kb"
CHUNK_SEPARATOR = "\n\n=====\n\n"

_WORD_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "how",
    "what", "when", "where", "which", "who", "why", "i", "my", "me", "you",
    "your", "for", "of", "on", "in", "to", "and", "or", "it", "with", "can",
}


@dataclass
class Chunk:
    source: str
    content: str
    score: float

    def as_context(self) -> str:
        return f"[SOURCE: {self.source}]\n{self.content.strip()}"


def _tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


def load_documents() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(KB_DIR.glob("*.md"))
    }


def search(query: str, k: int = 3) -> list[Chunk]:
    """Return the top-k documents by keyword overlap with the query."""
    query_terms = _tokenize(query)
    results: list[Chunk] = []
    for name, content in load_documents().items():
        doc_terms = _tokenize(content)
        title_terms = _tokenize(name)
        if not query_terms:
            continue
        score = 0.0
        for term in query_terms:
            score += doc_terms.count(term)
            # filename hits are a strong signal in a KB this small
            score += 3.0 * title_terms.count(term)
        if score > 0:
            results.append(Chunk(source=name, content=content, score=score))
    results.sort(key=lambda c: c.score, reverse=True)
    return results[:k]


def join_chunks(chunks: list[Chunk]) -> str:
    """Combine chunks into the single string NeMo exposes as $relevant_chunks."""
    return CHUNK_SEPARATOR.join(chunk.as_context() for chunk in chunks)
