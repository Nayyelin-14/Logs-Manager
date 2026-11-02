"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseSyslogMessage = parseSyslogMessage;
const MONTHS = {
    Jan: 0,
    Feb: 1,
    Mar: 2,
    Apr: 3,
    May: 4,
    Jun: 5,
    Jul: 6,
    Aug: 7,
    Sep: 8,
    Oct: 9,
    Nov: 10,
    Dec: 11,
};
const KEY_VALUE_PATTERN = /(?:^|\s)([A-Za-z_][\w.-]*)=(?:"([^"]*)"|'([^']*)'|(\S+))/g;
function parseSyslogMessage(input) {
    const original = input.trim();
    if (!original)
        return null;
    let priority;
    let rest = original;
    const priorityMatch = rest.match(/^<(\d{1,3})>/);
    if (priorityMatch) {
        priority = Number(priorityMatch[1]);
        rest = rest.slice(priorityMatch[0].length);
    }
    let timestamp = new Date().toISOString();
    let hostname;
    let message = rest;
    const rfc5424 = rest.match(/^1\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(?:-|\[[^\]]*\])\s*(.*)$/s);
    if (rfc5424) {
        timestamp = normalizeTimestamp(rfc5424[1]) ?? timestamp;
        hostname = rfc5424[2] === "-" ? undefined : rfc5424[2];
        message = rfc5424[6];
    }
    else {
        const rfc3164 = rest.match(/^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)$/s);
        if (rfc3164) {
            timestamp = parseRfc3164Timestamp(rfc3164[1]) ?? timestamp;
            hostname = rfc3164[2];
            message = rfc3164[3];
        }
    }
    const fields = parseKeyValues(message);
    const parsed = {
        ...fields,
        priority,
        timestamp,
        host: fields.host || hostname,
        hostname,
        message: original,
    };
    if (!fields.msg) {
        parsed.msg = message;
    }
    return parsed;
}
function parseKeyValues(message) {
    const fields = {};
    KEY_VALUE_PATTERN.lastIndex = 0;
    let match;
    while ((match = KEY_VALUE_PATTERN.exec(message)) !== null) {
        const value = match[2] ?? match[3] ?? match[4] ?? "";
        fields[match[1]] = value;
    }
    return fields;
}
function parseRfc3164Timestamp(value) {
    const match = value.match(/^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})$/);
    if (!match)
        return undefined;
    const month = MONTHS[match[1]];
    if (month === undefined)
        return undefined;
    const now = new Date();
    const date = new Date(Date.UTC(now.getUTCFullYear(), month, Number(match[2]), Number(match[3]), Number(match[4]), Number(match[5])));
    if (date.getTime() > Date.now() + 24 * 60 * 60 * 1000) {
        date.setUTCFullYear(date.getUTCFullYear() - 1);
    }
    return date.toISOString();
}
function normalizeTimestamp(value) {
    if (!value || value === "-")
        return undefined;
    const numeric = Number(value);
    if (!Number.isNaN(numeric) && value.trim() !== "") {
        const millis = numeric < 1e12 ? numeric * 1000 : numeric;
        const date = new Date(millis);
        return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}
//# sourceMappingURL=syslog.js.map