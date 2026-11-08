#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RENDER = ROOT / "render.yaml"
VERCEL = ROOT / "frontend" / "vercel.json"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-saas.yml"
SECRET_KEYS = {
    "DATABASE_URL",
    "REDIS_URL",
    "INGEST_API_KEY",
    "ACCESS_TOKEN_SECRET",
    "REFRESH_TOKEN_SECRET",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)


def check_render() -> bool:
    if not RENDER.exists():
        fail("render.yaml is missing")
        return False
    data = yaml.safe_load(RENDER.read_text())
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, list) or not services:
        fail("render.yaml has no services")
        return False
    web = [s for s in services if s.get("type") == "web"]
    if len(web) != 1:
        fail(f"render.yaml must define exactly one web service, found {len(web)}")
        return False
    other = [s for s in services if s.get("type") != "web"]
    if other:
        fail("render.yaml must not define paid worker or static services")
        return False
    service = web[0]
    if service.get("plan") != "free":
        fail("render.yaml web service plan must be free")
        return False
    if service.get("runtime") != "docker":
        fail("render.yaml web service runtime must be docker")
        return False
    if not service.get("dockerfilePath", "").endswith("Dockerfile"):
        fail("render.yaml web service is missing dockerfilePath")
        return False
    if service.get("healthCheckPath") != "/ready":
        fail("render.yaml healthCheckPath must be /ready")
        return False
    env = {item.get("key"): item for item in service.get("envVars", [])}
    required = {
        "DATABASE_URL": None,
        "REDIS_URL": None,
        "ACCESS_TOKEN_SECRET": None,
        "REFRESH_TOKEN_SECRET": None,
        "WORKER_EMBEDDED": "true",
        "SYSLOG_ENABLED": "false",
        "COOKIE_SECURE": "true",
        "APP_ENV": "production",
    }
    for key, expected in required.items():
        if key not in env:
            fail(f"render.yaml is missing env var {key}")
            return False
        if expected is not None and str(env[key].get("value")) != expected:
            fail(f"render.yaml env var {key} must be {expected}")
            return False
    for key in SECRET_KEYS:
        item = env.get(key)
        if item and "value" in item and "generateValue" not in item:
            fail(f"render.yaml must not hardcode {key}")
            return False
    return True


def check_vercel() -> bool:
    if not VERCEL.exists():
        fail("frontend/vercel.json is missing")
        return False
    data = json.loads(VERCEL.read_text())
    rewrites = data.get("rewrites")
    if not isinstance(rewrites, list) or len(rewrites) < 2:
        fail("frontend/vercel.json needs an API rewrite and an SPA fallback")
        return False
    api = rewrites[0]
    if api.get("source") != "/api/:path*":
        fail("frontend/vercel.json first rewrite must proxy /api/:path*")
        return False
    if not str(api.get("destination", "")).endswith("/api/:path*"):
        fail("frontend/vercel.json API rewrite destination must end with /api/:path*")
        return False
    if "onrender.com" not in str(api.get("destination", "")):
        fail("frontend/vercel.json API rewrite must target the Render backend")
        return False
    if rewrites[-1] != {"source": "/(.*)", "destination": "/index.html"}:
        fail("frontend/vercel.json must end with the SPA fallback rewrite")
        return False
    return True


def check_deploy_workflow() -> bool:
    if not DEPLOY_WORKFLOW.exists():
        fail(".github/workflows/deploy-saas.yml is missing")
        return False
    text = DEPLOY_WORKFLOW.read_text()
    required = [
        "workflow_run",
        "RENDER_DEPLOY_HOOK_URL",
        "VERCEL_TOKEN",
        "smoke_saas.sh",
    ]
    for token in required:
        if token not in text:
            fail(f".github/workflows/deploy-saas.yml is missing {token}")
            return False
    return True


def main() -> int:
    ok = check_render()
    ok = check_vercel() and ok
    ok = check_deploy_workflow() and ok
    if ok:
        print("PASS: SaaS configuration is valid")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
