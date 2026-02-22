-- Migration: fts_attachment_gin
-- 첨부파일 본문 FTS 인덱스 (한국어/영어 simple 사전 사용)

ALTER TABLE bid_notices
  ADD COLUMN IF NOT EXISTS attachment_tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(attachment_text, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS bid_notices_attachment_tsv_gin
  ON bid_notices USING GIN (attachment_tsv);
