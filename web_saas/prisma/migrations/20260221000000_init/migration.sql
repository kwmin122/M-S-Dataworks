-- Migration: init
-- 베이스 테이블 초기 생성
-- 이후 마이그레이션이 추가하는 테이블(proposal_drafts, pre_bid_signals, users)과
-- FTS 컬럼(attachment_tsv)은 제외

-- ── Enum 타입 ──────────────────────────────────────────────────────────────

CREATE TYPE "IngestionJobStatus" AS ENUM (
  'NEW', 'FETCH_ERROR', 'PARSE_ERROR', 'COMPLETED', 'RETRY_EXHAUSTED'
);

CREATE TYPE "EvaluationJobStatus" AS ENUM (
  'PENDING', 'SCORED', 'SCORE_ERROR', 'QUOTA_EXCEEDED',
  'NOTIFIED', 'NOTIFY_ERROR', 'RETRY_EXHAUSTED'
);

CREATE TYPE "BidInterestStatus" AS ENUM ('STARRED', 'ARCHIVED');

CREATE TYPE "PlanTier" AS ENUM ('FREE', 'PRO');

-- ── organizations ──────────────────────────────────────────────────────────

CREATE TABLE "organizations" (
    "id"             TEXT NOT NULL,
    "name"           TEXT NOT NULL,
    "company_facts"  JSONB NOT NULL,
    "interest_config" JSONB,
    "created_at"     TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"     TIMESTAMP(3) NOT NULL,
    CONSTRAINT "organizations_pkey" PRIMARY KEY ("id")
);

-- ── subscriptions ──────────────────────────────────────────────────────────

CREATE TABLE "subscriptions" (
    "id"                   TEXT NOT NULL,
    "organization_id"      TEXT NOT NULL,
    "plan"                 "PlanTier" NOT NULL DEFAULT 'FREE',
    "status"               TEXT NOT NULL,
    "stripe_sub_id"        TEXT,
    "current_period_start" TIMESTAMP(3) NOT NULL,
    "current_period_end"   TIMESTAMP(3) NOT NULL,
    "created_at"           TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"           TIMESTAMP(3) NOT NULL,
    CONSTRAINT "subscriptions_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "subscriptions_organization_id_key" ON "subscriptions"("organization_id");

ALTER TABLE "subscriptions"
  ADD CONSTRAINT "subscriptions_organization_id_fkey"
  FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE;

-- ── usage_quotas ───────────────────────────────────────────────────────────

CREATE TABLE "usage_quotas" (
    "id"              TEXT NOT NULL,
    "organization_id" TEXT NOT NULL,
    "period_start"    TIMESTAMP(3) NOT NULL,
    "used_count"      INTEGER NOT NULL DEFAULT 0,
    "max_count"       INTEGER NOT NULL,
    "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"      TIMESTAMP(3) NOT NULL,
    CONSTRAINT "usage_quotas_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "usage_quotas_organization_id_period_start_key"
  ON "usage_quotas"("organization_id", "period_start");

-- ── bid_notices ────────────────────────────────────────────────────────────
-- attachment_tsv 컬럼은 20260222000000_fts_attachment_gin 마이그레이션에서 추가

CREATE TABLE "bid_notices" (
    "id"              TEXT NOT NULL,
    "source"          TEXT NOT NULL,
    "external_id"     TEXT NOT NULL,
    "title"           TEXT NOT NULL,
    "category"        TEXT,
    "region"          TEXT,
    "url"             TEXT,
    "published_at"    TIMESTAMP(3),
    "deadline_at"     TIMESTAMP(3),
    "estimated_amt"   BIGINT,
    "attachment_text" TEXT,
    "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "bid_notices_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "bid_notices_source_external_id_key"
  ON "bid_notices"("source", "external_id");

-- ── ingestion_jobs ─────────────────────────────────────────────────────────

CREATE TABLE "ingestion_jobs" (
    "id"                TEXT NOT NULL,
    "bid_notice_id"     TEXT NOT NULL,
    "status"            "IngestionJobStatus" NOT NULL DEFAULT 'NEW',
    "idempotency_key"   TEXT NOT NULL,
    "provisional_hash"  TEXT NOT NULL,
    "content_hash"      TEXT,
    "attachment_url"    TEXT,
    "retry_count"       INTEGER NOT NULL DEFAULT 0,
    "locked_at"         TIMESTAMP(3),
    "lock_owner"        TEXT,
    "next_retry_at"     TIMESTAMP(3),
    "created_at"        TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"        TIMESTAMP(3) NOT NULL,
    CONSTRAINT "ingestion_jobs_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "ingestion_jobs_idempotency_key_key"
  ON "ingestion_jobs"("idempotency_key");

CREATE INDEX "ingestion_jobs_status_locked_at_next_retry_at_idx"
  ON "ingestion_jobs"("status", "locked_at", "next_retry_at");

ALTER TABLE "ingestion_jobs"
  ADD CONSTRAINT "ingestion_jobs_bid_notice_id_fkey"
  FOREIGN KEY ("bid_notice_id") REFERENCES "bid_notices"("id") ON DELETE CASCADE;

-- ── evaluation_jobs ────────────────────────────────────────────────────────

CREATE TABLE "evaluation_jobs" (
    "id"                 TEXT NOT NULL,
    "organization_id"    TEXT NOT NULL,
    "bid_notice_id"      TEXT NOT NULL,
    "status"             "EvaluationJobStatus" NOT NULL DEFAULT 'PENDING',
    "idempotency_key"    TEXT NOT NULL,
    "notice_revision"    TEXT NOT NULL,
    "evaluation_reason"  TEXT NOT NULL,
    "is_eligible"        BOOLEAN,
    "details"            JSONB,
    "action_plan"        TEXT,
    "quota_consumed"     BOOLEAN NOT NULL DEFAULT false,
    "retry_count"        INTEGER NOT NULL DEFAULT 0,
    "locked_at"          TIMESTAMP(3),
    "lock_owner"         TEXT,
    "next_retry_at"      TIMESTAMP(3),
    "created_at"         TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"         TIMESTAMP(3) NOT NULL,
    CONSTRAINT "evaluation_jobs_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "evaluation_jobs_idempotency_key_key"
  ON "evaluation_jobs"("idempotency_key");

CREATE INDEX "evaluation_jobs_organization_id_bid_notice_id_idx"
  ON "evaluation_jobs"("organization_id", "bid_notice_id");

CREATE INDEX "evaluation_jobs_status_locked_at_next_retry_at_idx"
  ON "evaluation_jobs"("status", "locked_at", "next_retry_at");

ALTER TABLE "evaluation_jobs"
  ADD CONSTRAINT "evaluation_jobs_organization_id_fkey"
  FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE;

ALTER TABLE "evaluation_jobs"
  ADD CONSTRAINT "evaluation_jobs_bid_notice_id_fkey"
  FOREIGN KEY ("bid_notice_id") REFERENCES "bid_notices"("id") ON DELETE CASCADE;

-- ── used_nonces ────────────────────────────────────────────────────────────

CREATE TABLE "used_nonces" (
    "id"         TEXT NOT NULL,
    "nonce"      TEXT NOT NULL,
    "expired_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "used_nonces_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "used_nonces_nonce_key" ON "used_nonces"("nonce");
CREATE INDEX "used_nonces_expired_at_idx" ON "used_nonces"("expired_at");

-- ── saved_searches ─────────────────────────────────────────────────────────

CREATE TABLE "saved_searches" (
    "id"              TEXT NOT NULL,
    "organization_id" TEXT NOT NULL,
    "name"            TEXT NOT NULL,
    "conditions"      JSONB NOT NULL,
    "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"      TIMESTAMP(3) NOT NULL,
    CONSTRAINT "saved_searches_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "saved_searches_organization_id_idx"
  ON "saved_searches"("organization_id");

ALTER TABLE "saved_searches"
  ADD CONSTRAINT "saved_searches_organization_id_fkey"
  FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE;

-- ── bid_interests ──────────────────────────────────────────────────────────

CREATE TABLE "bid_interests" (
    "id"              TEXT NOT NULL,
    "organization_id" TEXT NOT NULL,
    "bid_notice_id"   TEXT NOT NULL,
    "status"          "BidInterestStatus" NOT NULL DEFAULT 'STARRED',
    "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"      TIMESTAMP(3) NOT NULL,
    CONSTRAINT "bid_interests_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "bid_interests_organization_id_bid_notice_id_key"
  ON "bid_interests"("organization_id", "bid_notice_id");

ALTER TABLE "bid_interests"
  ADD CONSTRAINT "bid_interests_organization_id_fkey"
  FOREIGN KEY ("organization_id") REFERENCES "organizations"("id") ON DELETE CASCADE;

ALTER TABLE "bid_interests"
  ADD CONSTRAINT "bid_interests_bid_notice_id_fkey"
  FOREIGN KEY ("bid_notice_id") REFERENCES "bid_notices"("id") ON DELETE CASCADE;
