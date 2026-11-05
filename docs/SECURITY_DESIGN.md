# Security Design — Authentication, Authorization, and Tenant Isolation

**Version:** 1.0  
**Date:** 2026-11-03  
**Status:** Design Phase

---

## 1. Authentication Architecture

### 1.1 JWT Configuration (Exact Match to the Legacy Backend)

| Parameter | Value | Source |
|-----------|-------|--------|
| **Algorithm** | HS256 | `python-jose` default |
| **Access Token Secret** | `ACCESS_TOKEN_SECRET` env | 32+ char random |
| **Refresh Token Secret** | `REFRESH_TOKEN_SECRET` env | 32+ char random |
| **Access Token TTL** | 15 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| **Refresh Token TTL** | 30 days | `REFRESH_TOKEN_EXPIRE_DAYS` |
| **Token Payload** | `{ userId, username, email, tenant, role }` | Exact match |

### 1.2 JWT Payload Structure

```python
# app/core/security.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TokenPayload(BaseModel):
    userId: int
    username: Optional[str] = None
    email: str
    tenant: str
    role: str  # "VIEWER" or "ADMIN"
    exp: int
    iat: int
    type: str  # "access" or "refresh"
```

**Legacy Payload (for reference):**
```typescript
interface TokenPayload extends JwtPayload {
  userId: number;
  username: string;
  email: string;
  tenant: string;
  role: string;
}
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
    token_payload = payload.model_dump()
    token_payload.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "access",
    })
    return jwt.encode(token_payload, settings.ACCESS_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(payload: TokenPayload) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token_payload = payload.model_dump()
    token_payload.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "refresh",
    })
    return jwt.encode(token_payload, settings.REFRESH_TOKEN_SECRET, algorithm=settings.JWT_ALGORITHM)
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
from fastapi import Depends, Request, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_token, create_access_token, create_refresh_token
from app.core.config import settings
from app.models.user import User
from app.core.database import get_session

async def get_current_user(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session)
) -> TokenPayload:
    """
    Validates access token. If expired, attempts refresh using refresh token cookie.
    Returns TokenPayload with user info.
    """
    access_token = request.cookies.get("accessToken")
    refresh_token = request.cookies.get("refreshToken")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated user. Try Again!!!",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Try access token first
    if access_token:
        try:
            payload = decode_token(access_token, settings.ACCESS_TOKEN_SECRET)
            return TokenPayload(**payload)
        except jwt.ExpiredSignatureError:
            pass  # Fall through to refresh
        except jwt.JWTError:
            pass  # Fall through to refresh
    
    # Access token missing or invalid → try refresh token
    try:
        payload = decode_token(refresh_token, settings.REFRESH_TOKEN_SECRET)
        # Verify user still exists and is active
        user = await session.get(User, payload["userId"])
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=401, detail="Account not active")
        
        # Issue new tokens
        new_payload = TokenPayload(
            userId=user.id,
            username=user.username,
            email=user.email,
            tenant=user.tenant,
            role=user.role
        )
        new_access = create_access_token(new_payload)
        new_refresh = create_refresh_token(new_payload)
        
        set_auth_cookies(response, new_access, new_refresh)
        return new_payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token refresh failed")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Token refresh failed")
```

---

## 3. OTP Authentication

### 3.1 OTP Generation (Exact Match)

```python
# app/core/security.py
from crypto import random_bytes

def generate_otp() -> int:
    """6-digit OTP: (3 random bytes as hex) % 900000 + 100000"""
    return (int.from_bytes(random_bytes(3), "big") % 900000) + 100000

def generate_token() -> str:
    """32-byte hex token for OTP verification"""
    return random_bytes(32).hex()
```

### 3.2 OTP Storage

| Field | Type | Description |
|-------|------|-------------|
| `email` | String (unique) | User email |
| `opt_code` | String | Bcrypt-hashed OTP |
| `remember_token` | String | 32-byte hex, sent to frontend |
| `verify_token` | String | Set after OTP verified |
| `count` | SmallInt | OTP request count today |
| `error` | SmallInt | Failed verification count today |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

### 3.3 OTP Verification Flow

```
POST /api/auth/register (username, email, tenant)
    │
    ▼
Generate OTP + hash (bcrypt) + remember_token
    │
    ▼
Store in Otp table (count=1, error=0)
    │
    ▼
Queue OTP email (arq job)
    │
    ▼
Return { message, userData: OtpRecord, tenant, username, token: remember_token }

---

POST /api/auth/verify-Otp (username, email, tenant, otp, token)
    │
    ▼
Validate token matches remember_token
    │
    ▼
Check OTP not expired (2 min)
    │
    ▼
Verify OTP (bcrypt compare)
    │
    ▼
On success: generate verify_token, reset count/error
    │
    ▼
Return { isSuccess: true, token: verify_token }

---

POST /api/auth/confirm-password (email, username, tenant, password, confirmPassword, token)
    │
    ▼
Validate token matches verify_token
    │
    ▼
Check not expired (10 min)
    │
    ▼
Hash password (bcrypt)
    │
    ▼
Create User record
    │
    ▼
Issue access + refresh tokens, set cookies
    │
    ▼
Return { message, userId, userData: UserPublic }
```

---

## 4. Role-Based Access Control

### 4.1 Role Mapping

| Prisma Role | Assignment Role | Description |
|-------------|-----------------|-------------|
| `USER` | VIEWER | Read-only access to own tenant |
| `ADMIN` | ADMIN | Administrative access within their own tenant |

**No code changes needed** — the role values `USER` and `ADMIN` are used directly in authorization checks. The assignment's "VIEWER" concept maps to existing `USER` role.

**Critical**: ADMIN does **not** automatically have access to all tenants. Cross-tenant access is prohibited unless a separate platform-level role is introduced (not in current scope).

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

### 4.3 Endpoint Protection Matrix

| Endpoint | Required Dependency | Notes |
|----------|---------------------|-------|
| `POST /api/auth/login` | None | Public |
| `POST /api/auth/register` | None | Public |
| `POST /api/auth/verify-Otp` | None | Public |
| `POST /api/auth/confirm-password` | None | Public |
| `POST /api/auth/logout` | `get_current_user` | Authenticated |
| `GET /api/auth/auth-check` | `get_current_user` | Authenticated |
| `POST /api/ingest` | `verify_api_key` OR `get_current_user` | API key or user |
| `POST /api/ingest/batch` | `verify_api_key` OR `get_current_user` | API key or user |
| `GET /api/get-logs` | `get_current_user` | VIEWER+ (tenant-scoped) |
| `DELETE /api/delete-log/:id` | `require_admin` | Admin only (own tenant) |
| `GET /api/dashboard` | `get_current_user` | VIEWER+ (tenant-scoped) |
| `GET /api/user-dashboard/:id` | `require_viewer` | Viewer only (own tenant) |
| `GET /api/get-alerts` | `get_current_user` | VIEWER+ (tenant-scoped) |
| `PATCH /api/alerts/:id` | `require_admin` | Admin only (own tenant) |
| `GET /api/get-rules` | `require_admin` | Admin only (own tenant) |
| `POST /api/create-alertRule` | `require_admin` | Admin only (own tenant) |
| `PUT /api/update-rule/:id` | `require_admin` | Admin only (own tenant) |
| `PATCH /api/rules/:id/enabled` | `require_admin` | Admin only (own tenant) |
| `DELETE /api/delete-rule/:id` | `require_admin` | Admin only (own tenant) |
| `GET /api/get-users` | `require_admin` | Admin only (own tenant) |
| `POST /api/create-user` | `require_admin` | Admin only (own tenant) |
| `PUT /api/update-user` | `require_admin` | Admin only (own tenant) |
| `DELETE /api/delete-user/:id` | `require_admin` | Admin only (own tenant) |
| `GET /api/get-all-data` | `require_admin` | Admin only (own tenant) |

---

## 5. Tenant Isolation

### 5.1 Core Principle

**Never trust tenant identifiers from VIEWER requests.** Tenant is always derived from the authenticated user's identity.

### 5.2 Tenant Resolution Logic

```python
# app/core/dependencies.py
from fastapi import Depends
from app.models.user import User

async def get_user_tenant(current_user: TokenPayload = Depends(get_current_user)) -> str:
    """
    Returns the tenant for the current user.
    Always returns the authenticated user's tenant.
    """
    return current_user.tenant

async def get_effective_tenant(
    current_user: TokenPayload = Depends(get_current_user),
    requested_tenant: str | None = None
) -> str:
    """
    Resolves effective tenant for query filtering.
    - VIEWER (USER): always user.tenant (ignores requested_tenant)
    - ADMIN: always user.tenant (ignores requested_tenant)
    - Cross-tenant access: PROHIBITED by default
    
    If cross-tenant access is needed in future, introduce a separate
    platform-level role (e.g., SUPER_ADMIN) with explicit authorization.
    """
    # Both VIEWER and ADMIN are scoped to their own tenant
    return current_user.tenant
```

### 5.3 Usage in Services

```python
# app/services/log_service.py
async def get_logs(
    session: AsyncSession,
    user: TokenPayload,
    filters: LogFilters,
    requested_tenant: str | None = None
):
    tenant = get_effective_tenant(user, requested_tenant)
    
    query = select(SecurityEvent)
    
    # tenant is ALWAYS set (either user's tenant)
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

### 7.1 Configuration (Environment-Based)

```python
# app/core/config.py
class Settings(BaseSettings):
    INGEST_API_KEY: str
    INGEST_API_TENANT: str = "demoA"
    INGEST_API_USERNAME: str = "log-forwarder"
    INGEST_API_KEYS: str = ""  # JSON: {"key1": "tenantA", "key2": {"tenant": "tenantB", "username": "aws"}}
    
    def get_api_key_identity(self, provided_key: str) -> ApiKeyIdentity | None:
        # Check single key
        if secrets.compare_digest(provided_key, self.INGEST_API_KEY):
            return ApiKeyIdentity(
                tenant=self.INGEST_API_TENANT,
                username=self.INGEST_API_USERNAME,
                email=f"{self.INGEST_API_USERNAME}@local"
            )
        
        # Check multiple keys JSON
        if self.INGEST_API_KEYS:
            try:
                keys = json.loads(self.INGEST_API_KEYS)
                for key, value in keys.items():
                    if secrets.compare_digest(provided_key, key):
                        if isinstance(value, str):
                            return ApiKeyIdentity(tenant=value)
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

### 9.1 Global Rate Limit (ported from the legacy `rateLimit` middleware)

```python
# app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to all /api routes
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api"):
        # Check rate limit
        pass
    return await call_next(request)
```

**Note:** Use `slowapi` for FastAPI rate limiting. Configure per-endpoint limits for auth endpoints.

### 9.2 Auth-Specific Limits

| Endpoint | Limit |
|----------|-------|
| `POST /api/auth/login` | 5 req/min per IP |
| `POST /api/auth/register` | 3 req/min per IP |
| `POST /api/auth/verify-Otp` | 10 req/min per IP |
| `POST /api/ingest` | 100 req/min per API key |

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
| OTP rate limiting | Max 3 requests/day, 5 errors/day lockout |
| Refresh token rotation | New refresh token issued on each refresh |
| Tenant isolation enforced | All queries scoped by user.tenant for VIEWER and ADMIN |
| IDOR protection | All ID-based lookups verify tenant ownership for VIEWER and ADMIN |
| CORS restricted | `allow_origins` from config, `allow_credentials=True` |

---

**End of Security Design**