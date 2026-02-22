-- Migration: add_pre_bid_signal

CREATE TABLE "pre_bid_signals" (
    "id" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "external_id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "estimated_amt" BIGINT,
    "region" TEXT,
    "estimated_at" TIMESTAMP(3),
    "is_estimate" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "pre_bid_signals_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "pre_bid_signals_source_external_id_key" ON "pre_bid_signals"("source", "external_id");
