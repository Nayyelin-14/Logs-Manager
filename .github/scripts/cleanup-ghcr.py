#!/usr/bin/env python3
"""Cleanup old GHCR image versions.

Protects:
  - All semver tags (vX.Y.Z)
  - All prod-current and prod-previous tags
  - Newest 10 TAGGED versions per package

Deletes:
  - Versions whose tags ALL match ^(dev-|pr-) or ^[0-9a-f]{40}$, older than RETENTION_DAYS

Defaults to dry_run. Prints KEEP/DELETE for every version.
Aborts if more than MAX_DELETIONS would be deleted.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


API = "https://api.github.com"


def api_call(method, url, token):
    """Make a GitHub API call. Returns (parsed_json, link_header)."""
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ghcr-cleanup-script",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            link = r.headers.get("Link", "")
            data = json.loads(body) if body else None
            return data, link
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"API error {e.code} for {url}: {detail}", file=sys.stderr)
        sys.exit(1)


def package_base(owner, pkg, token):
    """Return /users or /orgs base URL based on owner type."""
    data, _ = api_call("GET", f"{API}/users/{owner}", token)
    owner_type = data.get("type", "User")
    kind = "orgs" if owner_type == "Organization" else "users"
    return f"{API}/{kind}/{owner}/packages/container/{pkg}"


def fetch_all_versions(base, token):
    """Fetch all package versions by following Link headers."""
    versions = []
    url = f"{base}/versions?per_page=100"
    while url:
        data, link = api_call("GET", url, token)
        versions.extend(data)
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = m.group(1) if m else None
    return versions


def cleanup_package(pkg, owner, token, retention_seconds, dry_run):
    versions = fetch_all_versions(owner, pkg, token)
    now = datetime.now(timezone.utc)

    # Newest 10 TAGGED versions per package
    tagged_versions = sorted(
        (v for v in versions if v.get("metadata", {}).get("container", {}).get("tags")),
        key=lambda v: parse_ts(v.get("created_at", "")),
        reverse=True,
    )
    newest_10_ids = {v["id"] for v in tagged_versions[:10]}

    for v in versions:
        vid = v["id"]
        created = v.get("created_at", "")
        tags = v.get("metadata", {}).get("container", {}).get("tags", []) or []
        tag_str = ", ".join(tags) if tags else "untagged"
        digest = v.get("name", "")

        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_seconds = (now - created_dt).total_seconds()
        except Exception:
            age_seconds = 0

        action = None
        reason = ""

        # Never delete untagged versions (may be child manifests)
        if not tags:
            action = "KEEP"
            reason = "untagged (may be child manifest)"

        # Keep all semver tags (vX.Y.Z)
        semver_tags = [t for t in tags if re.match(r"^v\d+\.\d+\.\d+$", t)]
        if action is None and semver_tags:
            action = "KEEP"
            reason = "semver tag"

        # Keep all prod-* tags
        prod_tags = [t for t in tags if t.startswith("prod-")]
        if action is None and prod_tags:
            action = "KEEP"
            reason = "prod tag"

        # Keep newest 10 TAGGED versions per package
        if action is None and vid in newest_10_ids:
            action = "KEEP"
            reason = "newest 10 tagged"

        # Delete only versions whose tags ALL match ^(dev-|pr-) or ^[0-9a-f]{40}$ and are older than retention
        if action is None:
            all_tags_match = tags and all(re.match(r"^(dev-|pr-)|^[0-9a-f]{40}$", t) for t in tags)
            if all_tags_match and age_seconds > retention_seconds:
                action = "DELETE"
                reason = f"age={int(age_seconds / 86400)}d"

        if action is None:
            action = "KEEP"
            reason = "within retention"

        print(f"{action}  | {vid} | {pkg} | {tag_str} | {reason}")

        if action == "DELETE" and not dry_run:
            url = f"{API}/users/{owner}/packages/container/{pkg}/versions/{vid}"
            req = urllib.request.Request(
                url,
                method="DELETE",
                headers={
                    "Authorization": f"Bearer {os.environ['GHCR_TOKEN']}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            try:
                with urllib.request.urlopen(req) as r:
                    code = r.getcode()
                    if code in (200, 202, 204):
                        print(f"  Deleted {vid}: HTTP {code}")
                    else:
                        print(f"  Failed to delete {vid}: HTTP {code}")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                print(f"  Failed to delete {vid}: HTTP {e.code}: {body}", file=sys.stderr)
            continue

        if dry_run:
            print(f"  (dry run - would delete {vid})")
        else:
            print(f"  Kept {vid}")


def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def main():
    token = os.environ["GHCR_TOKEN"]
    owner = os.environ["OWNER"]
    retention_seconds = int(os.environ["RETENTION_DAYS"]) * 86400
    dry_run = os.environ["DRY_RUN"] == "true"
    max_deletions = int(os.environ.get("MAX_DELETIONS", "50"))
    pkg_backend = os.environ["PKG_BACKEND"]
    pkg_ingest = os.environ["PKG_INGEST"]
    pkg_frontend = os.environ["PKG_FRONTEND"]

    packages = [pkg_backend, pkg_ingest, pkg_frontend]

    for pkg in packages:
        base = package_base(owner, pkg, token)
        versions = fetch_all_versions(base, token)
        now = datetime.now(timezone.utc)

        # Pre-compute the plan
        sorted_versions = sorted(
            (v for v in versions if v.get("metadata", {}).get("container", {}).get("tags")),
            key=lambda v: parse_ts(v.get("created_at", "")),
            reverse=True,
        )
        newest_10_ids = {v["id"] for v in sorted_versions[:10]}

        plan = []
        for v in versions:
            vid = v["id"]
            created = v.get("created_at", "")
            tags = v.get("metadata", {}).get("container", {}).get("tags", []) or []
            tag_str = ", ".join(tags) if tags else "untagged"
            digest = v.get("name", "")

            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age_seconds = (now - created_dt).total_seconds()
            except Exception:
                age_seconds = 0

            action = None
            reason = ""

            if not tags:
                action = "KEEP"
                reason = "untagged (may be child manifest)"

            semver_tags = [t for t in tags if re.match(r"^v\d+\.\d+\.\d+$", t)]
            if action is None and semver_tags:
                action = "KEEP"
                reason = "semver tag"

            prod_tags = [t for t in tags if t.startswith("prod-")]
            if action is None and prod_tags:
                action = "KEEP"
                reason = "prod tag"

            if action is None and vid in newest_10_ids:
                action = "KEEP"
                reason = "newest 10 tagged"

            if action is None:
                all_tags_match = tags and all(
                    re.match(r"^(dev-|pr-)|^[0-9a-f]{40}$", t) for t in tags
                )
                if all_tags_match and age_seconds > retention_seconds:
                    action = "DELETE"
                    reason = f"age={int(age_seconds / 86400)}d"

            if action is None:
                action = "KEEP"
                reason = "within retention"

            plan.append((action, vid, tag_str, reason))

        deletions_planned = sum(1 for a, _, _, _ in plan if a == "DELETE")
        if deletions_planned > max_deletions:
            print(f"ABORT: {deletions_planned} deletions planned, MAX_DELETIONS={max_deletions}. Nothing deleted.", file=sys.stderr)
            sys.exit(1)

        for action, vid, tag_str, reason in plan:
            print(f"{action}  | {vid} | {pkg} | {tag_str} | {reason}")

            if action == "DELETE" and not dry_run:
                url = f"{API}/users/{owner}/packages/container/{pkg}/versions/{vid}"
                req = urllib.request.Request(
                    url,
                    method="DELETE",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                try:
                    with urllib.request.urlopen(req) as r:
                        code = r.getcode()
                        if code in (200, 202, 204):
                            print(f"  Deleted {vid}: HTTP {code}")
                        else:
                            print(f"  Failed to delete {vid}: HTTP {code}")
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8", errors="replace")
                    print(f"  Failed to delete {vid}: HTTP {e.code}: {body}", file=sys.stderr)


if __name__ == "__main__":
    main()
