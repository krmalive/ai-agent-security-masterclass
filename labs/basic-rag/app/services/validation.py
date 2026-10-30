from __future__ import annotations

from app.config import Settings
from app.domain.models import Citation, TestingPlan
from app.rag.manifest import build_manifest


def enrich_citations(plan: TestingPlan, settings: Settings) -> TestingPlan:
    """Best-effort citation enrichment that never rejects the agent's report."""
    manifest = build_manifest(str(settings.wstg_pdf_path))
    for test in plan.tests:
        entry = manifest.get(test.scenario_id.strip().upper())
        if not entry:
            test.citation = None
            continue
        pages = (
            str(entry.start_page)
            if entry.start_page == entry.end_page
            else f"{entry.start_page}-{entry.end_page}"
        )
        test.scenario_id = entry.scenario_id
        test.title = entry.title
        test.citation = Citation(
            scenario_id=entry.scenario_id,
            title=entry.title,
            pages=pages,
            excerpt=entry.excerpt,
        )
    return plan
