import { NextFunction, Response } from "express";
import { timingSafeEqual } from "crypto";
import authMiddleware from "./isAuth";
import { CustomRequest, TokenPayload } from "../utils/refreshToken";
import { handleError } from "../utils/errorHandeling";
import { errorCode } from "../config/errrorcode";

interface ApiKeyIdentity {
  tenant: string;
  username?: string;
  email?: string;
}

export async function ingestAuth(
  req: CustomRequest,
  res: Response,
  next: NextFunction
) {
  const providedKey = req.header("x-api-key");

  if (!providedKey) {
    return authMiddleware(req, res, next);
  }

  const identity = findApiKeyIdentity(providedKey);

  if (!identity) {
    return next(
      handleError("Invalid API key.", 401, errorCode.unthenticated)
    );
  }

  if (!identity.tenant) {
    return next(
      handleError(
        "API key is not bound to a tenant.",
        403,
        errorCode.unauthorized
      )
    );
  }

  const user: TokenPayload = {
    userId: 0,
    role: "USER",
    tenant: identity.tenant,
    email: identity.email || "api-key@local",
    username: identity.username || "api-key",
  };

  req.user = user;
  return next();
}

function findApiKeyIdentity(providedKey: string): ApiKeyIdentity | undefined {
  const identities = loadApiKeys();

  for (const [key, identity] of identities) {
    if (safeEqual(providedKey, key)) {
      return identity;
    }
  }

  return undefined;
}

function loadApiKeys(): Map<string, ApiKeyIdentity> {
  const identities = new Map<string, ApiKeyIdentity>();

  const raw = process.env.INGEST_API_KEYS;
  if (raw) {
    try {
      const parsed = JSON.parse(raw);

      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        for (const [key, value] of Object.entries(parsed)) {
          if (typeof value === "string") {
            identities.set(key, { tenant: value });
          } else if (value && typeof value === "object") {
            const record = value as Record<string, unknown>;
            identities.set(key, {
              tenant:
                typeof record.tenant === "string" ? record.tenant : "",
              username:
                typeof record.username === "string"
                  ? record.username
                  : undefined,
              email:
                typeof record.email === "string" ? record.email : undefined,
            });
          }
        }
      }
    } catch (error) {
      console.error("Invalid INGEST_API_KEYS JSON:", error);
    }
  }

  const singleKey = process.env.INGEST_API_KEY;
  if (singleKey) {
    identities.set(singleKey, {
      tenant:
        process.env.INGEST_API_TENANT ||
        process.env.INGEST_DEFAULT_TENANT ||
        "",
      username: process.env.INGEST_API_USERNAME || "api-key",
    });
  }

  return identities;
}

function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);

  if (leftBuffer.length !== rightBuffer.length) return false;
  return timingSafeEqual(leftBuffer, rightBuffer);
}
