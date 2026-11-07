# Neon Database Schema Compatibility Report

**Date:** 2024-11-04  
**Database:** Neon PostgreSQL (ep-jolly-tooth-b3usyykj-pooler.c-4.ap-southeast-1.aws.neon.tech)  
**Inspection Method:** Read-only queries against `information_schema` and `pg_catalog`

---

## 1. Actual Database Schema (Physical)

### Tables
| Table Name | Type |
|------------|------|
| `Otp` | User table (mixed case) |
| `User` | User table (mixed case) |
| `_prisma_migrations` | Prisma metadata |
| `alert_rules` | Alert rules (snake_case) |
| `alerts` | Alerts (snake_case) |
| `security_logs` | Security events (snake_case) |

---

### Column Comparison: SQLAlchemy Model vs Actual DB

#### **User** (table: `"User"`)

| Model Attribute | DB Column | Match |
|-----------------|-----------|-------|
| `id` | `id` | ✅ |
| `username` | `username` | ✅ |
| `email` | `email` | ✅ |
| `password` | `password` | ✅ |
| `role` | `role` (enum `Role`) | ✅ |
| `tenant` | `tenant` | ✅ |
| `status` | `status` (enum `Status`) | ✅ |
| `create_at` → `createAt` | `createAt` | ✅ (model maps correctly) |
| `updated_at` → `updatedAt` | `updatedAt` | ✅ (model maps correctly) |

**Indexes (DB):** `User_pkey`, `User_email_key`, `User_tenant_idx`, `User_role_idx`, `User_createAt_idx`, `User_status_idx`  
**Model Indexes:** `ix_User_tenant`, `ix_User_role`, `ix_User_create_at`, `ix_User_status` → **MISMATCH** (model uses `create_at`)

---

#### **Otp** (table: `"Otp"`)

| Model Attribute | DB Column | Match |
|-----------------|-----------|-------|
| `id` | `id` | ✅ |
| `email` | `email` | ✅ |
| `opt_code` → `optCode` | `optCode` | ✅ |
| `remember_token` → `rememberToken` | `rememberToken` | ✅ |
| `verify_token` → `verifyToken` | `verifyToken` | ✅ |
| `count` | `count` | ✅ |
| `error` | `error` | ✅ |
| `create_at` → `createAt` | `createAt` | ✅ |
| `updated_at` → `updatedAt` | `updatedAt` | ✅ |

**Indexes (DB):** `Otp_pkey`, `Otp_email_key`  
**Model Indexes:** `ix_Otp_email` → **MISMATCH** (DB uses `Otp_email_key`)

---

#### **alert_rules** (table: `alert_rules`)

| Model Attribute | DB Column | Match |
|-----------------|-----------|-------|
| `id` | `id` | ✅ |
| `name` | `name` | ✅ |
| `description` | `description` | ✅ |
| `tenant` | `tenant` | ✅ |
| `conditions` | `conditions` (jsonb) | ✅ |
| `enabled` | `enabled` | ✅ |
| `severity` | `severity` | ✅ |
| `created_at` → `createdAt` | `createdAt` | ✅ |
| `updated_at` → `updatedAt` | `updatedAt` | ✅ |

**Indexes (DB):** `alert_rules_pkey` only  
**Model Indexes:** None defined → **OK** (no indexes expected)

---

#### **alerts** (table: `alerts`)

| Model Attribute | DB Column | Match |
|-----------------|-----------|-------|
| `id` | `id` | ✅ |
| `rule_id` → `ruleId` | `rule_id` | ❌ **MISMATCH** (DB uses `rule_id`, model uses `ruleId`) |
| `tenant` | `tenant` | ✅ |
| `description` | `description` | ✅ |
| `triggered_at` → `triggeredAt` | `triggeredAt` | ✅ |
| `event_ids` | `event_ids` | ✅ |
| `severity` | `severity` | ✅ |
| `status` | `status` | ✅ |
| `title` | `title` | ✅ |
| `dedupe_key` → `dedupeKey` | `dedupe_key` | ❌ **MISMATCH** (DB uses `dedupe_key`, model uses `dedupeKey`) |

**Indexes (DB):** `alerts_pkey`, `alerts_tenant_status_idx`, `alerts_rule_id_dedupe_key_triggeredAt_idx`  
**Model Indexes:** `ix_alerts_tenant_status`, `ix_alerts_rule_dedupe_triggered` → **PARTIAL MISMATCH**

---

#### **security_logs** (table: `security_logs`)

| Model Attribute | DB Column | Match |
|-----------------|-----------|-------|
| `id` | `id` | ✅ |
| `timestamp` → `@timestamp` | `@timestamp` | ✅ |
| `tenant` | `tenant` | ✅ |
| `source` | `source` (enum) | ✅ |
| `vendor` | `vendor` | ✅ |
| `product` | `product` | ✅ |
| `event_type` → `eventType` | `event_type` | ❌ **MISMATCH** |
| `canonical_event_type` → `canonicalEventType` | `canonical_event_type` | ❌ **MISMATCH** |
| `original_event_type` → `originalEventType` | `original_event_type` | ❌ **MISMATCH** |
| `event_subtype` → `eventSubtype` | `event_subtype` | ❌ **MISMATCH** |
| `severity` | `severity` | ✅ |
| `action` | `action` | ✅ |
| `src_ip` → `srcIp` | `src_ip` | ❌ **MISMATCH** |
| `src_port` → `srcPort` | `src_port` | ❌ **MISMATCH** |
| `dst_ip` → `dstIp` | `dst_ip` | ❌ **MISMATCH** |
| `dst_port` → `dstPort` | `dst_port` | ❌ **MISMATCH** |
| `protocol` | `protocol` | ✅ |
| `user` | `user` | ✅ |
| `host` | `host` | ✅ |
| `process` | `process` | ✅ |
| `url` | `url` | ✅ |
| `http_method` → `httpMethod` | `http_method` | ❌ **MISMATCH** |
| `status_code` → `statusCode` | `status_code` | ❌ **MISMATCH** |
| `rule_name` → `ruleName` | `rule_name` | ❌ **MISMATCH** |
| `rule_id` → `ruleId` | `rule_id` | ❌ **MISMATCH** |
| `cloud_account_id` → `cloudAccountId` | `cloud_account_id` | ❌ **MISMATCH** |
| `cloud_region` → `cloudRegion` | `cloud_region` | ❌ **MISMATCH** |
| `cloud_service` → `cloudService` | `cloud_service` | ❌ **MISMATCH** |
| `raw` | `raw` (jsonb) | ✅ |
| `tags` → `_tags` | `_tags` | ❌ **MISMATCH** |
| `created_at` → `createdAt` | `created_at` | ❌ **MISMATCH** |
| `updated_at` → `updatedAt` | `updated_at` | ❌ **MISMATCH** |
| `ip` | `ip` | ✅ |
| `description` | `description` | ✅ |
| `event_id` → `eventId` | `eventId` | ❌ **MISMATCH** |
| `login_type` → `loginType` | `loginType` | ❌ **MISMATCH** |
| `priority` | `priority` | ✅ |
| `sha256` | `sha256` | ✅ |
| `status` | `status` | ✅ |
| `interface` | `interface` | ✅ |
| `mac` | `mac` | ✅ |
| `canonical_event_type` | `canonical_event_type` | ✅ (DB has both) |
| `original_event_type` | `original_event_type` | ✅ (DB has both) |
| `ingested_at` → `ingestedAt` | *missing* | ❌ **MISSING** |

**Indexes (DB - 14 indexes):**
- `security_logs_pkey`
- `security_logs_@timestamp_idx`
- `security_logs_tenant_@timestamp_idx`
- `security_logs_source_@timestamp_idx`
- `security_logs_event_type_idx`
- `security_logs_severity_idx`
- `security_logs_tenant_user_idx`
- `security_logs_tenant_src_ip_idx`
- `security_logs_src_ip_idx`
- `security_logs_tenant_created_at_idx`
- `security_logs_tenant_source_created_at_idx`
- `security_logs_tenant_action_created_at_idx`
- `security_logs_tenant_event_type_created_at_idx`
- `security_logs_canonical_event_type_idx`
- `security_logs_tenant_canonical_event_type_created_at_idx`

**Model Indexes (15):**
- Uses camelCase column names in index definitions → **MISMATCH** with DB snake_case indexes

---

### **Email Notifications** table: **MISSING** from DB
- Table `email_notifications` does not exist in DB
- Required for email notification tracking feature

---

## 2. Summary of Incompatibilities

### Critical (Block Phase 3)
| Issue | Table | Impact |
|-------|-------|--------|
| `rule_id` vs `ruleId` | `alerts` | Model uses `ruleId`, DB has `rule_id` |
| `dedupe_key` vs `dedupeKey` | `alerts` | Model uses `dedupeKey`, DB has `dedupe_key` |
| `event_type` vs `eventType` | `security_logs` | Model uses `eventType`, DB has `event_type` |
| `canonical_event_type` vs `canonicalEventType` | `security_logs` | Model uses `canonicalEventType`, DB has `canonical_event_type` |
| `src_ip` vs `srcIp` | `security_logs` | Model uses `srcIp`, DB has `src_ip` |
| `created_at` vs `createdAt` | `security_logs` | Model uses `createdAt`, DB has `created_at` |
| `ingested_at` missing | `security_logs` | Column missing entirely |
| `email_notifications` table | Missing | Table doesn't exist |

### Index Mismatches
| Model Index | DB Index | Status |
|-------------|----------|--------|
| `ix_User_create_at` | `User_createAt_idx` | Mismatch |
| `ix_Otp_email` | `Otp_email_key` | Mismatch |
| `ix_alerts_rule_dedupe_triggered` | `alerts_rule_id_dedupe_key_triggeredAt_idx` | Mismatch |
| 15 security_logs indexes | 14 DB indexes | Multiple mismatches |

---

## 3. Recommendations for Phase 3

### Option A: Keep DB as-is, Fix SQLAlchemy Models
- Map all model columns to actual DB column names (snake_case where DB has snake_case)
- Add missing `ingested_at` column via migration (requires approval)
- Create `email_notifications` table via migration
- Fix all index definitions to match actual DB indexes

### Option B: Migrate DB to Match Models
- Requires ALTER TABLE operations (NOT ALLOWED per restrictions)
- Would rename all snake_case columns to camelCase

**Decision:** Must use **Option A** - adapt models to match existing DB schema.

---

## 4. Files Requiring Changes for Schema Compatibility

### Models to Fix
1. `app/models/alert.py` - Fix `Alert` column mappings (`rule_id`, `triggeredAt`, `dedupe_key`)
2. `app/models/security_event.py` - Fix all snake_case column mappings
3. `app/models/user.py` - Fix index names
4. `app/models/otp.py` - Fix index name
5. Add `email_notifications` table migration (when approved)

### Index Definitions to Fix
- All index column references must use actual DB column names

---

## 5. Action Plan for Phase 3

1. **Immediate**: Fix SQLAlchemy models to match actual DB schema (read-only)
2. **After approval**: Create migrations for missing `ingested_at` column and `email_notifications` table
3. Implement API endpoints using corrected models

---

**End of Schema Compatibility Report**