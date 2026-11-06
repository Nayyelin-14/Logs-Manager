"""
Webhook receiver service.

Logs incoming alert webhooks and serves recent ones on GET /alerts.
Used as a demo target for alert notifications.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)
ALERTS: list[dict] = []
MAX_ALERTS = 1000


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    data["_received_at"] = datetime.now(timezone.utc).isoformat()
    ALERTS.insert(0, data)
    if len(ALERTS) > MAX_ALERTS:
        ALERTS.pop()
    app.logger.info("WEBHOOK ALERT: %s", json.dumps(data, default=str))
    return jsonify({"status": "ok"}), 200


@app.route("/alerts", methods=["GET"])
def list_alerts():
    return jsonify(ALERTS[:50])


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
