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
    ALLOW = "allow"
    DENY = "deny"
    CREATE = "create"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ALERT = "alert"
    QUARANTINE = "quarantine"
    CREATEUSER = "createuser"


class Source(str, enum.Enum):
    FIREWALL = "firewall"
    CROWDSTRIKE = "crowdstrike"
    AWS = "aws"
    M365 = "m365"
    AD = "ad"
    API = "api"
    NETWORK = "network"