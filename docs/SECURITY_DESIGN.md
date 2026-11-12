# Security Design — Authentication, Authorization, and Tenant Isolation

**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Implemented

---

## 1. Authentication Architecture

### 1.1 JWT Configuration (Exact Match to the Legacy Backend)

| Parameter | Value | Source |
|-----------|-------|--------|
| **Algorithm** | HS256 | `JWT_ALGORITHM`; encoded/decoded with PyJWT |
| **Access Token Secret** | `ACCESS_TOKEN_SECRET` env | 32+ char random |
| **Refresh Token Secret** | `REFRESH_TOKEN_SECRET` env | 32+ char random |
| **Access Token TTL** | 15 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| **Refresh Token TTL** | 30 days | `REFRESH_TOKEN_EXPIRE_DAYS` |
| **Token Payload** | `{ userId, username, email, tenant, role, exp }` | `TokenPayload.to_dict()` |

### 1.2 JWT Payload Structure

`TokenPayload` is a plain Python class (not a Pydantic model). It keeps
snake_case attributes internally and maps them to the camelCase `userId` claim
in the JWT.

```python
# app/core/security.py
class TokenPayload:
    def __init__(self, user_id: int, username: Optional[str], email: str,
                 tenant: str, role: str):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.tenant = tenant
        self.role = role

    def to_dict(self) -> dict:
        return {
            "userId": self.user_id,
            "username": self.username,
            "email": self.email,
            "tenant": self.tenant,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenPayload":
        return cls(
            user_id=data.get("userId") or data.get("user_id"),
            username=data.get("username"),
            email=data.get("email"),
            tenant=data.get("tenant"),
            role=data.get("role"),
        )
```

### 1.3 Token Creation

```python
# app/core/security.py
import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings

def create_access_token(payload: TokenPayload) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_payload = payload.to_dict()
    token_payload.update({"exp": int(expire.timestamp())})
    return jwt.encode(token_payload, settings.ACCESS_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(payload: TokenPayload) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token_payload = payload.to_dict()
    token_payload.update({"exp": int(expire.timestamp())})
    return jwt.encode(token_payload, settings.REFRESH_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
```

### 1.4 Cookie Settings (Exact Match)

```python
# app/core/config.py
class Settings(BaseSettings):
    COOKIE_SECURE: bool = False  # True in production
    COOKIE_SAME_SITE: str = "lax"  # "none" in production cross-origin
    
    def cookie_options(self) -> dict:
        return {
            "httponly": True,
            "secure": self.COOKIE_SECURE,
            "samesite": self.COOKIE_SAME_SITE,
            "path": "/",
        }
```

**Legacy Reference (`cookieOptions.ts`):**
```typescript
const secure = process.env.COOKIE_SECURE === "true" || process.env.NODE_ENV === "production";
const sameSite = process.env.COOKIE_SAME_SITE || (secure ? "none" : "lax");
return { httpOnly: true, secure, sameSite };
```

### 1.5 Setting Cookies on Response

```python
# app/api/routes/auth.py
from fastapi import Response
from app.core.config import settings

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    opts = settings.cookie_options()
    response.set_cookie(
        "accessToken",
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **opts
    )
    response.set_cookie(
        "refreshToken",
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **opts
    )

def clear_auth_cookies(response: Response):
    opts = settings.cookie_options()
    response.delete_cookie("accessToken", **opts)
    response.delete_cookie("refreshToken", **opts)
```

---

## 2. Authentication Flow

### 2.1 Login Flow

```
POST /api/auth/login
    │
    ▼
Validate email + password (bcrypt)
    │
    ▼
Create TokenPayload { userId, username, email, tenant, role }
    │
    ▼
Generate access_token (15m) + refresh_token (30d)
    │
    ▼
Set HttpOnly cookies on response
    │
    ▼
Return { message, userData (UserPublic) }
```

### 2.2 Automatic Token Refresh (Middleware)

**Legacy Behavior (`isAuth.ts`):**
1. Check `accessToken` cookie
2. If valid → continue
3. If expired/missing → check `refreshToken` cookie
4. Verify refresh token → fetch user from DB
5. Issue new access + refresh tokens
6. Set new cookies
7. Attach user to request → continue

**FastAPI Implementation (`app/core/dependencies.py`):**

```python
from jwt import ExpiredSignatureError, PyJWTError
from app.core.security import (
    TokenPayload,
    decode_token,
    create_access_token,
    create_refresh_token,
)

async def get_current_user(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenPayload:
    access_token = request.cookies.get("accessToken")
    refresh_token = request.cookies.get("refreshToken")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated user. Try Again!!!",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try the access token first.
    if access_token:
        try:
            payload = decode_token(access_token, settings.ACCESS_TOKEN_SECRET)
            user = await session.scalar(
                select(User).where(User.id == payload["userId"])
            )
            if not user or user.status != "ACTIVE":
                raise HTTPException(status_code=401, detail="Account not active")

            # Rebuild authorization from the current DB row. Never trust stale
            # role/tenant claims from the token.
            return TokenPayload(
                user_id=user.id,
                username=user.username,
                email=user.email,
                tenant=user.tenant,
                role=user.role.value if hasattr(user.role, "value") else user.role,
            )
        except ExpiredSignatureError:
            pass  # Fall through to refresh.
        except PyJWTError:
            pass  # Fall through to refresh.

    # Access token missing or invalid → try the refresh token.
    try:
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
        user = await session.scalar(select(User).where(User.id == payload["userId"]))
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=401, detail="Account not active")

        new_payload = TokenPayload(
            user_id=user.id,
            username=user.username,
            email=user.email,
            tenant=user.tenant,
            role=user.role.value if hasattr(user.role, "value") else user.role,
        )
        opts = settings.cookie_options()
        response.set_cookie(
            "accessToken",
            create_access_token(new_payload),
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            **opts,
        )
        response.set_cookie(
            "refreshToken",
            create_refresh_token(new_payload),
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            **opts,
        )
        # Keep the non-HttpOnly double-submit CSRF cookie alive as well.
        return new_payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token refresh failed")
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Token refresh failed")
```

---

## 3. Authentication Flow

Authentication is **login-only**. There is **no public self-registration**, **no OTP verification**, and **no password-recovery flow**. Admin users create accounts with `POST /api/create-user`; clients log in with `POST /api/auth/login` and receive HttpOnly JWT cookies. The legacy `Otp` table/email flow is not implemented and not used by any route.
```

## 4. Role-Based Access Control

### 4.1 Role Mapping

| Code Role | Assignment Role | Description |
|-----------|-----------------|-------------|
| `ADMIN` (tenant `NULL`) | Platform ADMIN | Full administrative access; may query all tenants when `tenant` is empty/`all`, or a specific tenant otherwise |
| `ADMIN` (tenant set) | Tenant ADMIN | Administrative access bound to its own tenant; cross-tenant reads/writes and tenant management are rejected |
| `VIEWER` | VIEWER | Read-only access; always forced to `user.tenant`, ignoring requested `tenant` |

The code uses `ADMIN` and `VIEWER` directly. There is no legacy `USER` role.
The seed/demo admin is a platform ADMIN with `tenant = NULL`.

### 4.2 Authorization Dependencies

```python
# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from app.models.user import User

async def require_admin(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user

async def require_viewer(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if current_user.role not in ("VIEWER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user

# For endpoints that allow both but need tenant scoping
async def get_current_user_any(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    return current_user
```

`require_admin` establishes the role. Routes that touch tenant-owned resources
also call `owns_tenant` / `effective_read_tenant` (ingest rules) so a
tenant-bound ADMIN cannot modify another tenant's rules, alerts, users, logs,
or tenant API keys. Tenant management (`/api/tenants*`) requires a platform
ADMIN (`tenant = NULL`). Cross-tenant reads remain available to a platform
ADMIN by design.

### 4.3 Endpoint Protection Matrix

| Endpoint | Required Dependency | Notes |
|----------|---------------------|-------|
| `POST /api/auth/login` | None | Public |
| `POST /api/auth/logout` | `get_current_user` | Authenticated |
| `GET /api/auth/auth-check` | `get_current_user` | Authenticated |
| `POST /api/ingest` | `verify_api_key` OR `get_current_user` | API key or user |
| `POST /api/ingest/batch` | `verify_api_key` OR `get_current_user` | API key or user |
| `POST /api/ingest/file` | `verify_api_key` OR `get_current_user` | API key or user |
| `POST /api/ingest/syslog` | `verify_api_key` | TLS syslog forwarder |
| `GET /api/events/{event_id}` | `get_current_user` | Tenant-scoped detail; 404 on tenant mismatch |
| `GET /api/get-logs` | `get_current_user` | VIEWER+ (tenant-scoped) |
| `DELETE /api/delete-log/:id` | `require_admin` | Admin only |
| `GET /api/dashboard` | `get_current_user` | VIEWER+ (tenant-scoped) |
| `GET /api/get-alerts` | `get_current_user` | VIEWER+ (tenant-scoped) |
| `PATCH /api/alerts/:id` | `require_admin` | Admin only |
| `GET /api/get-rules` | `require_admin` | Admin only |
| `POST /api/create-alertRule` | `require_admin` | Admin only |
| `PUT /api/update-rule/:id` | `require_admin` | Admin only |
| `PATCH /api/rules/:id/enabled` | `require_admin` | Admin only |
| `DELETE /api/delete-rule/:id` | `require_admin` | Admin only |
| `POST /api/rules/:id/test` | `require_admin` | Admin only |
| `GET /api/get-users` | `require_admin` | Admin only |
| `POST /api/create-user` | `require_admin` | Admin only |
| `PUT /api/update-user` | `require_admin` | Admin only |
| `DELETE /api/delete-user/:id` | `require_admin` | Admin only |
| `GET /api/get-all-data` | `require_admin` | Admin only |
| `GET /api/tenants` | `require_admin` | Admin only |
| `POST /api/tenants` | `require_admin` | Admin only |
| `PATCH /api/tenants/{name}` | `require_admin` | Admin only |
| `POST /api/tenants/{name}/rotate-key` | `require_admin` | Admin only |

---

## 5. Tenant Isolation

### 5.1 Core Principle

**Never trust tenant identifiers from VIEWER requests.** Tenant is always derived from the authenticated user's identity.

### 5.2 Tenant Resolution Logic

```python
# app/core/tenancy.py
def resolve_read_tenant(user, requested: Optional[str] = None) -> Optional[str]:
    """Return the tenant filter for read endpoints.

    None means "all tenants" and is reserved for platform admins (ADMIN with
    no tenant). Any other account is forced to its own tenant; an account
    without a tenant gets 403 instead of an unscoped query.
    """
    if is_platform_admin(user):
        requested_key = tenant_key(requested)
        if requested_key in ("", "all"):
            return None
        return normalize_tenant(requested)

    tenant = getattr(user, "tenant", None)
    if not tenant_key(tenant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not assigned to a tenant",
        )
    return tenant
```

`effective_tenant(user, requested)` remains as a backwards-compatible alias.

### 5.3 Usage in Services

```python
# app/services/log_service.py
async def get_logs(
    session: AsyncSession,
    user: TokenPayload,
    filters: LogFilters,
    requested_tenant: str | None = None
):
    tenant = resolve_read_tenant(user, requested_tenant)

    query = select(SecurityEvent)

    # None means "all tenants" (platform ADMIN only); every other account is
    # always constrained to its own tenant.
    if tenant is not None:
        query = query.where(SecurityEvent.tenant == tenant)

    # Apply other filters...
    return await paginate(session, query, filters)
```

### 5.4 Ingestion Tenant Binding

**API Key Ingestion:** Tenant is bound to the API key at configuration time.

```python
# app/core/dependencies.py
async def verify_api_key(
    request: Request,
    session: AsyncSession = Depends(get_session)
) -> TokenPayload:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Lookup API key in config (env-based) or database
    identity = settings.get_api_key_identity(api_key)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not identity.tenant:
        raise HTTPException(status_code=403, detail="API key not bound to tenant")
    
    return TokenPayload(
        userId=0,  # Synthetic user for API key
        username=identity.username or "api-key",
        email=identity.email or "api-key@local",
        tenant=identity.tenant,
        role="VIEWER"
    )
```

**Syslog Ingestion:** Tenant from `SYSLOG_TENANT` env var.

```python
# app/integrations/syslog.py
SYSLOG_CONTEXT = {
    "tenant": settings.SYSLOG_TENANT,
    "username": settings.SYSLOG_USERNAME,
}
```

### 5.5 IDOR Protection

All resource access by ID must verify tenant ownership for **both VIEWER and ADMIN**:

```python
# app/services/alert_service.py
async def get_alert_by_id(session: AsyncSession, alert_id: str, user: TokenPayload) -> Alert:
    query = select(Alert).where(Alert.id == alert_id)
    
    # Both VIEWER and ADMIN are scoped to their own tenant
    query = query.where(Alert.tenant == user.tenant)
    
    alert = await session.scalar(query)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return alert
```

---

## 6. Password Security

### 6.1 Hashing

```python
# app/core/security.py
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

- **Algorithm:** bcrypt
- **Cost Factor:** 12 (matches the legacy `bcryptjs` default)
- **Storage:** `User.password` column (String)

---

## 7. API Key Authentication

### 7.1 Configuration (Database-Backed)

API keys are stored in the `tenants` table with SHA-256 hashes. Each active tenant
has exactly one API key. Key verification:

```python
# app/core/dependencies.py
async def verify_api_key(request, session) -> TokenPayload:
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    result = await session.execute(
        select(Tenant).where(
            Tenant.api_key_hash == key_hash,
            Tenant.is_active == True
        )
    )
    tenant_row = result.scalar_one_or_none()

    if not tenant_row:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return TokenPayload(
        user_id=0,
        username=f"ingest-{tenant_row.name}",
        email=f"ingest-{tenant_row.name}@local",
        tenant=tenant_row.name,
        role="VIEWER",
    )
```

The `tenants` table schema:

| Column | Type | Constraints |
|--------|------|-------------|
| id | String(25) | PK |
| name | String(50) | UNIQUE, CHECK `^[a-z0-9_-]{2,50}$` AND name <> 'all' |
| api_key_hash | String(64) | UNIQUE NOT NULL |
| is_active | Boolean | DEFAULT true |
| created_at | DateTime(timezone) | DEFAULT now() |
| alert_webhook_url | String(500) | NULL |
| alert_emails | String[] | NULL |

### 7.2 Admin Tenant Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/tenants` | POST | Admin | Create tenant, returns API key once |
| `/api/tenants` | GET | Admin | List tenants (no keys/hashes exposed) |
| `/api/tenants/{name}` | PATCH | Admin | Activate/deactivate tenant |
| `/api/tenants/{name}/rotate-key` | POST | Admin | Rotate API key (old key invalidated) |
                        elif isinstance(value, dict):
                            return ApiKeyIdentity(
                                tenant=value.get("tenant", ""),
                                username=value.get("username"),
                                email=value.get("email")
                            )
            except json.JSONDecodeError:
                pass
        
        return None
```

### 7.2 Timing-Safe Comparison

Use `secrets.compare_digest()` for all key comparisons (same semantics as the legacy `crypto.timingSafeEqual`).

---

## 8. CORS & Cookie Security

### 8.1 CORS Configuration

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["http://localhost:5173", "https://app.example.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Cookie"],
    expose_headers=["Set-Cookie"],
)
```

### 8.2 Security Headers

```python
# app/main.py
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

if settings.APP_ENV == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

---

## 9. Rate Limiting

### 9.1 Ingestion Rate Limit

Ingestion endpoints use the shared in-process limiter in
`app/core/limiting.py`. The limiter keys on the SHA-256 of the presented
`X-API-Key`, falling back to the remote address when no key is present, so one
tenant cannot exhaust another tenant's budget behind a reverse proxy.

```python
# app/core/limiting.py
limiter = Limiter(key_func=ingest_rate_key)

# app/api/routes/ingest.py
@router.post("/ingest")
@limiter.limit(lambda: get_settings().INGEST_RATE_LIMIT)
async def ingest_single_event(request: Request, ...):
    ...
```

The same decorator is applied to `/api/ingest/batch`, `/api/ingest/file`, and
`/api/ingest/syslog`. The limit is configurable with `INGEST_RATE_LIMIT`
(default `600/minute`). Exceeded requests return HTTP 429 with `Retry-After`.

### 9.2 Auth-Specific Limits

| Endpoint | Limit |
|----------|-------|
| `POST /api/auth/login` | 5 req/min per IP |
| `POST /api/ingest`, `/api/ingest/batch`, `/api/ingest/file`, `/api/ingest/syslog` | `INGEST_RATE_LIMIT` (default 600/min) per API key |

---

## 10. Audit Logging (Future Enhancement)

Not present in the legacy implementation. Recommended for FastAPI:

```python
# Log admin actions
AUDIT_ACTIONS = {
    "user_create", "user_update", "user_delete",
    "rule_create", "rule_update", "rule_delete", "rule_enable",
    "alert_resolve",
    "config_change",
}

async def audit_log(action: str, user: TokenPayload, resource_id: str, details: dict):
    # Store in audit_log table or structured logging
    logger.info("audit", extra={
        "action": action,
        "user_id": user.userId,
        "user_email": user.email,
        "tenant": user.tenant,
        "resource_id": resource_id,
        "details": details,
    })
```

---

## 11. Secrets Management

### 11.1 Required Secrets

| Secret | Environment Variable | Rotation |
|--------|---------------------|----------|
| Access Token Secret | `ACCESS_TOKEN_SECRET` | Annual |
| Refresh Token Secret | `REFRESH_TOKEN_SECRET` | Annual |
| Database Password | `POSTGRES_PASSWORD` | Per policy |
| Redis Password | `REDIS_PASSWORD` | Per policy |
| SMTP Password | `SMTP_PASSWORD` | Per policy |
| Ingest API Key | `INGEST_API_KEY` | Quarterly |

### 11.2 Email Configuration

Use **separate feature toggles** for each email type. All can share the same SMTP sender but are independently enabled/disabled.

| Feature | Environment Variable | Default |
|---------|---------------------|---------|
| SMTP Enabled (master switch) | `SMTP_ENABLED` | `false` |
| OTP Email Enabled | `OTP_EMAIL_ENABLED` | `true` |
| Alert Email Enabled | `ALERT_EMAIL_ENABLED` | `true` |

SMTP credentials (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`) are required only if `SMTP_ENABLED=true`.

### 11.2 Production Requirements

- Use secret manager (AWS Secrets Manager, HashiCorp Vault, Doppler)
- Inject at container startup
- Never commit to git
- Rotate on schedule

---

## 12. Compliance Checklist

| Requirement | Implementation |
|-------------|----------------|
| Passwords never logged | `User.password` excluded from all responses |
| Tokens in HttpOnly cookies | `httponly=True` on both cookies |
| Secure cookies in production | `COOKIE_SECURE=true` |
| SameSite protection | `COOKIE_SAME_SITE=none` (cross-origin) / `lax` (same-origin) |
| Timing-safe key comparison | `secrets.compare_digest()` |
| Bcrypt cost ≥ 12 | `bcrypt.gensalt(12)` |
| Login rate limiting | 5 req/min per IP (enforced by middleware/slowapi) |
| Refresh token rotation | New refresh token issued on each refresh |
| Tenant isolation enforced | All queries scoped by user.tenant for VIEWER and ADMIN |
| IDOR protection | All ID-based lookups verify tenant ownership for VIEWER and ADMIN |
| CORS restricted | `allow_origins` from config, `allow_credentials=True` |

---

**End of Security Design**