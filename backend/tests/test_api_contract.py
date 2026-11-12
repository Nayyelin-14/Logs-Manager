"""Lightweight frontend <-> backend contract guard.

The SPA and the FastAPI schema must agree on the routes and query parameters
they exchange. This module reads ``app.openapi()`` only - it never touches the
database or Redis - so drift fails fast (well under a second) instead of
showing up as a blank screen in manual testing.
"""

from __future__ import annotations

from app.main import app

SCHEMA = app.openapi()

# Every route the React client calls (see frontend/src/api).
FRONTEND_CALLS: list[tuple[str, str]] = [
    ("post", "/api/auth/login"),
    ("post", "/api/auth/logout"),
    ("get", "/api/auth/auth-check"),
    ("get", "/api/events"),
    ("get", "/api/events/{event_id}"),
    ("delete", "/api/delete-log/{log_id}"),
    ("get", "/api/get-alerts"),
    ("patch", "/api/alerts/{alert_id}"),
    ("post", "/api/alerts/test-notification"),
    ("get", "/api/get-rules"),
    ("post", "/api/create-alertRule"),
    ("put", "/api/update-rule/{rule_id}"),
    ("patch", "/api/rules/{rule_id}/enabled"),
    ("delete", "/api/delete-rule/{rule_id}"),
    ("get", "/api/get-users"),
    ("post", "/api/create-user"),
    ("put", "/api/update-user"),
    ("delete", "/api/delete-user/{user_id}"),
    ("get", "/api/get-all-data"),
    ("get", "/api/dashboard"),
    ("get", "/api/stats/top"),
    ("get", "/api/stats/timeline"),
    ("get", "/api/stats/summary"),
    ("post", "/api/ingest"),
    ("post", "/api/ingest/ui"),
]

# Query parameters the client actually sends for each call.
FRONTEND_QUERY_PARAMS: dict[tuple[str, str], set[str]] = {
    ("get", "/api/events"): {
        "tenant",
        "source",
        "event_type",
        "severity",
        "date",
        "user",
        "src_ip",
        "from",
        "to",
        "q",
        "limit",
        "cursor",
        "sort_by",
        "sort_order",
    },
    ("get", "/api/get-alerts"): {
        "tenant",
        "status",
        "severity",
        "search",
        "limit",
        "cursor",
    },
    ("get", "/api/get-rules"): {"tenant", "search", "limit", "cursor"},
    ("get", "/api/get-users"): {
        "tenant",
        "search",
        "role",
        "status",
        "date",
        "limit",
        "cursor",
    },
    ("get", "/api/get-all-data"): {"tenant"},
    ("get", "/api/dashboard"): {"tenant", "range", "source"},
    ("get", "/api/stats/top"): {"field", "n", "tenant", "source", "from", "to"},
    ("get", "/api/stats/timeline"): {
        "interval",
        "tenant",
        "source",
        "from",
        "to",
    },
    ("get", "/api/stats/summary"): {"tenant", "source"},
    ("patch", "/api/rules/{rule_id}/enabled"): {"enabled"},
}


def _operation(method: str, path: str) -> dict:
    return SCHEMA["paths"][path][method]


def _parameter_names(method: str, path: str) -> set[str]:
    return {
        parameter["name"] for parameter in _operation(method, path).get("parameters", [])
    }


def test_every_frontend_route_is_declared() -> None:
    missing = [
        f"{method.upper()} {path}"
        for method, path in FRONTEND_CALLS
        if path not in SCHEMA["paths"] or method not in SCHEMA["paths"][path]
    ]
    assert not missing, f"Frontend calls missing from OpenAPI: {missing}"


def test_frontend_query_parameters_are_declared() -> None:
    problems: list[str] = []
    for (method, path), expected in FRONTEND_QUERY_PARAMS.items():
        declared = _parameter_names(method, path)
        missing = expected - declared
        if missing:
            problems.append(f"{method.upper()} {path} missing {sorted(missing)}")
    assert not problems, "\n".join(problems)


def test_rule_toggle_uses_query_parameter_contract() -> None:
    parameters = _operation("patch", "/api/rules/{rule_id}/enabled")["parameters"]
    enabled = next(
        parameter for parameter in parameters if parameter["name"] == "enabled"
    )
    assert enabled["in"] == "query"
    assert enabled.get("required") is True


def _schema_types(parameter: dict) -> set[str]:
    schema = parameter.get("schema", {})
    if "type" in schema:
        return {str(schema["type"])}
    return {
        str(option["type"])
        for option in schema.get("anyOf", [])
        if "type" in option
    }


def test_user_cursor_is_an_integer() -> None:
    parameters = _operation("get", "/api/get-users")["parameters"]
    cursor = next(parameter for parameter in parameters if parameter["name"] == "cursor")
    assert cursor["in"] == "query"
    # The client treats the cursor as a numeric user id and re-sends it.
    types = _schema_types(cursor)
    assert "integer" in types and "string" not in types
