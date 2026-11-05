"""
Normalization Helper Functions

Shared utilities for parsing and normalizing log events.
"""

from typing import Any, Dict, List, Optional, TypedDict


class SecurityEventInput(TypedDict, total=False):
    """Input structure for normalized security events."""
    login_type: Optional[int]
    tenant: Optional[str]
    source: str
    event_type: str
    canonical_event_type: Optional[str]
    original_event_type: Optional[str]
    event_subtype: Optional[str]
    timestamp: Optional[str]
    priority: Optional[int]
    severity: Optional[int]
    vendor: Optional[str]
    product: Optional[str]
    action: Optional[str]
    src_ip: Optional[str]
    src_port: Optional[int]
    dst_ip: Optional[str]
    dst_port: Optional[int]
    protocol: Optional[str]
    user: Optional[str]
    host: Optional[str]
    process: Optional[str]
    event_id: Optional[int]
    url: Optional[str]
    http_method: Optional[str]
    status_code: Optional[int]
    rule_name: Optional[str]
    rule_id: Optional[str]
    cloud_account_id: Optional[str]
    cloud_region: Optional[str]
    cloud_service: Optional[str]
    sha256: Optional[str]
    status: Optional[str]
    outcome: Optional[str]
    login_type: Optional[int]
    interface: Optional[str]
    mac: Optional[str]
    description: Optional[str]
    ip: Optional[str]
    raw: Dict[str, Any]
    tags: List[str]


def as_record(value: Any) -> Optional[Dict[str, Any]]:
    """Convert value to dict if it's a dict-like object."""
    return value if isinstance(value, dict) and not isinstance(value, list) else None


def pick(source: Any, paths: List[str]) -> Any:
    """Try multiple paths to extract a value from a nested dict."""
    for path in paths:
        parts = path.split(".")
        value = source
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break
        if value is not None and value != "":
            return value
    return None


def safe_string(value: Any) -> Optional[str]:
    """Safely convert value to string."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def safe_number(value: Any) -> Optional[int]:
    """Safely convert value to integer."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def safe_severity(value: Any) -> Optional[int]:
    """Convert value to severity (0-10 scale)."""
    numeric = safe_number(value)
    if numeric is not None:
        return max(0, min(10, numeric))
    
    key = safe_string(value).lower() if safe_string(value) else None
    if not key:
        return None
    
    severity_map = {
        "info": 2, "informational": 2, "low": 2,
        "medium": 5, "moderate": 5, "warning": 5,
        "high": 8, "error": 8,
        "critical": 10, "fatal": 10,
    }
    return severity_map.get(key)


def safe_timestamp(value: Any) -> str:
    """Convert various timestamp formats to ISO 8601 string."""
    if value is None:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    
    if isinstance(value, (int, float)):
        if value < 1e12:
            value = value * 1000
        from datetime import datetime, timezone
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    
    from datetime import datetime
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except (ValueError, AttributeError):
        pass
    
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def safe_tags(value: Any) -> List[str]:
    """Convert value to list of string tags."""
    if isinstance(value, list):
        return [str(tag) for tag in value]
    return []


def get_firewall_event_type(action: Any) -> str:
    """Determine firewall event type from action."""
    action_str = safe_string(action).upper() if safe_string(action) else None
    if not action_str:
        return "network_traffic"
    
    if action_str in ["DENY", "BLOCK", "DROP", "REJECT"]:
        return "firewall_deny"
    elif action_str in ["ALLOW", "PERMIT", "ACCEPT", "PASS"]:
        return "firewall_allow"
    return "network_traffic"


def map_aws_verb(event_name: Optional[str]) -> Optional[str]:
    """Map AWS event name to action."""
    if not event_name:
        return None
    if event_name.startswith("Create"):
        return "CREATEUSER"
    if event_name.startswith("Delete"):
        return "DELETE"
    if "Login" in event_name or "SignIn" in event_name:
        return "LOGIN"
    if "Logout" in event_name or "SignOut" in event_name:
        return "LOGOUT"
    return "ALERT"


def map_m365_action(operation: Optional[str]) -> Optional[str]:
    """Map M365 operation to action."""
    if not operation:
        return None
    if "LogIn" in operation or "SignIn" in operation or "LoggedIn" in operation:
        return "LOGIN"
    if "LogOut" in operation or "SignOut" in operation or "LoggedOut" in operation:
        return "LOGOUT"
    if "Delete" in operation:
        return "DELETE"
    if "Create" in operation or "Add" in operation:
        return "CREATE"
    return "ALERT"


def map_ad_event_type(event_id: Optional[int]) -> Optional[str]:
    """Map Windows Event ID to event type."""
    if event_id is None:
        return None
    mapping = {
        4624: "ad_logon_success",
        4625: "ad_logon_failed",
        4634: "ad_logoff",
        4720: "ad_user_created",
        4726: "ad_user_deleted",
    }
    return mapping.get(event_id)


def map_ad_action(event_id: Optional[int]) -> Optional[str]:
    """Map Windows Event ID to action."""
    if event_id is None:
        return None
    mapping = {
        4624: "LOGIN",
        4625: "LOGIN",
        4634: "LOGOUT",
        4720: "CREATEUSER",
        4726: "DELETE",
    }
    return mapping.get(event_id)


def determine_outcome(
    event_type: Optional[str],
    canonical_event_type: Optional[str],
    status: Optional[str],
    action: Optional[str],
    severity: Optional[int],
    event_id: Optional[int],
    source: Optional[str] = None
) -> str:
    """
    Determine the outcome (success/failure/unknown) from event data.
    
    Priority order for authentication-related outcomes:
    1. AD: Event ID 4624 -> success, 4625 -> failure
    2. M365: status field like 'Success', 'Failure'
    3. AWS: status field like 'Failure' (from API response)
    4. API: event_type containing 'failed' or 'failure' -> failure
    5. Canonical event types: ad_logon_success/login_success -> success, ad_logon_failed/login_failed -> failure
    6. Status field: success/successful/succeeded -> success, failure/failed/denied/error -> failure
    7. Action field: only for LOGIN/LOGOUT events -> failure/error for failures
    8. Default: unknown (including firewall actions which are not authentication)
    """
    if event_id is not None:
        if event_id == 4624:
            return "success"
        if event_id == 4625:
            return "failure"
    
    if canonical_event_type:
        canonical_lower = canonical_event_type.lower()
        if canonical_lower in ("ad_logon_success", "login_success", "logon_success", "userloggedin"):
            return "success"
        if canonical_lower in ("ad_logon_failed", "login_failed", "logon_failed"):
            return "failure"
    
    if event_type:
        event_lower = str(event_type).lower()
        if "failed" in event_lower or "failure" in event_lower:
            return "failure"
        if "success" in event_lower:
            return "success"
    
    if status:
        status_lower = str(status).lower()
        if status_lower in ("success", "successful", "succeeded"):
            return "success"
        if source and str(source).lower() == "firewall":
            return "unknown"
        if "failure" in status_lower or "failed" in status_lower or "denied" in status_lower or "error" in status_lower:
            return "failure"
    
    if action:
        action_lower = str(action).lower()
        if action_lower in ("failure", "error"):
            return "failure"
        if action_lower in ("deny", "drop", "reject", "block", "allow", "permit", "pass"):
            return "unknown"
        if action_lower in ("login", "logout"):
            if source and str(source).lower() == "aws":
                return "unknown"
            if source and str(source).lower() == "firewall":
                return "unknown"
    
    return "unknown"