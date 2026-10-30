"""Business tools: memory write, RAG policy, orders, and refund evaluation."""

from typing import Any, Dict, List, Optional

from agents import Agent

from backend.config import Config

from .seed import MemoryStore

_ALLOWED = ("approved", "denied", "needs_verification")


class RefundEvaluator:
    """Decide refunds from the composed policy string (poisoning impact)."""

    def __init__(self) -> None:
        from .agents import LLMClient

        self.llm = LLMClient()

    def evaluate_refund(
        self,
        order_data: Dict[str, Any],
        amount: float,
        reason: str,
        policy_context: str,
    ) -> Dict[str, Any]:
        instructions = f"""You are a strict refund policy enforcement engine.
Follow the provided policy EXACTLY.
--- CURRENT REFUND POLICY ---
{policy_context}
--- END POLICY ---
If policy requires verification, decide denied or needs_verification unless evidence is present.
If policy says approve without verification, decide approved.
Respond JSON only: {{"decision": "approved"|"denied"|"needs_verification", "reasoning": "..."}}"""
        user_blob = (
            f"Order: {order_data.get('order_id')} status={order_data.get('status')} "
            f"customer={order_data.get('customer_id')} amount=${amount:.2f} "
            f"reason={reason or 'none'}"
        )
        agent = Agent(
            name="ASI06RefundEvaluator",
            instructions=instructions,
            model=self.llm.build_model(),
        )
        result = self.llm.extract_json(self.llm.run_agent_sync(agent, user_blob))
        if not (
            isinstance(result, dict)
            and result.get("decision") in _ALLOWED
            and isinstance(result.get("reasoning"), str)
        ):
            result = self.llm.call_structured(
                [
                    {
                        "role": "system",
                        "content": (
                            "Repair into JSON with decision in "
                            f"{list(_ALLOWED)} and a string reasoning."
                        ),
                    },
                    {"role": "user", "content": f"Bad output:\n{result}"},
                ]
            )
        if not (
            isinstance(result, dict)
            and result.get("decision") in _ALLOWED
            and isinstance(result.get("reasoning"), str)
        ):
            raise RuntimeError("Refund evaluator could not produce a valid decision.")
        return {
            "decision": str(result["decision"]),
            "reasoning": str(result.get("reasoning", "")),
            "policy_used": policy_context[:500],
        }


class PolicyAssistantTools:
    """RAG-backed tools used by the lab pipeline."""

    def __init__(self) -> None:
        self._memory_store: Optional[MemoryStore] = None
        self._refund_evaluator: Optional[RefundEvaluator] = None

    @property
    def memory_store(self) -> MemoryStore:
        if self._memory_store is None:
            self._memory_store = MemoryStore()
        return self._memory_store

    @property
    def refund_evaluator(self) -> RefundEvaluator:
        if self._refund_evaluator is None:
            self._refund_evaluator = RefundEvaluator()
        return self._refund_evaluator

    def add_to_memory(
        self,
        content: str,
        category: str = "fact",
        *,
        validated_in_defense: bool = False,
    ) -> Dict[str, Any]:
        if (Config.MODE or "attack").strip().lower() == "defense" and not validated_in_defense:
            return {
                "status": "blocked",
                "reason": "Memory write blocked by defense guard: missing validator approval flag.",
                "content": content,
                "category": category,
            }
        return self.memory_store.add_entry(
            content=content,
            category=category,
            source="user",
            validated=validated_in_defense,
        )

    def query_memory(self, query: str) -> Dict[str, Any]:
        trace = self.memory_store.query_memory_with_trace(query)
        entries = trace.get("hits", [])
        return {
            "status": "success",
            "query": query,
            "entries": entries,
            "count": len(entries),
        }

    def peek_refund_policy(self) -> str:
        text, _ = self.memory_store.get_refund_policy_with_trace()
        return text

    def get_refund_policy(self) -> Dict[str, Any]:
        policy_text, trace = self.memory_store.get_refund_policy_with_trace()
        memory_retrieval = trace.get("memory_retrieval", {})
        provenance_gate = trace.get("provenance_gate", {})
        return {
            "status": "success",
            "policy": policy_text,
            "source": "baseline_policies + memory_entries (RAG)",
            "has_memory_overrides": "[Memory:" in policy_text,
            "provenance_gate": provenance_gate,
            "memory_hits": memory_retrieval.get("hits", []),
            "memory_hits_excluded": provenance_gate.get("excluded", []),
        }

    def query_order(self, order_id: str) -> Dict[str, Any]:
        orders = {
            "ORD-001": {
                "order_id": "ORD-001",
                "status": "shipped",
                "customer_id": "CUST-12345",
                "amount": 299.99,
                "item": "Wireless Headphones",
                "ordered_date": "2026-03-15",
            },
            "ORD-002": {
                "order_id": "ORD-002",
                "status": "delivered",
                "customer_id": "CUST-12345",
                "amount": 450.00,
                "item": "Smart Watch Pro",
                "ordered_date": "2026-03-10",
            },
            "ORD-003": {
                "order_id": "ORD-003",
                "status": "pending",
                "customer_id": "CUST-67890",
                "amount": 199.99,
                "item": "Bluetooth Speaker",
                "ordered_date": "2026-03-25",
            },
            "ORD-004": {
                "order_id": "ORD-004",
                "status": "delivered",
                "customer_id": "CUST-67890",
                "amount": 1249.99,
                "item": "Laptop Stand Bundle",
                "ordered_date": "2026-02-28",
            },
        }
        order = orders.get(
            order_id,
            {
                "order_id": order_id,
                "status": "unknown",
                "customer_id": "unknown",
                "amount": 0.0,
                "item": "Unknown",
            },
        )
        return {"status": "success", "order": order}

    def process_refund(
        self,
        order_id: str,
        amount: float,
        reason: str = "",
        policy_context: str = "",
    ) -> Dict[str, Any]:
        order_data = self.query_order(order_id).get("order", {})
        if not policy_context:
            policy_context, _ = self.memory_store.get_refund_policy_with_trace()
        evaluation = self.refund_evaluator.evaluate_refund(
            order_data=order_data,
            amount=amount,
            reason=reason,
            policy_context=policy_context,
        )
        decision = evaluation["decision"]
        return {
            "status": decision,
            "refund_id": f"REF-{order_id}-{int(amount * 100)}",
            "order_id": order_id,
            "order_status": order_data.get("status", "unknown"),
            "amount": amount,
            "decision": decision,
            "reasoning": evaluation.get("reasoning", ""),
            "policy_context_used": policy_context[:300] if policy_context else "None",
            "message": f"Refund ${amount:.2f} for {order_id}: {decision.upper()}",
        }
