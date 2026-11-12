from enum import Enum
from typing import Dict, List, Optional, Set
from app.models.enums import Source
class CanonicalEventMapping:
    def __init__(self, canonical: str, aliases: List[str], sources: List[Source] = None, description: str = ""):
        self.canonical = canonical
        self.aliases = aliases
        self.sources = sources or []
        self.description = description


CANONICAL_EVENT_TAXONOMY: Dict[str, CanonicalEventMapping] = {
    "login_success": CanonicalEventMapping(
        canonical="login_success",
        aliases=[
            "ad_logon_success",
            "login_success",
            "logon_success",
            "signin_success",
            "user_logged_in",
            "UserLoggedIn",
            "UserLoginSuccess",
        ],
        sources=[Source.AD, Source.M365, Source.API],
        description="Successful user login",
    ),
    "login_failed": CanonicalEventMapping(
        canonical="login_failed",
        aliases=[
            "ad_logon_failed",
            "login_failed",
            "logon_failed",
            "signin_failed",
            "failed_login",
            "failed_logon",
            "login_failure",
            "logon_failure",
            "UserLoggedIn",
            "MailboxLogin",
        ],
        sources=[Source.AD, Source.M365, Source.API, Source.CROWDSTRIKE],
        description="Failed login attempt",
    ),
    "logout": CanonicalEventMapping(
        canonical="logout",
        aliases=[
            "ad_logoff",
            "logout",
            "logoff",
            "signout",
            "user_logged_out",
            "UserLoggedOut",
        ],
        sources=[Source.AD, Source.M365, Source.API],
        description="User logout",
    ),
    "user_created": CanonicalEventMapping(
        canonical="user_created",
        aliases=[
            "CreateUser",
            "ad_user_created",
            "user_created",
            "user_added",
            "user_provisioned",
        ],
        sources=[Source.AWS, Source.AD, Source.API, Source.M365],
        description="User account created",
    ),
    "user_deleted": CanonicalEventMapping(
        canonical="user_deleted",
        aliases=[
            "DeleteUser",
            "ad_user_deleted",
            "user_deleted",
            "user_removed",
        ],
        sources=[Source.AWS, Source.AD, Source.API],
        description="User account deleted",
    ),
    "user_modified": CanonicalEventMapping(
        canonical="user_modified",
        aliases=[
            "ModifyUser",
            "ad_user_modified",
            "user_modified",
            "user_updated",
        ],
        sources=[Source.AWS, Source.AD, Source.API],
        description="User account modified",
    ),
    "privilege_escalation": CanonicalEventMapping(
        canonical="privilege_escalation",
        aliases=[
            "AddUserToGroup",
            "AddUserToAdminGroup",
            "ad_privilege_escalation",
            "privilege_escalation",
            "privilege_elevation",
        ],
        sources=[Source.AD, Source.AWS, Source.M365],
        description="Privilege escalation or group membership change",
    ),
    "malware_detected": CanonicalEventMapping(
        canonical="malware_detected",
        aliases=[
            "MalwareDetected",
            "malware_detected",
            "MALWAREDETECTED",
            "malware",
            "virus_detected",
            "threat_detected",
            "MalwareDetected",
        ],
        sources=[Source.CROWDSTRIKE, Source.API],
        description="Malware or threat detected",
    ),
    "threat_detected": CanonicalEventMapping(
        canonical="threat_detected",
        aliases=[
            "threat_detected",
            "ThreatDetected",
            "detection",
            "alert",
        ],
        sources=[Source.CROWDSTRIKE, Source.API],
        description="Generic threat detection",
    ),
    "process_blocked": CanonicalEventMapping(
        canonical="process_blocked",
        aliases=[
            "process_blocked",
            "ProcessBlocked",
            "exploit_blocked",
            "execution_blocked",
        ],
        sources=[Source.CROWDSTRIKE],
        description="Process execution blocked",
    ),
    "firewall_deny": CanonicalEventMapping(
        canonical="firewall_deny",
        aliases=[
            "deny",
            "denied",
            "block",
            "blocked",
            "drop",
            "rejected",
            "firewall_deny",
            "firewall_block",
            "DENY",
            "BLOCK",
            "DROP",
            "REJECT",
        ],
        sources=[Source.FIREWALL, Source.NETWORK],
        description="Firewall denied/blocked connection",
    ),
    "firewall_allow": CanonicalEventMapping(
        canonical="firewall_allow",
        aliases=[
            "allow",
            "permit",
            "accept",
            "pass",
            "firewall_allow",
            "firewall_permit",
            "ALLOW",
            "PERMIT",
            "ACCEPT",
            "PASS",
        ],
        sources=[Source.FIREWALL, Source.NETWORK],
        description="Firewall allowed connection",
    ),
    "network_connection": CanonicalEventMapping(
        canonical="network_connection",
        aliases=[
            "connection",
            "network_connection",
            "traffic",
            "flow",
        ],
        sources=[Source.FIREWALL, Source.NETWORK],
        description="Network connection observed",
    ),
    "link_down": CanonicalEventMapping(
        canonical="link_down",
        aliases=[
            "link_down",
            "link_down",
            "interface_down",
            "port_down",
            "interface_down",
        ],
        sources=[Source.NETWORK],
        description="Network link/interface down",
    ),
    "link_up": CanonicalEventMapping(
        canonical="link_up",
        aliases=[
            "link_up",
            "interface_up",
            "link_up",
            "port_up",
        ],
        sources=[Source.NETWORK],
        description="Network link/interface up",
    ),
    "aws_create_user": CanonicalEventMapping(
        canonical="aws_create_user",
        aliases=["CreateUser"],
        sources=[Source.AWS],
        description="AWS IAM user created",
    ),
    "aws_delete_user": CanonicalEventMapping(
        canonical="aws_delete_user",
        aliases=["DeleteUser"],
        sources=[Source.AWS],
        description="AWS IAM user deleted",
    ),
    "aws_console_login": CanonicalEventMapping(
        canonical="aws_console_login",
        aliases=["ConsoleLogin"],
        sources=[Source.AWS],
        description="AWS console login",
    ),
    "aws_api_call": CanonicalEventMapping(
        canonical="aws_api_call",
        aliases=["aws_api_call", "api_call"],
        sources=[Source.AWS],
        description="Generic AWS API call",
    ),
    "m365_user_login": CanonicalEventMapping(
        canonical="m365_user_login",
        aliases=["UserLoggedIn", "MailboxLogin", "UserLogin"],
        sources=[Source.M365],
        description="Microsoft 365 user login",
    ),
    "m365_mailbox_login": CanonicalEventMapping(
        canonical="m365_mailbox_login",
        aliases=["MailboxLogin"],
        sources=[Source.M365],
        description="Microsoft 365 mailbox login",
    ),
    "m365_admin_action": CanonicalEventMapping(
        canonical="m365_admin_action",
        aliases=["AddMemberToGroup", "RemoveMemberFromGroup", "Set-Mailbox", "New-Mailbox"],
        sources=[Source.M365],
        description="Microsoft 365 admin action",
    ),
    "ad_logon_success": CanonicalEventMapping(
        canonical="ad_logon_success",
        aliases=["ad_logon_success", "4624"],
        sources=[Source.AD],
        description="Active Directory successful logon (Event ID 4624)",
    ),
    "ad_logon_failed": CanonicalEventMapping(
        canonical="ad_logon_failed",
        aliases=["ad_logon_failed", "4625", "ad_logon_failed"],
        sources=[Source.AD],
        description="Active Directory failed logon (Event ID 4625)",
    ),
    "ad_logoff": CanonicalEventMapping(
        canonical="ad_logoff",
        aliases=["ad_logoff", "4634"],
        sources=[Source.AD],
        description="Active Directory logoff (Event ID 4634)",
    ),
    "ad_user_created": CanonicalEventMapping(
        canonical="ad_user_created",
        aliases=["ad_user_created", "4720"],
        sources=[Source.AD],
        description="Active Directory user created (Event ID 4720)",
    ),
    "ad_user_deleted": CanonicalEventMapping(
        canonical="ad_user_deleted",
        aliases=["ad_user_deleted", "4726"],
        sources=[Source.AD],
        description="Active Directory user deleted (Event ID 4726)",
    ),
    "unknown": CanonicalEventMapping(
        canonical="unknown",
        aliases=["unknown", "unknown_event", "other"],
        sources=[],
        description="Unknown or unclassified event",
    ),
}
_CANONICAL_EVENT_MAP: Dict[str, str] = {}
for canonical, mapping in CANONICAL_EVENT_TAXONOMY.items():
    _CANONICAL_EVENT_MAP[canonical.lower()] = mapping.canonical


    for alias in mapping.aliases:
        _CANONICAL_EVENT_MAP[alias.lower()] = mapping.canonical

def resolve_canonical_event_type(
    event_type: Optional[str],
    source: Optional[Source] = None
) -> str:
    if not event_type:
        return "unknown"

    normalized = event_type.lower().strip()
    canonical = _CANONICAL_EVENT_MAP.get(normalized)
    if canonical:
        return canonical

    if source:
        for mapping in CANONICAL_EVENT_TAXONOMY.values():
            if mapping.sources and source in mapping.sources:
                for alias in mapping.aliases:
                    if alias.lower() == normalized:
                        return mapping.canonical
    return normalized.replace(" ", "_").replace("-", "_").replace(".", "_")

def get_aliases_for_canonical(canonical: str) -> List[str]:
    return CANONICAL_EVENT_TAXONOMY.get(canonical, CanonicalEventMapping("", [])).aliases

def is_known_event_type(event_type: str, source: Optional[Source] = None) -> bool:
    normalized = event_type.lower().strip()
    if normalized in _CANONICAL_EVENT_MAP:
        return True
    if source:
        for mapping in CANONICAL_EVENT_TAXONOMY.values():
            if mapping.sources and source in mapping.sources:
                for alias in mapping.aliases:
                    if alias.lower() == normalized:
                        return True
    return False
def get_canonical_events_for_source(source: Source) -> List[str]:

    events = set()
    for canonical, mapping in CANONICAL_EVENT_TAXONOMY.items():
        if not mapping.sources or source in mapping.sources:
            events.add(canonical)
    return list(events)

def get_canonical_event_description(canonical: str) -> Optional[str]:
    return CANONICAL_EVENT_TAXONOMY.get(canonical, CanonicalEventMapping("", [])).description
def infer_source_from_event(event: dict) -> Source:

    if isinstance(event, dict):
        raw = event.get("raw")
        payload = {**raw, **event} if isinstance(raw, dict) else event
    else:
        raw = getattr(event, "raw", None)
        payload = raw if isinstance(raw, dict) else {}
    if any(key in payload for key in [
        "eventSource", "event_source",
        "recipientAccountId", "recipient_account_id",
        "awsRegion", "aws_region",
        "userIdentity", "user_identity",
        "eventVersion", "event_version",
    ]):
        return Source.AWS
    if any(key in payload for key in [
        "DetectName", "detect_name",
        "ComputerName", "computer_name",
        "SHA256String", "sha256",
        "event_simpleName", "event_simple_name",
        "ImageFileName", "file_name",
    ]):
        return Source.CROWDSTRIKE
    if any(key in payload for key in [
        "EventID", "event_id",
        "TargetUserName", "target_user_name",
        "SubjectUserName", "subject_user_name",
        "LogonType", "logon_type",
    ]):
        return Source.AD
    if any(key in payload for key in [
        "Operation", "operation",
        "Workload", "workload",
        "RecordType", "record_type",
        "UserPrincipalName", "user_principal_name",
        "ClientIP", "client_ip",
    ]):
        return Source.M365
    # Firewall/NGW keys: a security-appliance log carries an action plus
    # endpoints (src/dst) and a policy. These take precedence so a firewall
    # line is never reclassified as network.
    _FIREWALL_KEYS = {
        "action", "Action", "act", "disposition",
        "src", "srcIp", "src_ip", "sourceIp", "source_ip", "saddr",
        "dst", "dstIp", "dst_ip", "destinationIp", "destination_ip", "daddr",
        "spt", "srcPort", "src_port", "source_port",
        "dpt", "dstPort", "dst_port", "destination_port",
        "proto", "protocol", "network.protocol",
        "policy", "vendor", "product",
    }
    # Network/router keys: interface, MAC and reason/link events identify a
    # router or switch rather than a firewall. Only consulted when no
    # firewall key is present.
    _ROUTER_KEYS = {
        "if", "interface", "interfaceName", "interface_name",
        "mac", "macAddress", "mac_address",
        "reason",
    }
    if any(key in payload for key in _FIREWALL_KEYS):
        return Source.FIREWALL
    if any(key in payload for key in _ROUTER_KEYS) or str(
        payload.get("event", "")
    ).startswith("link-"):
        return Source.NETWORK

    return Source.API
