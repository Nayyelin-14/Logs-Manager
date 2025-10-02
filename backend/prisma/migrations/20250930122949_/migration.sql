/*
  Warnings:

  - You are about to drop the column `actions` on the `alert_rules` table. All the data in the column will be lost.
  - You are about to drop the column `enabled` on the `alert_rules` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "public"."alert_rules" DROP COLUMN "actions",
DROP COLUMN "enabled";
