"""Chroma-backed memory: user writes are the poisoning surface for refund policy RAG."""

import os
import uuid
from typing import Any, Dict, List, Tuple

from backend.config import Config

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

REFUND_POLICY_MEMORY_QUERY = "refund policy verification approval"


class MemoryStore:
    """Persist and retrieve memory that can poison refund policy context."""

    def __init__(self) -> None:
        self.client = None
        self.memory_collection = None
        self.baseline_collection = None
        self.is_available = False
        if not CHROMADB_AVAILABLE:
            return
        try:
            os.makedirs(Config.CHROMA_DB_PATH, exist_ok=True)
            from .embeddings import get_embedding_function

            embedding_fn = get_embedding_function()
            self.client = chromadb.PersistentClient(
                path=Config.CHROMA_DB_PATH,
                settings=Settings(anonymized_telemetry=False),
            )
            self.memory_collection = self.client.get_or_create_collection(
                name="memory_entries",
                metadata={"description": "User-added memory"},
                embedding_function=embedding_fn,
            )
            self.baseline_collection = self.client.get_or_create_collection(
                name="baseline_policies",
                metadata={"description": "Read-only baseline policies"},
                embedding_function=embedding_fn,
            )
            self._ensure_seeded()
            self.is_available = True
        except Exception as exc:
            print(f"Error initializing MemoryStore: {exc}")

    def _ensure_seeded(self) -> None:
        if not self.baseline_collection or self.baseline_collection.count() > 0:
            return
        try:
            from .guardrails import seal_entry

            baseline_content = (
                "Refunds require verification of order status and delivery "
                "confirmation before approval."
            )
            baseline_meta = seal_entry(
                baseline_content, "policy", "system", "system"
            )
            baseline_meta["is_baseline"] = True
            self.baseline_collection.add(
                ids=["refund_policy_baseline"],
                documents=[baseline_content],
                metadatas=[baseline_meta],
            )
        except Exception as exc:
            print(f"Error seeding baseline: {exc}")

    def add_entry(
        self,
        content: str,
        category: str = "fact",
        source: str = "user",
        *,
        validated: bool = False,
    ) -> Dict[str, Any]:
        entry_id = f"mem_{uuid.uuid4().hex[:12]}"
        validated_flag = "true" if validated else "false"
        from .guardrails import seal_entry

        meta = seal_entry(content, category, source, validated_flag)
        meta["is_baseline"] = False
        if self.memory_collection:
            try:
                self.memory_collection.add(
                    ids=[entry_id], documents=[content], metadatas=[meta]
                )
                return {
                    "status": "added",
                    "entry_id": entry_id,
                    "content": content,
                    "category": category,
                    "provenance": {
                        "validated": validated_flag,
                        "seal": meta["provenance_seal"],
                        "source": source,
                        "timestamp": meta.get("timestamp", ""),
                        "algorithm": "HMAC-SHA256",
                        "payload_fields": "content|category|source|timestamp|validated",
                    },
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}
        return {
            "status": "added",
            "entry_id": entry_id,
            "content": content,
            "category": category,
            "provenance": {
                "validated": validated_flag,
                "seal": meta["provenance_seal"],
                "source": source,
                "timestamp": meta.get("timestamp", ""),
                "algorithm": "HMAC-SHA256",
                "payload_fields": "content|category|source|timestamp|validated",
            },
        }

    def query_memory_with_trace(
        self, query: str, n_results: int = 5
    ) -> Dict[str, Any]:
        empty = {
            "query": query,
            "n_results_requested": n_results,
            "collection": "memory_entries",
            "hits": [],
        }
        if not self.memory_collection:
            return {**empty, "note": "Chroma not available"}
        try:
            count = self.memory_collection.count()
            if count == 0:
                return empty
            results = self.memory_collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
                include=["metadatas", "distances", "documents"],
            )
            if not results or not results.get("ids") or not results["ids"][0]:
                return empty
            hits = []
            for i, doc_id in enumerate(results["ids"][0]):
                dist = None
                if results.get("distances") and results["distances"][0]:
                    dist = results["distances"][0][i]
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                hits.append(
                    {
                        "id": doc_id,
                        "content": meta.get("content", ""),
                        "category": meta.get("category", "fact"),
                        "source": meta.get("source", "user"),
                        "timestamp": meta.get("timestamp", ""),
                        "validated": meta.get("validated", "false"),
                        "provenance_seal": meta.get("provenance_seal", ""),
                        "distance": dist,
                    }
                )
            return {
                "query": query,
                "n_results_requested": n_results,
                "n_results_returned": len(hits),
                "collection": "memory_entries",
                "distance_note": "Chroma default space: lower distance = more similar",
                "hits": hits,
            }
        except Exception as exc:
            return {**empty, "error": str(exc)}

    def get_baseline_refund_text(self) -> str:
        if self.baseline_collection and self.baseline_collection.count() > 0:
            try:
                results = self.baseline_collection.get(ids=["refund_policy_baseline"])
                if results["ids"]:
                    return results["metadatas"][0][0].get("content", "")
            except Exception:
                pass
        return "Refunds require verification of order status and delivery confirmation."

    def get_refund_policy_with_trace(self) -> Tuple[str, Dict[str, Any]]:
        baseline_text = self.get_baseline_refund_text()
        memory_trace = self.query_memory_with_trace(
            REFUND_POLICY_MEMORY_QUERY, n_results=3
        )
        mode = (Config.MODE or "attack").strip().lower()
        all_hits = memory_trace.get("hits", [])
        from .guardrails import filter_trusted_hits

        if mode == "defense":
            trusted_hits, excluded = filter_trusted_hits(all_hits, mode)
            memory_trace["hits"] = trusted_hits
            provenance_gate: Dict[str, Any] = {
                "mode": "defense",
                "included": len(trusted_hits),
                "excluded": excluded,
            }
        else:
            trusted_hits = all_hits
            provenance_gate = {"mode": "attack", "note": "verification_skipped"}
        memory_parts = [
            f"[Memory: {m.get('content', '')}]" for m in trusted_hits
        ]
        composed = " ".join([baseline_text] + memory_parts).strip()
        trace = {
            "step": "policy_context_composition",
            "description": "Baseline policy + semantically retrieved user memory",
            "baseline": {
                "source": "collection:baseline_policies",
                "id": "refund_policy_baseline",
                "text": baseline_text,
            },
            "memory_retrieval": memory_trace,
            "provenance_gate": provenance_gate,
            "composed_preview": composed[:800] + ("..." if len(composed) > 800 else ""),
        }
        return composed, trace

    def get_all_memory_entries(self) -> List[Dict[str, Any]]:
        if not self.memory_collection:
            return []
        try:
            results = self.memory_collection.get()
            if not results or not results["ids"]:
                return []
            return [
                {
                    "id": results["ids"][i],
                    "content": (results["metadatas"][i] or {}).get("content", ""),
                    "category": (results["metadatas"][i] or {}).get("category", "fact"),
                    "source": (results["metadatas"][i] or {}).get("source", "user"),
                    "timestamp": (results["metadatas"][i] or {}).get("timestamp", ""),
                    "validated": (results["metadatas"][i] or {}).get("validated", "false"),
                    "provenance_seal": (results["metadatas"][i] or {}).get(
                        "provenance_seal", ""
                    ),
                }
                for i in range(len(results["ids"]))
            ]
        except Exception:
            return []

    def get_baseline_policies(self) -> List[Dict[str, Any]]:
        if not self.baseline_collection:
            return []
        try:
            results = self.baseline_collection.get()
            if not results or not results["ids"]:
                return []
            return [
                {"id": results["ids"][i], **results["metadatas"][i]}
                for i in range(len(results["ids"]))
            ]
        except Exception:
            return [
                {
                    "id": "refund_policy_baseline",
                    "content": (
                        "Refunds require verification of order status and "
                        "delivery confirmation."
                    ),
                    "category": "policy",
                }
            ]

    def clear_memory(self) -> Dict[str, Any]:
        if not self.memory_collection:
            return {"status": "cleared", "deleted": 0}
        try:
            ids = self.memory_collection.get().get("ids", [])
            if ids:
                self.memory_collection.delete(ids=ids)
            return {"status": "cleared", "deleted": len(ids)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
