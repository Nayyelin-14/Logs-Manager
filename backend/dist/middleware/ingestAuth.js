"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ingestAuth = ingestAuth;
const crypto_1 = require("crypto");
const isAuth_1 = __importDefault(require("./isAuth"));
const errorHandeling_1 = require("../utils/errorHandeling");
const errrorcode_1 = require("../config/errrorcode");
async function ingestAuth(req, res, next) {
    const providedKey = req.header("x-api-key");
    if (!providedKey) {
        return (0, isAuth_1.default)(req, res, next);
    }
    const identity = findApiKeyIdentity(providedKey);
    if (!identity) {
        return next((0, errorHandeling_1.handleError)("Invalid API key.", 401, errrorcode_1.errorCode.unthenticated));
    }
    if (!identity.tenant) {
        return next((0, errorHandeling_1.handleError)("API key is not bound to a tenant.", 403, errrorcode_1.errorCode.unauthorized));
    }
    const user = {
        userId: 0,
        role: "USER",
        tenant: identity.tenant,
        email: identity.email || "api-key@local",
        username: identity.username || "api-key",
    };
    req.user = user;
    return next();
}
function findApiKeyIdentity(providedKey) {
    const identities = loadApiKeys();
    for (const [key, identity] of identities) {
        if (safeEqual(providedKey, key)) {
            return identity;
        }
    }
    return undefined;
}
function loadApiKeys() {
    const identities = new Map();
    const raw = process.env.INGEST_API_KEYS;
    if (raw) {
        try {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
                for (const [key, value] of Object.entries(parsed)) {
                    if (typeof value === "string") {
                        identities.set(key, { tenant: value });
                    }
                    else if (value && typeof value === "object") {
                        const record = value;
                        identities.set(key, {
                            tenant: typeof record.tenant === "string" ? record.tenant : "",
                            username: typeof record.username === "string"
                                ? record.username
                                : undefined,
                            email: typeof record.email === "string" ? record.email : undefined,
                        });
                    }
                }
            }
        }
        catch (error) {
            console.error("Invalid INGEST_API_KEYS JSON:", error);
        }
    }
    const singleKey = process.env.INGEST_API_KEY;
    if (singleKey) {
        identities.set(singleKey, {
            tenant: process.env.INGEST_API_TENANT ||
                process.env.INGEST_DEFAULT_TENANT ||
                "",
            username: process.env.INGEST_API_USERNAME || "api-key",
        });
    }
    return identities;
}
function safeEqual(left, right) {
    const leftBuffer = Buffer.from(left);
    const rightBuffer = Buffer.from(right);
    if (leftBuffer.length !== rightBuffer.length)
        return false;
    return (0, crypto_1.timingSafeEqual)(leftBuffer, rightBuffer);
}
//# sourceMappingURL=ingestAuth.js.map