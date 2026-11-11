#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def load_events(path):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read().strip()

    if not text:
        raise ValueError("Input file is empty.")

    if path.lower().endswith((".jsonl", ".ndjson")):
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    data = json.loads(text)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("events", "logs", "records", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]

    raise ValueError("Input must be a JSON object or array.")


def post_json(url, payload, api_key):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Send single or batch log events to the Logs Manager API."
    )
    parser.add_argument("file", help="JSON, JSONL, or NDJSON file")
    parser.add_argument(
        "--url",
        default=os.environ.get("LMS_API_URL", "http://localhost:4500/api"),
        help="API base URL (default: http://localhost:4500/api)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("INGEST_API_KEY"),
        help="Machine ingestion API key (or set INGEST_API_KEY)",
    )
    parser.add_argument("--tenant", help="Tenant to set on events missing one")
    parser.add_argument("--source", help="Source to set on events missing one")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Force the batch endpoint even for a single event",
    )
    args = parser.parse_args()

    if not args.api_key:
        parser.error("Provide --api-key or set INGEST_API_KEY.")

    events = load_events(args.file)

    for event in events:
        if not isinstance(event, dict):
            continue
        if args.source and not event.get("source"):
            event["source"] = args.source
        if args.tenant and not event.get("tenant"):
            event["tenant"] = args.tenant

    is_batch = args.batch or len(events) > 1
    endpoint = f"{args.url.rstrip('/')}/ingest" + ("/batch" if is_batch else "")
    # The documented batch contract is an object; the API also accepts a bare
    # array, but send the wrapped form so older servers keep working.
    payload = {"events": events} if is_batch else events[0]

    if not is_batch and not payload.get("source"):
        payload["source"] = args.source or "api"

    status, response_body = post_json(endpoint, payload, args.api_key)
    print(f"POST {endpoint} -> {status}")
    print(response_body)

    if status >= 400:
        sys.exit(1)


if __name__ == "__main__":
    main()
