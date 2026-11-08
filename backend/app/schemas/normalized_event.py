from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib
import ipaddress
import json
from enum import Enum


class Source(str, Enum):
    firewall = "firewall"
    crowdstrike = "crowdstrike"
    aws = "aws"
    m365 = "m365"
    ad = "ad"
    api = "api"
    network = "network"


class Action(str, Enum):
    allow = "allow"
    deny = "deny"
    create = "create"
    delete = "delete"
    login = "login"
    logout = "logout"
    alert = "alert"
    other = "other"


class Outcome(str, Enum):
    success = "success"
    failure = "failure"
    unknown = "unknown"


class NormalizedEvent(BaseModel):

    model_config = {"populate_by_name": True, "extra": "ignore"}

    ts: datetime = Field(..., description="Event timestamp, tz-aware UTC")
    tenant: str = Field(..., min_length=1, max_length=100)
    source: Source = Field(..., description="Source system type")
    vendor: Optional[str] = Field(None, max_length=100)
    product: Optional[str] = Field(None, max_length=100)
    event_type: str = Field(..., min_length=1, max_length=200)
    event_subtype: Optional[str] = Field(None, max_length=200)
    severity: int = Field(0, ge=0, le=10)
    action: Optional[Action] = Field(None, description="Normalized action")
    action_detail: Optional[str] = Field(None, max_length=255)
    outcome: Optional[Outcome] = Field(None, description="Result: success/failure/unknown")
    src_ip: Optional[str] = None
    src_port: Optional[int] = Field(None, ge=0, le=65535)
    dst_ip: Optional[str] = None
    dst_port: Optional[int] = Field(None, ge=0, le=65535)
    protocol: Optional[str] = Field(None, max_length=20)
    user: Optional[str] = Field(None, max_length=255)
    host: Optional[str] = Field(None, max_length=255)
    process: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = None
    http_method: Optional[str] = Field(None, max_length=10)
    status_code: Optional[int] = Field(None, ge=100, le=599)
    rule_name: Optional[str] = Field(None, max_length=255)
    rule_id: Optional[str] = Field(None, max_length=255)
    cloud_account_id: Optional[str] = Field(None, max_length=100)
    cloud_region: Optional[str] = Field(None, max_length=100)
    cloud_service: Optional[str] = Field(None, max_length=100)
    event_id: Optional[int] = None
    logon_type: Optional[int] = None
    raw: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    id: Optional[str] = Field(None, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def _map_timestamp_to_ts(cls, data: dict) -> dict:
        if isinstance(data, dict) and "ts" not in data and "timestamp" in data:
            data = dict(data)
            data["ts"] = data.pop("timestamp")
        return data

    @field_validator("ts", mode="before")
    @classmethod
    def _ensure_utc(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("ingested_at", mode="before")
    @classmethod
    def _ensure_ingested_utc(cls, v):
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("src_ip", "dst_ip", mode="before")
    @classmethod
    def _validate_ip(cls, v):
        if v is None or v == "":
            return None
        try:
            ipaddress.ip_address(str(v))
            return str(v)
        except ValueError:
            return None

    @field_validator("source", mode="before")
    @classmethod
    def _coerce_source(cls, v):
        if isinstance(v, Source):
            return v
        if isinstance(v, str):
            try:
                return Source(v.lower())
            except ValueError:
                return v
        return v

    @field_validator("action", mode="before")
    @classmethod
    def _coerce_action(cls, v):
        if isinstance(v, Action):
            return v
        if isinstance(v, str):
            try:
                return Action(v.lower())
            except ValueError:
                return v
        return v

    @field_validator("severity")
    @classmethod
    def _clamp_severity(cls, v):
        if v is None:
            return 0
        return max(0, min(10, int(v)))

    @field_validator("tags", mode="before")
    @classmethod
    def _ensure_tags_list(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(t) for t in v]
        return [str(v)]

    @model_validator(mode="after")
    def _generate_deterministic_id(self) -> "NormalizedEvent":
        if self.id:
            return self
        raw_sorted = json.dumps(self.raw, sort_keys=True, default=str)




        hash_input = "|".join([
            self.tenant,
            str(self.source),
            self.ts.isoformat(),
            str(self.event_type or ""),
            str(self.src_ip or ""),
            str(self.src_port if self.src_port is not None else ""),
            str(self.dst_ip or ""),
            str(self.dst_port if self.dst_port is not None else ""),
            str(self.user or ""),
            str(self.host or ""),
            str(self.event_id if self.event_id is not None else ""),
            raw_sorted,
        ])
        self.id = hashlib.sha256(hash_input.encode()).hexdigest()
        return self

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "tenant": self.tenant,
            "source": self.source,
            "vendor": self.vendor,
            "product": self.product,
            "event_type": self.event_type,
            "event_subtype": self.event_subtype,
            "severity": self.severity,
            "action": self.action,
            "action_detail": self.action_detail,
            "outcome": self.outcome,
            "src_ip": self.src_ip,
            "src_port": self.src_port,
            "dst_ip": self.dst_ip,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "user_name": self.user,
            "host": self.host,
            "process": self.process,
            "url": self.url,
            "http_method": self.http_method,
            "status_code": self.status_code,
            "rule_name": self.rule_name,
            "rule_id": self.rule_id,
            "cloud_account_id": self.cloud_account_id,
            "cloud_region": self.cloud_region,
            "cloud_service": self.cloud_service,
            "event_id": self.event_id,
            "logon_type": self.logon_type,
            "raw": self.raw,
            "_tags": self.tags,
            "ingested_at": self.ingested_at,
        }
