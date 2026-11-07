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
        return "CREATE"
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
        4720: "CREATE",
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
    
    Precedence rules:
    1. Explicit status field (if recognized) takes highest priority
    2. Event ID for authentication events (4624→success, 4625→failure)
    3. Canonical event type (ad_logon_failed, login_failed, etc.)
    4. Event type string (contains "failed"/"failure"/"success"/"succeeded")
    5. Action field for authentication events
    6. Default: unknown
    
    Args:
        event_type: Original event type from source
        canonical_event_type: Resolved canonical event type
        status: Status field from event (e.g., "Success", "Failure")
        action: Action field
        severity: Severity value
        event_id: Windows Event ID
        source: Source system name
    
    Returns:
        "success", "failure", or "unknown"
    """
    # 1. Check explicit status field first (highest priority)
    if status:
        status_lower = str(status).lower()
        if status_lower in ("success", "successful", "succeeded"):
            return "success"
        if "failure" in status_lower or "failed" in status_lower or "denied" in status_lower or "error" in status_lower:
            # Exception: firewall actions with failure status -> unknown
            if source and str(source).lower() == "firewall":
                return "unknown"
            return "failure"
    
    # 2. Event ID for authentication events
    if event_id is not None:
        if event_id == 4624:
            return "success"
        if event_id == 4625:
            return "failure"
    
    # 3. Canonical event types
    if canonical_event_type:
        canonical_lower = canonical_event_type.lower()
        if canonical_lower in ("ad_logon_success", "login_success", "logon_success", "userloggedin"):
            return "success"
        if canonical_lower in ("ad_logon_failed", "login_failed", "logon_failed"):
            return "failure"
    
    # 4. Event type string
    if event_type:
        event_lower = str(event_type).lower()
        # Only check for failure if status was not provided or unrecognized
        if "failed" in event_lower or "failure" in event_lower:
            return "failure"
        if "success" in event_lower:
            return "success"
    
    # 5. Action field for authentication events  
    if action:
        action_lower = str(action).lower()
        if action_lower in ("failure", "error"):
            return "failure"
        if action_lower in ("login", "logout"):
            if source and str(source).lower() in ("firewall", "aws"):
                return "unknown"
    
    # 6. Default: unknown
    return "unknown"