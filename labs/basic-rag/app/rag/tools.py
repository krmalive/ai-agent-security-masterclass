from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import Settings

import chromadb
from chromadb.config import Settings as ChromaSettings
from crewai.tools import BaseTool
from crewai_tools import PDFSearchTool
from pydantic import BaseModel, Field, PrivateAttr

from app.rag.manifest import build_manifest, extract_scenario_text

EventSink = Callable[[str, str, str | None, dict[str, Any] | None], None]


class EmptyInput(BaseModel):
    pass


class FileInput(BaseModel):
    path: str = Field(description="Path relative to the ShopFast application root")


class CodeSearchInput(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=200,
        description=(
            "Case-insensitive regular expression to grep for, such as "
            "'Depends\\(|Header\\(|UploadFile|webhook|owner_id'"
        ),
    )
    path_glob: str = Field(
        default="**/*",
        max_length=100,
        description="Optional relative file glob, for example '**/*.py' or 'frontend/*.js'",
    )
    max_results: int = Field(default=40, ge=1, le=80)


class SearchInput(BaseModel):
    query: str = Field(min_length=3, description="A focused WSTG semantic search query")


class ReferenceInput(BaseModel):
    scenario_id: str = Field(description="Exact WSTG scenario identifier, for example WSTG-ATHZ-04")


class ListApplicationFilesTool(BaseTool):
    name: str = "list_application_files"
    description: str = "List every source and documentation file in the ShopFast application fixture."
    args_schema: type[BaseModel] = EmptyInput
    _root: Path = PrivateAttr()
    _emit: EventSink = PrivateAttr()

    def __init__(self, root: Path, emit: EventSink):
        super().__init__()
        self._root = root
        self._emit = emit

    def _run(self) -> str:
        files = sorted(
            str(path.relative_to(self._root))
            for path in self._root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        self._emit("code_inventory", f"Discovered {len(files)} application files", "Application Analyst", {"files": files})
        return "\n".join(files)


class ReadApplicationFileTool(BaseTool):
    name: str = "read_application_file"
    description: str = "Read one ShopFast file using a path returned by list_application_files."
    args_schema: type[BaseModel] = FileInput
    _root: Path = PrivateAttr()
    _emit: EventSink = PrivateAttr()

    def __init__(self, root: Path, emit: EventSink):
        super().__init__()
        self._root = root.resolve()
        self._emit = emit

    def _run(self, path: str) -> str:
        target = (self._root / path).resolve()
        if not target.is_relative_to(self._root) or not target.is_file():
            raise ValueError("Path must identify a file inside the ShopFast fixture")
        text = target.read_text(encoding="utf-8")
        self._emit("code_file_opened", f"Read {path}", "Application Analyst", {"path": path, "characters": len(text)})
        return text


class GrepApplicationCodeTool(BaseTool):
    name: str = "grep_application_code"
    description: str = (
        "Search across ShopFast source and documentation before choosing files to read. "
        "Returns matching relative paths, line numbers, and source lines. Use targeted regexes "
        "to follow routes, auth checks, object ownership, inputs, uploads, tokens, providers, and workflows."
    )
    args_schema: type[BaseModel] = CodeSearchInput
    _root: Path = PrivateAttr()
    _emit: EventSink = PrivateAttr()

    def __init__(self, root: Path, emit: EventSink):
        super().__init__()
        self._root = root.resolve()
        self._emit = emit

    def _run(self, query: str, path_glob: str = "**/*", max_results: int = 40) -> str:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as error:
            raise ValueError(f"Invalid search expression: {error}") from error

        matches: list[str] = []
        matched_files: set[str] = set()
        for path in sorted(self._root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(self._root)
            if not relative.match(path_glob):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if not pattern.search(line):
                    continue
                matched_files.add(str(relative))
                matches.append(f"{relative}:{line_number}: {line.strip()[:300]}")
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        self._emit(
            "code_search",
            f"Searched ShopFast for /{query}/: {len(matches)} matches in {len(matched_files)} files",
            "Application Analyst",
            {
                "query": query,
                "path_glob": path_glob,
                "matches": matches[:20],
                "truncated": len(matches) >= max_results,
            },
        )
        return "\n".join(matches) if matches else "No matches found."


class ObservedPDFSearchTool(BaseTool):
    name: str = "search_wstg"
    description: str = (
        "Semantically search the OWASP WSTG v4.2 PDF. Use focused queries describing a feature, "
        "risk, or testing technique. Search again when coverage is incomplete."
    )
    args_schema: type[BaseModel] = SearchInput
    _delegate: PDFSearchTool = PrivateAttr()
    _emit: EventSink = PrivateAttr()

    def __init__(self, settings: Settings, emit: EventSink):
        super().__init__()
        self._emit = emit
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        emit(
            "rag_indexing",
            "Preparing the persistent WSTG Chroma collection",
            "WSTG Test Planner",
            {"pdf": settings.wstg_pdf_path.name, "embedding_model": settings.embedding_model},
        )
        chroma_settings = ChromaSettings(
            persist_directory=str(settings.chroma_path),
            allow_reset=True,
            is_persistent=True,
            anonymized_telemetry=False,
        )
        chroma_client = chromadb.PersistentClient(
            path=str(settings.chroma_path), settings=chroma_settings
        )
        collection = next(
            (
                item
                for item in chroma_client.list_collections()
                if item.name == "wstg_v42"
            ),
            None,
        )
        if collection is not None and collection.count() == 0:
            # Recover from an interrupted first run without preserving an empty
            # collection carrying Chroma's default embedding configuration.
            chroma_client.delete_collection("wstg_v42")
            collection = None
        already_indexed = collection is not None and collection.count() > 0
        self._delegate = PDFSearchTool(
            collection_name="wstg_v42",
            limit=6,
            similarity_threshold=0.25,
            config={
                "embedding_model": {
                    "provider": "openai",
                    "config": {
                        "api_key": settings.requesty_api_key,
                        "model_name": settings.embedding_model,
                        "api_base": settings.requesty_base_url,
                    },
                },
                "vectordb": {
                    "provider": "chromadb",
                    "config": {},
                },
            },
        )
        if not already_indexed:
            self._delegate.add(str(settings.wstg_pdf_path))
            indexed_collection = next(
                (
                    item
                    for item in chroma_client.list_collections()
                    if item.name == "wstg_v42"
                ),
                None,
            )
            indexed_chunks = indexed_collection.count() if indexed_collection else 0
            if indexed_chunks == 0:
                raise RuntimeError(
                    "WSTG indexing produced no vectors. Verify the Requesty embedding model and API key."
                )
        else:
            indexed_chunks = collection.count() if collection else 0
        emit(
            "rag_ready",
            "Reused the persistent WSTG vector collection" if already_indexed else "WSTG vector collection is ready",
            "WSTG Test Planner",
            {"indexed_chunks": indexed_chunks, "reused": already_indexed},
        )

    def _run(self, query: str) -> str:
        self._emit("rag_query_started", query, "WSTG Test Planner", {"query": query})
        result = self._delegate._run(query=query, limit=6, similarity_threshold=0.25)
        preview = result[:1800]
        self._emit(
            "rag_results_received",
            "Retrieved candidate WSTG passages",
            "WSTG Test Planner",
            {"query": query, "preview": preview, "characters": len(result)},
        )
        return result


class WSTGReferenceTool(BaseTool):
    name: str = "get_wstg_reference"
    description: str = (
        "Verify an exact WSTG scenario ID and retrieve its authoritative title, PDF pages, and text. "
        "Every selected test must be verified with this tool before inclusion."
    )
    args_schema: type[BaseModel] = ReferenceInput
    _settings: Settings = PrivateAttr()
    _emit: EventSink = PrivateAttr()

    def __init__(self, settings: Settings, emit: EventSink):
        super().__init__()
        self._settings = settings
        self._emit = emit

    def _run(self, scenario_id: str) -> str:
        scenario_id = scenario_id.strip().upper()
        entry = build_manifest(str(self._settings.wstg_pdf_path)).get(scenario_id)
        if not entry:
            self._emit("citation_rejected", f"Unknown WSTG ID: {scenario_id}", "Plan Reviewer", {"scenario_id": scenario_id})
            return json.dumps({"valid": False, "scenario_id": scenario_id})
        payload = entry.as_dict()
        payload["valid"] = True
        payload["text"] = extract_scenario_text(self._settings.wstg_pdf_path, entry)
        self._emit(
            "citation_verified",
            f"Verified {scenario_id} on PDF pages {payload['pages']}",
            "Plan Reviewer",
            {key: payload[key] for key in ("scenario_id", "title", "pages", "excerpt")},
        )
        return json.dumps(payload)
