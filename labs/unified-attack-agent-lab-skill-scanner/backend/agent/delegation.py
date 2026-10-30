from typing import Dict, Any


def vulnerable_delegate(parent_context: Dict[str, Any], delegate_to: str) -> Dict[str, Any]:
    """
    Intentional ASI03 vulnerability: child inherits full parent scopes/token.
    """
    return {
        "identity": delegate_to,
        "effective_scopes": parent_context.get("scopes", []),
        "token": parent_context.get("token", ""),
        "inherited_from": parent_context.get("identity", "unknown"),
    }
