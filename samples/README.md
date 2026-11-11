# Sample ingestion

All HTTP requests use the machine API key, not a browser JWT cookie:

```bash
export LMS_API_URL=http://localhost:4500/api
export INGEST_API_KEY=change_me_to_a_long_random_value
```

The API key must be configured in `.env` and linked to the `demoa` tenant by
seeding (or by rotating the tenant key in the admin UI):

```dotenv
INGEST_API_KEY=change_me_to_a_long_random_value
INGEST_DEFAULT_TENANT=demoA
INGEST_API_USERNAME=log-forwarder
```

`tenant` in a request body must match the API key tenant. If it is omitted, the
API key tenant is used.

## Syslog

The self-hosted Docker stack receives native Syslog in its dedicated `ingest`
container. Configure it in the root `.env`:

```dotenv
SYSLOG_ENABLED=true
SYSLOG_HOST_PORT=514
SYSLOG_TENANT=demoA
SYSLOG_SOURCE=firewall
SYSLOG_UDP_PORT=5514
SYSLOG_TCP_PORT=5514
```

The container always listens on 5514; `SYSLOG_HOST_PORT` is the host-side port.
If host port 514 is busy (or Docker Desktop/WSL2 refuses it), set
`SYSLOG_HOST_PORT=5514` and send to 5514. The API container does not open a
Syslog port.

Hosted SaaS has no native listener. Use the HTTPS endpoint instead:

```bash
SYSLOG_HTTP_URL=https://<project>.vercel.app/api/ingest/syslog \
  INGEST_API_KEY="$INGEST_API_KEY" \
  ./samples/send_syslog_http.sh samples/syslog_firewall.log
```

Send the firewall or router sample:

```bash
./samples/send_syslog.sh udp samples/syslog_firewall.log
./samples/send_syslog.sh tcp samples/syslog_network.log
```

`send_syslog.sh` supports `SYSLOG_HOST` and `SYSLOG_PORT` overrides:

```bash
SYSLOG_PORT=5514 ./samples/send_syslog.sh udp samples/syslog_firewall.log
```

You can also use `logger`:

```bash
logger --udp --server 127.0.0.1 --port 5514 \
  '<134>Oct 30 22:14:15 fw01 vendor=Fortinet product=FortiGate action=DENY src=10.0.0.5 dst=8.8.8.8 spt=54321 dpt=53 proto=UDP msg="DNS query blocked" policy=block-dns if=wan1 event=traffic'
```

Messages may include `source=network` to override `SYSLOG_SOURCE` per message.
The listeners accept RFC3164, RFC5424, key-value fields, newline-delimited TCP,
and octet-counted TCP framing.

## Single HTTP event

```bash
python3 samples/post_logs.py samples/ad_4625.json
python3 samples/post_logs.py samples/crowdstrike.json
python3 samples/post_logs.py samples/aws_cloudtrail.json
python3 samples/post_logs.py samples/m365_audit.json
```

Or with `curl`:

```bash
curl -sS -X POST "$LMS_API_URL/ingest" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $INGEST_API_KEY" \
  --data @samples/aws_cloudtrail.json
```

## Batch HTTP events

JSON array or JSONL:

```bash
python3 samples/post_logs.py samples/batch_sample.jsonl
```

CSV upload:

```bash
curl -sS -X POST "$LMS_API_URL/ingest/batch" \
  -H "X-API-Key: $INGEST_API_KEY" \
  -F "file=@samples/ad_4625.csv"
```

JSON file upload:

```bash
curl -sS -X POST "$LMS_API_URL/ingest/batch" \
  -H "X-API-Key: $INGEST_API_KEY" \
  -F "file=@samples/crowdstrike.json"
```

`POST /api/ingest/batch` accepts:

- a multipart file field named `file` (JSON array, JSONL/NDJSON, or CSV)
- a raw JSON array
- `{ "events": [...] }` (also `logs`, `records`, `items`, or `data`)
- a single JSON event object

The default batch limit is 1000 events (`INGEST_BATCH_MAX_EVENTS`) and the
default upload limit is 10 MiB (`INGEST_MAX_FILE_BYTES`).

## Source mapping

`source` accepts the database enum values and these aliases:

| Alias | Stored source |
| --- | --- |
| `syslog`, `firewall`, `fortinet`, `paloalto`, `fortigate` | `FIREWALL` |
| `network`, `router`, `switch` | `NETWORK` |
| `aws`, `cloudtrail`, `amazon`, `aws_cloudtrail` | `AWS` |
| `crowdstrike`, `falcon`, `cs` | `CROWDSTRIKE` |
| `m365`, `o365`, `office365`, `microsoft365` | `M365` |
| `ad`, `active_directory`, `windows_ad`, `windows`, `logon` | `AD` |
| `api`, `http`, `json` | `API` |

When a batch event has no `source`, the service infers it from vendor fields
(for example `eventSource`/`aws_region` for AWS, `DetectName`/`ComputerName`
for CrowdStrike, `Operation`/`Workload` for M365, and `EventID`/
`TargetUserName` for Active Directory).

## Files

- `syslog_firewall.log` - RFC3164 firewall key-value sample
- `syslog_network.log` - RFC3164 router key-value sample
- `crowdstrike.json` / `crowdstrike.csv`
- `aws_cloudtrail.json` / `aws_cloudtrail.csv`
- `m365_audit.json` / `m365_audit.csv`
- `ad_4625.json` / `ad_4625.csv`
- `batch_sample.jsonl` - mixed-source batch
- `send_syslog.sh` - UDP/TCP/logger sender
- `post_logs.py` - single and batch JSON sender
