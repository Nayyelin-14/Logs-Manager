import enum
from sqlalchemy import Enum as SQLEnum


class Role(str, enum.Enum):
    VIEWER = "VIEWER"
    ADMIN = "ADMIN"


class Status(str, enum.Enum):
    FREEZE = "FREEZE"
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"


class Action(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CREATE = "CREATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    ALERT = "ALERT"
    QUARANTINE = "QUARANTINE"
    CREATEUSER = "CREATEUSER"


class Source(str, enum.Enum):
    FIREWALL = "FIREWALL"
    CROWDSTRIKE = "CROWDSTRIKE"
    AWS = "AWS"
    M365 = "M365"
    AD = "AD"
    API = "API"
    NETWORK = "NETWORK"