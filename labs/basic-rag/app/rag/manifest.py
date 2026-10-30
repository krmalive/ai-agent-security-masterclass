from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

WSTG_ID = re.compile(r"WSTG-[A-Z]+-\d{2}")


@dataclass(frozen=True)
class WSTGEntry:
    scenario_id: str
    title: str
    start_page: int
    end_page: int
    excerpt: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "pages": (
                str(self.start_page)
                if self.start_page == self.end_page
                else f"{self.start_page}-{self.end_page}"
            ),
            "excerpt": self.excerpt,
        }


def _clean(text: str) -> str:
    return " ".join(text.split())


def _outline_destinations(reader: PdfReader) -> list[tuple[str, int]]:
    destinations: list[tuple[str, int]] = []

    def walk(items: list[object]) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            try:
                destinations.append((str(getattr(item, "title", "")), reader.get_destination_page_number(item)))
            except (TypeError, ValueError, AttributeError):
                continue

    walk(reader.outline)
    return destinations


@lru_cache(maxsize=4)
def build_manifest(pdf_path: str) -> dict[str, WSTGEntry]:
    reader = PdfReader(pdf_path)
    destinations = _outline_destinations(reader)
    entries: dict[str, WSTGEntry] = {}
    for index, (bookmark_title, page_index) in enumerate(destinations):
        page_text = _clean(reader.pages[page_index].extract_text() or "")
        match = WSTG_ID.search(f"{bookmark_title} {page_text}")
        if not match or match.group(0) in entries:
            continue
        next_page = next(
            (candidate for _, candidate in destinations[index + 1 :] if candidate > page_index),
            page_index + 1,
        )
        end_index = max(page_index, next_page - 1)
        scenario_id = match.group(0)
        title = bookmark_title.strip() or scenario_id
        title = WSTG_ID.sub("", title).strip(" -–—")
        title = re.sub(r"^\d+\s*[-–—]\s*", "", title) or scenario_id
        entries[scenario_id] = WSTGEntry(
            scenario_id=scenario_id,
            title=title,
            start_page=page_index + 1,
            end_page=end_index + 1,
            excerpt=page_text[:1400],
        )
    return entries


def extract_scenario_text(pdf_path: Path, entry: WSTGEntry, max_chars: int = 5000) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for page_number in range(entry.start_page, entry.end_page + 1):
        pages.append(reader.pages[page_number - 1].extract_text() or "")
        if sum(map(len, pages)) >= max_chars:
            break
    return _clean("\n".join(pages))[:max_chars]
