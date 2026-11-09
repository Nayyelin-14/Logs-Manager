# Forwarders for syslog over HTTPS (SaaS)

The Docker appliance accepts native UDP/TCP syslog on host port **514**
(container port **5514**). Render and Vercel only expose HTTPS, so SaaS
deployments use `POST /api/ingest/syslog` instead.

Both examples below forward local syslog to:

```
https://<project>.vercel.app/api/ingest/syslog
```

and authenticate with the tenant API key from `INGEST_API_KEY` in the
`X-API-Key` header. The tenant always comes from that key; do not put a
different tenant in the body.

## Option A: Vector (recommended)

```bash
INGEST_API_KEY='<tenant key>' \
SYSLOG_HTTP_URL='https://<project>.vercel.app/api/ingest/syslog' \
vector --config samples/forwarder/vector.toml
```

Vector listens on UDP 514 locally, wraps each message as `{"lines": [...]}`,
batches up to 500 events, and posts over HTTPS. Run it on the same host as the
device or point the device at the forwarder's IP.

## Option B: rsyslog (`omhttp`)

1. Copy `rsyslog-https.conf` to `/etc/rsyslog.d/60-logs-manager-https.conf`.
2. Replace `<project>` with your Vercel project.
3. Export `INGEST_API_KEY` in the rsyslog service environment (systemd
   `Environment=` or `/etc/default/rsyslog`).
4. Restart rsyslog.

`omhttp` posts one JSON document per message. If your rsyslog build does not
ship `omhttp`, use Vector instead.

## Testing without a forwarder

```bash
INGEST_API_KEY='<tenant key>' samples/send_syslog_http.sh samples/syslog_firewall.log
INGEST_API_KEY='<tenant key>' samples/send_syslog_http.sh samples/syslog_network.log json
```

Expected response (HTTP 202):

```json
{"accepted": 1, "rejected": 0, "errors": []}
```
