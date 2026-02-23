/*
  Warnings:

  - You are about to drop the column `attachment_tsv` on the `bid_notices` table. All the data in the column will be lost.

*/
-- DropForeignKey
ALTER TABLE "bid_interests" DROP CONSTRAINT "bid_interests_bid_notice_id_fkey";

-- DropForeignKey
ALTER TABLE "bid_interests" DROP CONSTRAINT "bid_interests_organization_id_fkey";

-- DropForeignKey
ALTER TABLE "evaluation_jobs" DROP CONSTRAINT "evaluation_jobs_bid_notice_id_fkey";

-- DropForeignKey
ALTER TABLE "evaluation_jobs" DROP CONSTRAINT "evaluation_jobs_organization_id_fkey";

-- DropForeignKey
ALTER TABLE "ingestion_jobs" DROP CONSTRAINT "ingestion_jobs_bid_notice_id_fkey";

-- DropForeignKey
ALTER TABLE "saved_searches" DROP CONSTRAINT "saved_searches_organization_id_fkey";

-- DropForeignKey
ALTER TABLE "subscriptions" DROP CONSTRAINT "subscriptions_organization_id_fkey";

-- DropIndex
DROP INDEX "bid_notices_attachment_tsv_gin";

-- AlterTable
ALTER TABLE "bid_notices" DROP COLUMN "attachment_tsv";

-- AddForeignKey
ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ingestion_jobs" ADD CONSTRAINT "ingestion_jobs_bid_notice_id_fkey" FOREIGN KEY ("bid_notice_id") REFERENCES "bid_notices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "evaluation_jobs" ADD CONSTRAINT "evaluation_jobs_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "evaluation_jobs" ADD CONSTRAINT "evaluation_jobs_bid_notice_id_fkey" FOREIGN KEY ("bid_notice_id") REFERENCES "bid_notices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "saved_searches" ADD CONSTRAINT "saved_searches_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "bid_interests" ADD CONSTRAINT "bid_interests_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "bid_interests" ADD CONSTRAINT "bid_interests_bid_notice_id_fkey" FOREIGN KEY ("bid_notice_id") REFERENCES "bid_notices"("id") ON DELETE CASCADE ON UPDATE CASCADE;
