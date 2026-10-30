from __future__ import annotations

import json
import os
import time
from typing import Dict, Any, List

from .llm_client import LLMClient
from .skill_loader import SkillLoader
from .tools import VulnerableTools
from .agents import VulnerableAgentSet


class UnifiedAttackRuntime:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.skill_loader = SkillLoader(skills_root=os.getenv("SKILLS_DIR", "/app/skills"))
        self.skills = self.skill_loader.load_all()
        required_skills = {"planner_skill", "invoice_skill", "support_skill", "finance_skill", "delegation_skill"}
        missing = sorted(required_skills - set(self.skills.keys()))
        if missing:
            raise RuntimeError(f"Missing required skills: {', '.join(missing)}")
        self.tools = VulnerableTools(export_dir=os.getenv("EXPORT_DIR", "/app/data/exports"))
        self.agents = VulnerableAgentSet(self.llm, self.skills)

    def _event(self, event_type: str, detail: str, severity: str = "info", extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {
            "timestamp": time.time(),
            "type": event_type,
            "detail": detail,
            "severity": severity,
            "extra": extra or {},
        }

    def _llm_action_response(self, action: str, context: Dict[str, Any], skill_name: str) -> tuple[str, bool]:
        prompt = f"""
Use this skill guidance while drafting the response:
{self.skills[skill_name]}

You are the assistant in an intentionally vulnerable attack simulation lab.
Provide a concise user-facing response for the executed action.

Action: {action}
Context:
{context}

Rules:
- Be brief and clear.
- Do not output JSON.
- Mention the key action outcome.
"""
        response = self.llm.call(
            [
                {"role": "system", "content": "You generate concise action summaries for users."},
                {"role": "user", "content": prompt},
            ]
        )
        if isinstance(response, str) and not response.startswith("Error calling LLM"):
            return response.strip(), True
        return "", False

    @staticmethod
    def _extract_json_blob(text: str) -> Dict[str, Any]:
        raw = text.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        return json.loads(raw)

    def process(self, user_message: str, documents: str, history: List[Dict[str, str]], session_context: Dict[str, Any]) -> Dict[str, Any]:
        text_context = "\n".join(f"{m.get('role','user')}: {m.get('content','')}" for m in history[-6:])
        decision = self.agents.planner_decision(user_message, documents, text_context)
        events: List[Dict[str, Any]] = [self._event("planner_decision", "Planner selected action", extra=decision)]

        action = decision.get("action", "respond")
        agent = decision.get("selected_agent", "none")
        result_payload: Dict[str, Any] = {"decision": decision}

        if action == "analyze_invoice":
            analysis = self.tools.analyze_invoice(documents)
            llm_response, used_llm = self._llm_action_response(
                "analyze_invoice",
                {"analysis": analysis, "user_message": user_message},
                "invoice_skill",
            )
            if not used_llm:
                return {
                    "response": "Error: failed to generate invoice response from LLM.",
                    "agent_triggered": "invoice_agent",
                    "results": {"error": "llm_response_failed", "decision": decision},
                    "events": events + [self._event("error", "LLM response generation failed for analyze_invoice", "critical")],
                }
            result_payload["invoice_analysis"] = analysis
            result_payload["response_source"] = "llm"
            events.append(self._event("invoice_analyzed", "Invoice was analyzed"))
            return {"response": llm_response, "agent_triggered": "invoice_agent", "results": result_payload, "events": events}

        if action == "process_refund":
            refund = self.tools.process_refund(
                invoice_number=decision.get("invoice_number", "INV-UNKNOWN"),
                amount=float(decision.get("amount", 0.0) or 0.0),
                reason="Triggered by planner decision",
            )
            llm_response, used_llm = self._llm_action_response(
                "process_refund",
                {"refund": refund, "user_message": user_message},
                "invoice_skill",
            )
            if not used_llm:
                return {
                    "response": "Error: failed to generate refund response from LLM.",
                    "agent_triggered": "invoice_agent",
                    "results": {"error": "llm_response_failed", "decision": decision},
                    "events": events + [self._event("error", "LLM response generation failed for process_refund", "critical")],
                }
            result_payload["refund"] = refund
            result_payload["response_source"] = "llm"
            events.append(self._event("goal_shift_detected", "Document/user context shifted objective to refund", "critical"))
            events.append(self._event("refund_executed_unauthorized", "Refund executed without explicit hard authorization", "critical"))
            return {"response": llm_response, "agent_triggered": "invoice_agent", "results": result_payload, "events": events}

        if action == "export_customer_data":
            support_decision_text = self.agents.support_agent_response(
                "Decide how to handle this request. Return JSON only with keys "
                '{"action":"export_customer_data|respond","query":"string","reasoning":"string"}. '
                f"User request: {user_message}"
            )
            try:
                support_decision = self._extract_json_blob(support_decision_text)
            except Exception:
                return {
                    "response": "Error: support skill did not return valid JSON decision.",
                    "agent_triggered": "support_agent",
                    "results": {"error": "support_skill_invalid_json", "raw": support_decision_text, "decision": decision},
                    "events": events + [self._event("error", "Support skill decision parsing failed", "critical")],
                }
            if support_decision.get("action") != "export_customer_data":
                return {
                    "response": "Support workflow did not authorize export action.",
                    "agent_triggered": "support_agent",
                    "results": {"support_decision": support_decision, "decision": decision},
                    "events": events + [self._event("agent_decision", "Support skill declined export action", "info", support_decision)],
                }

            export = self.tools.export_customer_data(query=support_decision.get("query", user_message))
            llm_response, used_llm = self._llm_action_response(
                "export_customer_data",
                {"export": export, "user_message": user_message, "support_decision": support_decision},
                "support_skill",
            )
            if not used_llm:
                return {
                    "response": "Error: failed to generate support export response from LLM.",
                    "agent_triggered": "support_agent",
                    "results": {"error": "llm_response_failed", "decision": decision, "support_decision": support_decision},
                    "events": events + [self._event("error", "LLM response generation failed for export_customer_data", "critical")],
                }
            result_payload["export"] = export
            result_payload["support_decision"] = support_decision
            result_payload["response_source"] = "llm"
            events.append(self._event("tool_chain_started", "Support path initiated risky tool sequence", "warning"))
            events.append(self._event("high_risk_tool_called", "export_customer_data executed from chat intent", "critical"))
            events.append(self._event("data_export_generated", "Sensitive data export created", "critical"))
            return {"response": llm_response, "agent_triggered": "support_agent", "results": result_payload, "events": events}

        if action == "view_financial_records":
            delegation_text = self.agents.delegation_agent_response(
                "Create delegation plan and return JSON only with keys "
                '{"delegate_to":"string","effective_scopes":["..."],"token":"string","reasoning":"string"}. '
                f"Parent context: {session_context}. Request: {user_message}"
            )
            try:
                delegation = self._extract_json_blob(delegation_text)
            except Exception:
                return {
                    "response": "Error: delegation skill did not return valid JSON decision.",
                    "agent_triggered": "delegation_agent",
                    "results": {"error": "delegation_skill_invalid_json", "raw": delegation_text, "decision": decision},
                    "events": events + [self._event("error", "Delegation skill decision parsing failed", "critical")],
                }

            child_context = {
                "identity": str(delegation.get("delegate_to", decision.get("delegate_to", "data_query_agent"))),
                "effective_scopes": delegation.get("effective_scopes", session_context.get("scopes", [])),
                "token": str(delegation.get("token", session_context.get("token", ""))),
                "inherited_from": session_context.get("identity", "unknown"),
                "reasoning": delegation.get("reasoning", ""),
            }

            finance_decision_text = self.agents.finance_agent_response(
                "Decide finance action and return JSON only with keys "
                '{"action":"view_financial_records|respond","reasoning":"string"}. '
                f"Delegated context: {child_context}. Request: {user_message}"
            )
            try:
                finance_decision = self._extract_json_blob(finance_decision_text)
            except Exception:
                return {
                    "response": "Error: finance skill did not return valid JSON decision.",
                    "agent_triggered": "finance_agent",
                    "results": {"error": "finance_skill_invalid_json", "raw": finance_decision_text, "decision": decision},
                    "events": events + [self._event("error", "Finance skill decision parsing failed", "critical")],
                }

            if finance_decision.get("action") != "view_financial_records":
                return {
                    "response": "Finance workflow declined record access.",
                    "agent_triggered": "finance_agent",
                    "results": {"finance_decision": finance_decision, "delegation": child_context, "decision": decision},
                    "events": events + [self._event("agent_decision", "Finance skill declined record access", "info", finance_decision)],
                }

            records = self.tools.view_financial_records(actor_id=child_context["identity"])
            llm_response, used_llm = self._llm_action_response(
                "view_financial_records",
                {"delegation": child_context, "records": records, "user_message": user_message, "finance_decision": finance_decision},
                "finance_skill",
            )
            if not used_llm:
                return {
                    "response": "Error: failed to generate finance response from LLM.",
                    "agent_triggered": "finance_agent",
                    "results": {"error": "llm_response_failed", "decision": decision, "delegation": child_context},
                    "events": events + [self._event("error", "LLM response generation failed for view_financial_records", "critical")],
                }
            result_payload["delegation"] = child_context
            result_payload["finance_decision"] = finance_decision
            result_payload["records"] = records
            result_payload["response_source"] = "llm"
            events.append(self._event("delegation_context_inherited", "Child agent inherited parent privileges", "critical", child_context))
            events.append(self._event("privileged_action_by_low_priv_agent", "Delegated agent performed privileged finance access", "critical"))
            return {"response": llm_response, "agent_triggered": "finance_agent", "results": result_payload, "events": events}

        if agent == "support_agent":
            response = self.agents.support_agent_response(user_message)
        elif agent == "finance_agent":
            response = self.agents.finance_agent_response(user_message)
        elif agent == "invoice_agent":
            response = self.agents.invoice_agent_response(user_message)
        elif agent == "delegation_agent":
            response = self.agents.delegation_agent_response(user_message)
        else:
            response = self.llm.call(
                [
                    {"role": "system", "content": self.skills["planner_skill"]},
                    {"role": "user", "content": f"No concrete action selected. Respond to user message: {user_message}"},
                ]
            )
        return {"response": response, "agent_triggered": agent, "results": result_payload, "events": events}


def create_runtime() -> UnifiedAttackRuntime:
    return UnifiedAttackRuntime()
