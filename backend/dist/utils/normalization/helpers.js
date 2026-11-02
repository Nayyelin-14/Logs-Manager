"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.asRecord = asRecord;
exports.pick = pick;
exports.safeString = safeString;
exports.safeNumber = safeNumber;
exports.safeSeverity = safeSeverity;
exports.safeTimestamp = safeTimestamp;
exports.safeTags = safeTags;
exports.getFirewallEventType = getFirewallEventType;
exports.mapAWSVerb = mapAWSVerb;
exports.mapM365Action = mapM365Action;
exports.mapADEventType = mapADEventType;
exports.mapADAction = mapADAction;
function asRecord(value) {
    return value && typeof value === "object" && !Array.isArray(value)
        ? value
        : undefined;
}
function pick(source, paths) {
    for (const path of paths) {
        const value = path
            .split(".")
            .reduce((acc, key) => acc !== undefined && acc !== null ? acc[key] : undefined, source);
        if (value !== undefined && value !== null && value !== "") {
            return value;
        }
    }
    return undefined;
}
function safeString(value) {
    if (typeof value === "string")
        return value;
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    return undefined;
}
function safeNumber(value) {
    if (typeof value === "number" && !Number.isNaN(value))
        return value;
    if (typeof value === "string" && value.trim() !== "") {
        const parsed = Number(value.trim());
        return Number.isNaN(parsed) ? undefined : parsed;
    }
    return undefined;
}
function safeSeverity(value) {
    const numeric = safeNumber(value);
    if (numeric !== undefined) {
        return Math.max(0, Math.min(10, numeric));
    }
    const key = safeString(value)?.toLowerCase();
    if (!key)
        return undefined;
    switch (key) {
        case "info":
        case "informational":
        case "low":
            return 2;
        case "medium":
        case "moderate":
        case "warning":
            return 5;
        case "high":
        case "error":
            return 8;
        case "critical":
        case "fatal":
            return 10;
        default:
            return undefined;
    }
}
function safeTimestamp(value) {
    if (value) {
        if (typeof value === "number") {
            const millis = value < 1e12 ? value * 1000 : value;
            const date = new Date(millis);
            if (!Number.isNaN(date.getTime()))
                return date.toISOString();
        }
        const date = new Date(value);
        if (!Number.isNaN(date.getTime())) {
            return date.toISOString();
        }
    }
    return new Date().toISOString();
}
function safeTags(value) {
    return Array.isArray(value) ? value.map((tag) => String(tag)) : [];
}
function getFirewallEventType(action) {
    const actionStr = safeString(action)?.toUpperCase();
    switch (actionStr) {
        case "DENY":
        case "BLOCK":
        case "DROP":
            return "firewall_deny";
        case "ALLOW":
        case "PERMIT":
        case "ACCEPT":
            return "firewall_allow";
        default:
            return "network_traffic";
    }
}
function mapAWSVerb(eventName) {
    if (!eventName)
        return undefined;
    if (/^Create/i.test(eventName))
        return "CREATEUSER";
    if (/^Delete/i.test(eventName))
        return "DELETE";
    if (/Login|SignIn/i.test(eventName))
        return "LOGIN";
    if (/Logout|SignOut/i.test(eventName))
        return "LOGOUT";
    return "ALERT";
}
function mapM365Action(operation) {
    if (!operation)
        return undefined;
    if (/LogIn|SignIn|LoggedIn/i.test(operation))
        return "LOGIN";
    if (/LogOut|SignOut|LoggedOut/i.test(operation))
        return "LOGOUT";
    if (/Delete/i.test(operation))
        return "DELETE";
    if (/Create|Add/i.test(operation))
        return "CREATE";
    return "ALERT";
}
function mapADEventType(eventId) {
    switch (eventId) {
        case 4624:
            return "ad_logon_success";
        case 4625:
            return "ad_logon_failed";
        case 4634:
            return "ad_logoff";
        case 4720:
            return "ad_user_created";
        case 4726:
            return "ad_user_deleted";
        default:
            return undefined;
    }
}
function mapADAction(eventId) {
    switch (eventId) {
        case 4624:
        case 4625:
            return "LOGIN";
        case 4634:
            return "LOGOUT";
        case 4720:
            return "CREATEUSER";
        case 4726:
            return "DELETE";
        default:
            return undefined;
    }
}
//# sourceMappingURL=helpers.js.map