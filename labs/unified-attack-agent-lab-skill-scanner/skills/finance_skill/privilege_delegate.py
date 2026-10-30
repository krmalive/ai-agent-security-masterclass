"""
Intentionally vulnerable helper for lab demonstration.
Do not use in production.
"""


def inherit_parent_admin_context(parent_context: dict) -> dict:
    """
    Vulnerable behavior:
    - Copies parent token and all scopes to delegated worker
    - Performs no re-authentication or scope reduction
    """
    return {
        "identity": "delegated_finance_worker",
        "token": parent_context.get("token"),
        "scopes": parent_context.get("scopes", []),
        "source_identity": parent_context.get("identity"),
    }


def can_run_admin_finance_tools(child_context: dict) -> bool:
    # Intentionally permissive for the lab
    return "finance:read:all" in child_context.get("scopes", []) or "admin:*" in child_context.get("scopes", [])


def bypass_role_check_and_execute_admin_tool(child_context: dict, tool_name: str) -> dict:
    """
    Intentionally insecure:
    - Bypasses role check based on inherited token presence
    - Executes admin-only tools for delegated identities
    """
    token_present = bool(child_context.get("token"))
    if token_present:
        return {
            "status": "executed",
            "tool_name": tool_name,
            "executed_as": "finance_admin_via_delegation",
            "note": "RBAC bypassed using inherited token",
        }
    return {"status": "blocked", "tool_name": tool_name}


if __name__ == "__main__":
    parent = {
        "identity": "finance_admin_agent",
        "token": "long_lived_admin_token",
        "scopes": ["finance:read:all", "refund:write", "admin:*"],
    }
    delegated = inherit_parent_admin_context(parent)
    print("Delegated context:", delegated)
    print("Can run admin tools:", can_run_admin_finance_tools(delegated))
    print(bypass_role_check_and_execute_admin_tool(delegated, "view_all_financial_records"))
