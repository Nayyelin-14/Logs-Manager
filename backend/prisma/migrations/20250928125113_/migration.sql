-- CreateEnum
CREATE TYPE "public"."Role" AS ENUM ('USER', 'ADMIN');

-- CreateEnum
CREATE TYPE "public"."Status" AS ENUM ('FREEZE', 'INACTIVE', 'ACTIVE');

-- CreateEnum
CREATE TYPE "public"."Action" AS ENUM ('ALLOW', 'DENY', 'CREATE', 'DELETE', 'LOGIN', 'LOGOUT', 'ALERT', 'QUARANTINE', 'CREATEUSER');

-- CreateEnum
CREATE TYPE "public"."Source" AS ENUM ('FIREWALL', 'CROWDSTRIKE', 'AWS', 'M365', 'AD', 'API', 'NETWORK');

-- CreateTable
CREATE TABLE "public"."User" (
    "id" SERIAL NOT NULL,
    "username" TEXT,
    "password" TEXT,
    "email" TEXT NOT NULL,
    "role" "public"."Role" NOT NULL DEFAULT 'USER',
    "tenant" TEXT,
    "status" "public"."Status" NOT NULL DEFAULT 'ACTIVE',
    "createAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."alert_rules" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "tenant" TEXT NOT NULL,
    "threshold" INTEGER NOT NULL,
    "windowSeconds" INTEGER DEFAULT 0,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "condition" TEXT NOT NULL,
    "actions" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "alert_rules_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."alerts" (
    "id" TEXT NOT NULL,
    "rule_id" TEXT NOT NULL,
    "tenant" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "triggeredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "alerts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."Otp" (
    "id" SERIAL NOT NULL,
    "email" TEXT NOT NULL,
    "optCode" TEXT NOT NULL,
    "rememberToken" TEXT NOT NULL,
    "verifyToken" TEXT,
    "count" SMALLINT NOT NULL DEFAULT 0,
    "error" SMALLINT NOT NULL DEFAULT 0,
    "createAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Otp_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "public"."security_logs" (
    "id" TEXT NOT NULL,
    "@timestamp" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "tenant" TEXT NOT NULL,
    "source" "public"."Source" NOT NULL,
    "vendor" TEXT,
    "product" TEXT,
    "event_type" TEXT NOT NULL,
    "event_subtype" TEXT,
    "severity" INTEGER DEFAULT 0,
    "action" "public"."Action",
    "src_ip" TEXT,
    "src_port" TEXT,
    "dst_ip" TEXT,
    "dst_port" TEXT,
    "protocol" TEXT,
    "host" TEXT,
    "process" TEXT,
    "url" TEXT,
    "http_method" TEXT,
    "status_code" INTEGER,
    "rule_name" TEXT,
    "rule_id" TEXT,
    "cloud_account_id" TEXT,
    "cloud_region" TEXT,
    "cloud_service" TEXT,
    "raw" JSONB NOT NULL,
    "_tags" TEXT[],
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "ip" TEXT,
    "user" TEXT,
    "description" TEXT,
    "eventId" INTEGER,
    "loginType" INTEGER,
    "priority" INTEGER,
    "sha256" TEXT,
    "status" TEXT,
    "interface" TEXT,
    "mac" TEXT,

    CONSTRAINT "security_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "public"."User"("email");

-- CreateIndex
CREATE INDEX "User_tenant_idx" ON "public"."User"("tenant");

-- CreateIndex
CREATE INDEX "User_role_idx" ON "public"."User"("role");

-- CreateIndex
CREATE INDEX "User_createAt_idx" ON "public"."User"("createAt");

-- CreateIndex
CREATE INDEX "User_status_idx" ON "public"."User"("status");

-- CreateIndex
CREATE INDEX "alerts_tenant_idx" ON "public"."alerts"("tenant");

-- CreateIndex
CREATE UNIQUE INDEX "Otp_email_key" ON "public"."Otp"("email");

-- CreateIndex
CREATE INDEX "security_logs_@timestamp_idx" ON "public"."security_logs"("@timestamp");

-- CreateIndex
CREATE INDEX "security_logs_tenant_@timestamp_idx" ON "public"."security_logs"("tenant", "@timestamp");

-- CreateIndex
CREATE INDEX "security_logs_source_@timestamp_idx" ON "public"."security_logs"("source", "@timestamp");

-- CreateIndex
CREATE INDEX "security_logs_event_type_idx" ON "public"."security_logs"("event_type");

-- CreateIndex
CREATE INDEX "security_logs_severity_idx" ON "public"."security_logs"("severity");

-- CreateIndex
CREATE INDEX "security_logs_tenant_user_idx" ON "public"."security_logs"("tenant", "user");

-- CreateIndex
CREATE INDEX "security_logs_tenant_src_ip_idx" ON "public"."security_logs"("tenant", "src_ip");

-- CreateIndex
CREATE INDEX "security_logs_src_ip_idx" ON "public"."security_logs"("src_ip");

-- CreateIndex
CREATE INDEX "security_logs_tenant_created_at_idx" ON "public"."security_logs"("tenant", "created_at" DESC);

-- CreateIndex
CREATE INDEX "security_logs_tenant_source_created_at_idx" ON "public"."security_logs"("tenant", "source", "created_at" DESC);

-- CreateIndex
CREATE INDEX "security_logs_tenant_action_created_at_idx" ON "public"."security_logs"("tenant", "action", "created_at" DESC);

-- CreateIndex
CREATE INDEX "security_logs_tenant_event_type_created_at_idx" ON "public"."security_logs"("tenant", "event_type", "created_at" DESC);

-- AddForeignKey
ALTER TABLE "public"."alerts" ADD CONSTRAINT "alerts_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "public"."alert_rules"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
