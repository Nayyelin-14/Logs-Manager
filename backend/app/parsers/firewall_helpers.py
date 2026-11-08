import ipaddress
import re
from datetime import datetime, timezone
from typing import Any, Optional
def parse_syslog_pri(pri: int) -> tuple[int, int]:
    facility = pri // 8
    severity = pri % 8
    return facility, severity
def parse_syslog_timestamp(
    timestamp_str: str,
    reference_time: Optional[datetime] = None,
) -> Optional[datetime]:
    try:
        month_day_time = timestamp_str.strip()
        if reference_time is not None:
            ref = reference_time
        else:
            ref = datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        else:
            ref = ref.astimezone(timezone.utc)
        ref_year = ref.year
        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ]

        parts = month_day_time.split()
        if len(parts) != 3:
            return None
        month_name = parts[0]
        if month_name not in month_names:
            return None
        month = month_names.index(month_name) + 1

        try:
            day = int(parts[1])
        except ValueError:
            return None
        time_parts = parts[2].split(":")
        if len(time_parts) != 3:
            return None
        try:
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2])
        except ValueError:
            return None
        if not (1 <= month <= 12):
            return None
        if not (1 <= day <= 31):
            return None
        if not (0 <= hour <= 23):
            return None
        if not (0 <= minute <= 59):
            return None
        if not (0 <= second <= 59):
            return None
        candidates = [ref_year - 1, ref_year, ref_year + 1]
        best_dt = None
        best_diff = None
        for year in candidates:
            try:
                candidate = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
                diff = abs((candidate - ref).total_seconds())
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_dt = candidate
            except ValueError:
                continue
        if best_dt is None:
            return None

        return best_dt
    except Exception:
        return None
def parse_key_value_message(message: str) -> dict[str, str]:
    result = {}
    if not message:
        return result
    parts = message.split()

    current_key = None
    current_value = []

    for part in parts:
        if '=' in part:
            if current_key is not None and current_value and current_key not in result:
                result[current_key] = ' '.join(current_value)
            key, value = part.split('=', 1)
            if key not in result:
                current_key = key
                current_value = [value] if value else []
            else:
                current_key = None
                current_value = []
        else:
            if current_key is not None:
                current_value.append(part)
    if current_key is not None and current_value and current_key not in result:
        result[current_key] = ' '.join(current_value)
    return result

def validate_ip(ip_str: Optional[str]) -> Optional[str]:
    if ip_str is None:
        return None
    try:
        ipaddress.ip_address(ip_str)
        return ip_str
    except ValueError:
        return None
def validate_port(port: Optional[Any]) -> Optional[int]:
    if port is None:
        return None
    try:
        port_int = int(port)
        if 0 <= port_int <= 65535:
            return port_int
        return None
    except (ValueError, TypeError):
        return None
