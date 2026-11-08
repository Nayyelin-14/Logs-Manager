import json
import re
from typing import Any, Dict, List, Tuple

from app.core.config import get_settings
from app.core.exceptions import ValidationError
settings = get_settings()
ALLOWED_EXTENSIONS = ("json", "jsonl", "ndjson", "csv", "log", "txt")
MAX_FILE_BYTES = settings.INGEST_MAX_FILE_BYTES
MAX_RECORDS = settings.INGEST_BATCH_MAX_EVENTS

_SYSLOG_PRI = re.compile(r"^<\d{1,3}>")
_RFC3164_HEAD = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s")
_RFC5424_HEAD = re.compile(r"^1\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s")

def validate_upload(filename: str, size: int) -> None:
    if not filename or "." not in filename:
        raise ValidationError("Uploaded file must have a file extension.")
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}."
        )
    if size <= 0:
        raise ValidationError("Uploaded file is empty.")
    if size > MAX_FILE_BYTES:
        raise ValidationError(
            f"File exceeds the {MAX_FILE_BYTES} byte upload limit (got {size} bytes)."
        )
def looks_like_syslog_line(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if _SYSLOG_PRI.match(line):
        return True
    if _RFC3164_HEAD.match(line):
        return True
    if _RFC5424_HEAD.match(line):
        return True
    return False
def detect_format(text: str, filename: str, mimetype: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext in ("jsonl", "ndjson"):
        return "jsonl"
    if ext == "json":
        return "json"
    if ext == "csv":
        return "csv"

    if "csv" in mimetype and ext not in ("log", "txt"):
        return "csv"
    if "jsonl" in mimetype or "ndjson" in mimetype:
        return "jsonl"
    if "json" in mimetype and ext not in ("log", "txt"):
        return "json"

    lines = [ln for ln in text.splitlines() if ln.strip()]
    first_line = lines[0].strip() if lines else ""
    syslog_hits = sum(1 for ln in lines[:20] if looks_like_syslog_line(ln))
    if lines and syslog_hits >= max(1, len(lines[:20]) // 2):
        return "syslog"
    if first_line.startswith(("[", "{")):
        try:
            json.loads(text)
            return "json"
        except json.JSONDecodeError:
            return "jsonl"

    if "," in first_line:
        return "csv"
    if syslog_hits:
        return "syslog"
    return "jsonl"
def parse_batch_records(
    buffer: bytes,
    original_name: str = "",
    mimetype: str = "",
) -> Tuple[List[dict], List[Dict[str, Any]], str]:

    try:
        text = buffer.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValidationError(f"File is not valid UTF-8 text: {e}")
    text = text.replace("\ufeff", "").strip()
    if not text:
        raise ValidationError("Uploaded file is empty.")
    format_type = detect_format(text, original_name, mimetype)
    events: List[dict] = []
    rejected: List[Dict[str, Any]] = []
    if format_type == "json":
        events = parse_json(text)
    elif format_type == "jsonl":
        events, rejected = parse_json_lines(text)
    elif format_type == "csv":
        events = parse_csv(text)
    elif format_type == "syslog":
        events, rejected = parse_syslog_records(text)
    if not events:
        detail = f" First rejection: {rejected[0].get('error')}" if rejected else ""
        raise ValidationError(f"No events found in the uploaded file.{detail}")
    if len(events) > MAX_RECORDS:
        rejected.extend(
            {"index": idx, "error": f"Record limit of {MAX_RECORDS} exceeded, record discarded"}
            for idx in range(MAX_RECORDS, len(events))
        )
        events = events[:MAX_RECORDS]
    return events, rejected, format_type
def parse_batch_buffer(
    buffer: bytes,
    original_name: str = "",
    mimetype: str = "",
) -> List[dict]:
    events, _rejected, _fmt = parse_batch_records(buffer, original_name, mimetype)
    return events
def parse_json(text: str) -> List[dict]:

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}")
    if isinstance(parsed, list):
        return [event for event in parsed if isinstance(event, dict)]
    if isinstance(parsed, dict):
        for key in ["events", "logs", "records", "items", "data"]:
            if isinstance(parsed.get(key), list):
                return [event for event in parsed[key] if isinstance(event, dict)]
        return [parsed]
    raise ValidationError("JSON must contain an object or array of objects.")
def parse_json_lines(text: str) -> Tuple[List[dict], List[Dict[str, Any]]]:
    events: List[dict] = []
    rejected: List[Dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            rejected.append({"index": idx, "error": f"Invalid JSON on line {idx}: {e}"})
            continue
        if not isinstance(record, dict):
            rejected.append({
                "index": idx,
                "error": f"Line {idx} is a {type(record).__name__}, expected a JSON object",
            })
            continue
        events.append(record)
    return events, rejected
def parse_syslog_records(text: str) -> Tuple[List[dict], List[Dict[str, Any]]]:
    from app.integrations.syslog import parse_syslog_message
    events: List[dict] = []
    rejected: List[Dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parsed = parse_syslog_message(line)
        if not parsed:
            rejected.append({"index": idx, "error": f"Unparseable syslog line {idx}"})
            continue
        parsed["rawMessage"] = line
        events.append(parsed)
    return events, rejected

def parse_csv(text: str) -> List[dict]:

    events: List[dict] = []
    lines = text.splitlines()
    if not lines:
        return events
    headers = parse_csv_row(lines[0])
    if not headers or all(h == "" for h in headers):
        raise ValidationError("CSV file is missing a header row.")
    for row_idx in range(1, len(lines)):
        row = parse_csv_row(lines[row_idx])
        if all(v == "" for v in row):
            continue
        event = {}
        for col_idx, header in enumerate(headers):
            if not header:
                continue
            event[header] = row[col_idx] if col_idx < len(row) else ""
        events.append(event)
    return events

def parse_csv_row(line: str) -> List[str]:
    fields: List[str] = []
    field = ""
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    field += '"'
                    i += 1
                else:
                    in_quotes = False
            else:
                field += ch
        else:
            if ch == '"':
                in_quotes = True
            elif ch == ',':
                fields.append(field)
                field = ""
            else:
                field += ch
        i += 1
    fields.append(field)
    return fields
