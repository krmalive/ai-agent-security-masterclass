"""Lab orchestrator: input guard → plan → MODE gate → validate → execute → reply."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from backend.config import Config

from .agents import LLMClient, PolicyAssistant
from .guardrails import (
    MemoryValidator,
    disabled_guardrail,
    run_defense_input_guardrail,
    run_defense_output_guarded_response,
    summarize_trace_for_output_review,
)


def memory_write_policy_from_mode() -> Dict[str, Any]:
    on = (Config.MODE or "attack").strip().lower() == "defense"
    return {
        "should_validate_memory_writes": on,
        "reasoning": (
            "MODE=defense: MemoryValidator runs before add_to_memory."
            if on
            else "MODE=attack: MemoryValidator is not invoked; writes go to Chroma (lab poisoning surface)."
        ),
        "policy_profile": "lab_mode",
        "validation_gated_by_mode": True,
    }


def _messages_to_packager_parts(messages: List[Dict[str, str]]) -> Tuple[str, str]:
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    user = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in messages
        if m.get("role") != "system"
    )
    return system, user


class LabAgent:
    """Single teachable entry point for the ASI06 simulation."""

    def __init__(self) -> None:
        self.assistant = PolicyAssistant()
        self.validator = MemoryValidator()
        self.llm = LLMClient()

    def _is_defense(self) -> bool:
        return (Config.MODE or "attack").strip().lower() == "defense"

    def _is_asking_capabilities(self, user_message: str) -> bool:
        lowered = user_message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "what tools",
                "capabilities",
                "what can you do",
                "supported tools",
            )
        )

    def _reply(
        self,
        messages: List[Dict[str, str]],
        defense: bool,
        *,
        trace_for_review: str | None,
        agent_name: str,
    ) -> Tuple[str, Dict[str, Any]]:
        if defense:
            sys_p, user_p = _messages_to_packager_parts(messages)
            return run_defense_output_guarded_response(
                system_instructions=sys_p,
                user_prompt=user_p,
                trace_review_payload=trace_for_review or "{}",
            )
        return (
            self.llm.run_messages_as_agent(messages, agent_name=agent_name),
            disabled_guardrail("output"),
        )

    def _run_pipeline(self, user_message: str) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = []
        validations: List[Dict[str, Any]] = []

        intent = self.assistant.interpret_request(user_message)
        steps.append(
            {"step": "interpret", "label": "Intent classification", "status": "completed", "data": intent}
        )

        memory_context = self.assistant.get_memory_context()
        steps.append(
            {
                "step": "context",
                "label": "Context assembly (incl. policy + recent memory labels)",
                "status": "completed",
                "data": {"context": memory_context[:2000], "has_memory": bool(memory_context)},
            }
        )

        plan = self.assistant.plan_tools(user_message, intent, memory_context)
        if not isinstance(plan, list):
            plan = []
        plan_source = "llm_plan"
        steps.append(
            {
                "step": "plan",
                "label": "Tool plan (LLM)",
                "plan_source": plan_source,
                "status": "completed",
                "data": [
                    {"tool": p.get("tool", ""), "args": p.get("args", {})}
                    for p in plan
                    if isinstance(p, dict)
                ],
            }
        )

        policy_decision = memory_write_policy_from_mode()
        steps.append(
            {
                "step": "policy",
                "label": "Memory write policy (MODE)",
                "status": "completed",
                "data": policy_decision,
            }
        )

        executed: List[Dict[str, Any]] = []
        policy_context = ""

        for item in plan:
            if not isinstance(item, dict):
                continue
            tool_name = item.get("tool", "")
            args = item.get("args", {})
            if not args and tool_name:
                args = {k: v for k, v in item.items() if k != "tool"}

            if tool_name == "add_to_memory":
                content = args.get("content", "")
                category = args.get("category", "fact")
                validated_in_defense = False
                if policy_decision["should_validate_memory_writes"]:
                    validation = self.validator.validate_memory_write(content, category)
                    val_record = {
                        "tool": tool_name,
                        "content": content,
                        "category": category,
                        "allowed": validation["allowed"],
                        "reason": validation["reason"],
                    }
                    validations.append(val_record)
                    steps.append(
                        {
                            "step": "validate",
                            "label": f"Memory write gate: {'ALLOW' if validation['allowed'] else 'BLOCK'}",
                            "status": "blocked" if not validation["allowed"] else "completed",
                            "data": val_record,
                        }
                    )
                    if not validation["allowed"]:
                        executed.append(
                            {
                                "tool": tool_name,
                                "skipped": True,
                                "reason": validation["reason"],
                                "content": content,
                            }
                        )
                        continue
                    validated_in_defense = True
                result = self.assistant.tools.add_to_memory(
                    content=content,
                    category=category,
                    validated_in_defense=validated_in_defense,
                )
                if result.get("status") == "added" and result.get("provenance"):
                    steps.append(
                        {
                            "step": "provenance",
                            "label": "HMAC memory seal",
                            "status": "completed",
                            "data": result["provenance"],
                        }
                    )
                executed.append({"tool": tool_name, "result": result, "skipped": False})
                continue

            if tool_name == "query_memory":
                executed.append(
                    {
                        "tool": tool_name,
                        "result": self.assistant.tools.query_memory(args.get("query", "")),
                        "skipped": False,
                    }
                )
                continue

            if tool_name == "get_refund_policy":
                result = self.assistant.tools.get_refund_policy()
                policy_context = result.get("policy", "")
                executed.append({"tool": tool_name, "result": result, "skipped": False})
                continue

            if tool_name == "query_order":
                executed.append(
                    {
                        "tool": tool_name,
                        "result": self.assistant.tools.query_order(args.get("order_id", "")),
                        "skipped": False,
                    }
                )
                continue

            if tool_name == "process_refund":
                if not policy_context:
                    pol = self.assistant.tools.get_refund_policy()
                    policy_context = pol.get("policy", "")
                executed.append(
                    {
                        "tool": tool_name,
                        "result": self.assistant.tools.process_refund(
                            order_id=args.get("order_id", ""),
                            amount=float(args.get("amount", 0)),
                            reason=args.get("reason", ""),
                            policy_context=policy_context,
                        ),
                        "skipped": False,
                    }
                )

        steps.append(
            {
                "step": "execute",
                "label": "Tool execution",
                "status": "completed" if executed else "skipped",
                "data": executed,
            }
        )
        return {
            "steps": steps,
            "executed": executed,
            "intent": intent,
            "mode": Config.MODE,
            "plan_source": plan_source,
            "policy_decision": policy_decision,
            "validations": validations,
            "memory_context": memory_context[:2000],
            "plan": [
                {"tool": p.get("tool", ""), "args": p.get("args", {})}
                for p in plan
                if isinstance(p, dict)
            ],
        }

    def _build_reply_messages(
        self, user_message: str, intent: Dict[str, Any], executed: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        blocked = [
            e for e in executed
            if e.get("skipped") and "add_to_memory" in str(e.get("tool", ""))
        ]
        if blocked:
            reasons = [
                str(b.get("reason", "")).strip()
                for b in blocked
                if str(b.get("reason", "")).strip()
            ] or ["(empty validator reason)"]
            return [
                {"role": "system", "content": "Tell the user politely that memory could not be stored."},
                {"role": "user", "content": "Blocked reasons:\n" + "\n".join(reasons)},
            ]
        if executed:
            summary = [
                {"tool": e.get("tool"), "result": e.get("result"), "skipped": e.get("skipped")}
                for e in executed
            ]
            return [
                {"role": "system", "content": "Helpful policy assistant. Reply from tool results."},
                {
                    "role": "user",
                    "content": f'User: "{user_message}"\nIntent: {json.dumps(intent)}\n'
                    f"Results:\n{json.dumps(summary, indent=2)}",
                },
            ]
        return [
            {"role": "system", "content": "Helpful policy assistant."},
            {
                "role": "user",
                "content": f'User: "{user_message}"\nIntent: {json.dumps(intent)}\nNo tools ran.',
            },
        ]

    def chat(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]] | None = None,
        context: str = "",
        session_id: str = "",
    ) -> Dict[str, Any]:
        defense = self._is_defense()
        input_guardrail = (
            run_defense_input_guardrail(user_message, context)
            if defense
            else disabled_guardrail("input")
        )

        if defense and input_guardrail.get("tripwire_triggered"):
            return {
                "response": (
                    "Request blocked by defense input policy guardrail. "
                    f"{input_guardrail.get('reasoning', '')}".strip()
                ),
                "agent_triggered": "defense_input_guardrail",
                "results": {
                    "intent": {},
                    "executed": [],
                    "steps": [
                        {
                            "step": "input_guardrail",
                            "label": "Defense input guardrail (SDK)",
                            "status": "blocked",
                            "data": input_guardrail,
                        }
                    ],
                    "mode": Config.MODE,
                    "policy_decision": memory_write_policy_from_mode(),
                    "plan_source": "",
                    "validations": [],
                    "memory_context": "",
                    "plan": [],
                    "input_guardrail": input_guardrail,
                    "output_guardrail": {
                        "enabled": False,
                        "tripwire_triggered": False,
                        "reasoning": "Skipped — input policy blocked the request.",
                        "policy_source": "backend.agent.guardrails",
                    },
                },
            }

        if self._is_asking_capabilities(user_message):
            capabilities = [
                {
                    "name": "Policy Assistant",
                    "description": "Helps with refund policies, order lookup, and memory",
                    "capabilities": [
                        "add_to_memory - store facts, policies, preferences",
                        "query_memory - search stored memory",
                        "get_refund_policy - retrieve refund policy",
                        "query_order - lookup order status",
                        "process_refund - process refund requests",
                    ],
                }
            ]
            messages = [
                {"role": "system", "content": "You describe system capabilities clearly."},
                {
                    "role": "user",
                    "content": f"List these capabilities friendly:\n{json.dumps(capabilities, indent=2)}",
                },
            ]
            cap_trace = (
                json.dumps(
                    {"capability_response": True, "mode": Config.MODE, "user_message": user_message[:1500]},
                    ensure_ascii=True,
                )
                if defense
                else None
            )
            response, output_guardrail = self._reply(
                messages, defense, trace_for_review=cap_trace, agent_name="ASI06CapabilityNarrator"
            )
            return {
                "response": response,
                "agent_triggered": "",
                "results": {
                    "agents_revealed": capabilities,
                    "input_guardrail": input_guardrail,
                    "output_guardrail": output_guardrail,
                },
            }

        result = self._run_pipeline(user_message)
        executed = result.get("executed", [])
        messages = self._build_reply_messages(
            user_message, result.get("intent", {}), executed
        )
        trace_blob = summarize_trace_for_output_review(user_message, result) if defense else None
        response, output_guardrail = self._reply(
            messages, defense, trace_for_review=trace_blob, agent_name="ASI06Responder"
        )
        return {
            "response": response,
            "agent_triggered": "policy_assistant" if executed else "",
            "results": {
                "intent": result.get("intent", {}),
                "executed": executed,
                "steps": result.get("steps", []),
                "mode": result["mode"],
                "policy_decision": result.get("policy_decision", {}),
                "plan_source": result.get("plan_source", ""),
                "validations": result.get("validations", []),
                "memory_context": result.get("memory_context", ""),
                "plan": result.get("plan", []),
                "input_guardrail": input_guardrail,
                "output_guardrail": output_guardrail,
            },
        }


def create_chat_agent() -> LabAgent:
    return LabAgent()
