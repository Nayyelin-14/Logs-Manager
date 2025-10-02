/*
  Warnings:

  - You are about to drop the column `condition` on the `alert_rules` table. All the data in the column will be lost.
  - You are about to drop the column `threshold` on the `alert_rules` table. All the data in the column will be lost.
  - You are about to drop the column `windowSeconds` on the `alert_rules` table. All the data in the column will be lost.
  - Added the required column `conditions` to the `alert_rules` table without a default value. This is not possible if the table is not empty.
  - Added the required column `severity` to the `alerts` table without a default value. This is not possible if the table is not empty.
  - Added the required column `title` to the `alerts` table without a default value. This is not possible if the table is not empty.

*/
-- DropIndex
DROP INDEX "public"."alerts_tenant_idx";

-- AlterTable
ALTER TABLE "public"."alert_rules" DROP COLUMN "condition",
DROP COLUMN "threshold",
DROP COLUMN "windowSeconds",
ADD COLUMN     "conditions" JSONB NOT NULL,
ADD COLUMN     "enabled" BOOLEAN NOT NULL DEFAULT true;

-- AlterTable
ALTER TABLE "public"."alerts" ADD COLUMN     "event_ids" TEXT[],
ADD COLUMN     "severity" TEXT NOT NULL,
ADD COLUMN     "status" TEXT NOT NULL DEFAULT 'open',
ADD COLUMN     "title" TEXT NOT NULL;

-- CreateIndex
CREATE INDEX "alerts_tenant_status_idx" ON "public"."alerts"("tenant", "status");
