-- Migration: add_proposal_draft

CREATE TABLE "proposal_drafts" (
    "id" TEXT NOT NULL,
    "organization_id" TEXT NOT NULL,
    "bid_notice_id" TEXT NOT NULL,
    "template_key" TEXT,
    "draft_key" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "proposal_drafts_pkey" PRIMARY KEY ("id")
);
