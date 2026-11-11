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
vector --dangerously-allow-env-var-interpolation \
  --config samples/forwarder/vector.toml
```

`--dangerously-allow-env-var-interpolation` (or
`VECTOR_DANGEROUSLY_ALLOW_ENV_VAR_INTERPOLATION=true`) is required by Vector
0.61+: without it, `${SYSLOG_HTTP_URL}` and `${INGEST_API_KEY}` stay literal
and validation fails. The config also sets
`dangerously_allow_unconfined_template_resolution`, because Vector treats a
fully templated URI as lacking a static authority. The URL comes from the
operator, not from log events; Vector logs a confinement warning at startup
that is expected for this setup.

To validate the config before starting Vector:

```bash
INGEST_API_KEY='<tenant key>' \
SYSLOG_HTTP_URL='https://<project>.vercel.app/api/ingest/syslog' \
vector validate --dangerously-allow-env-var-interpolation \
  samples/forwarder/vector.toml
```

Vector listens on UDP 514 locally, sends **newline-delimited raw Syslog
text** (`Content-Type: text/plain`), batches up to 500 messages, and posts
over HTTPS. Do not wrap each event in `{"lines": [...]}`: with batching that
produces one JSON object per line, which the receiver rejects. Run Vector on
the same host as the device or point the device at the forwarder's IP.

Durability and retries:

- Events are buffered on **disk** (256 MiB cap, `when_full = "block"`) under
  Vector's `data_dir`, so a restart does not lose queued messages. Ensure that
  directory is writable and has room for the buffer.
- Vector retries HTTP **429, 5xx** and connection/timeout failures with
  exponential backoff. A `503` means nothing was persisted and the request
  should be retried.
- A `4xx` is treated as a permanent payload/auth problem. Validation and parse
  failures are reported in the `202` body per line and are not retried.

Response semantics:

| Status | Meaning |
|---|---|
| `202` | Request handled. Inspect `accepted` / `rejected` / `errors` per line. |
| `503` | Transient storage failure; nothing was persisted. Retry the request. |
| `500` | Unexpected server failure; retry is safe. |
| `400/401/403/413` | Permanent request/auth/limit problem. Do not retry unchanged. |

## Option B: rsyslog (`omhttp`)

1. Copy `rsyslog-https.conf` to `/etc/rsyslog.d/60-logs-manager-https.conf`.
2. Replace `<project>` with your Vercel project.
3. Export `INGEST_API_KEY` in the rsyslog service environment (systemd
   `Environment=` or `/etc/default/rsyslog`). The config reads it with
   `getenv()`, not `${...}`.
4. Restart rsyslog.

`omhttp` posts one JSON document per message, built from `%rawmsg%` so the
original PRI/timestamp/hostname survive. It retries transport errors, 429 and
5xx by default, keeps a bounded disk-assisted action queue, and resumes
indefinitely. If your rsyslog build does not ship `omhttp`, use Vector instead.

## Retry and duplicate semantics

The HTTPS endpoint commits an entire batch in one transaction. A `503`
therefore means no event from that request was stored, so retrying is safe for
messages that carry their own timestamp.

Devices that emit Syslog lines with **no embedded timestamp** are the
exception: the parser stamps them with the time of ingestion (existing
behavior, preserved intentionally). If the database commits but the HTTP
response is lost, a retry creates a second row for such a line. Keep the
device timestamp in the payload (`%rawmsg%` / Vector's raw `message`) to avoid
this; it is the only reliable identity signal.


## Testing without a forwarder

```bash
INGEST_API_KEY='<tenant key>' samples/send_syslog_http.sh samples/syslog_firewall.log
INGEST_API_KEY='<tenant key>' samples/send_syslog_http.sh samples/syslog_network.log json
```

Expected response (HTTP 202):

```json
{"accepted": 1, "rejected": 0, "errors": []}
```
