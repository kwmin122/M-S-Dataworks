#!/bin/bash
# TS-001 시나리오 E2E 검증 스크립트

set -e

SESSION_ID="ts001_$(date +%s)"
BASE_URL="http://localhost:8000"
RAG_URL="http://localhost:8001"

echo "=========================================="
echo "TS-001 E2E 검증 시작"
echo "Session ID: $SESSION_ID"
echo "=========================================="

# Step 1: 공고 업로드
echo -e "\n[Step 1] 공고 업로드..."
UPLOAD_TARGET=$(curl -s -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  "$BASE_URL/api/upload_target?session_id=$SESSION_ID")
echo "Response: $UPLOAD_TARGET"

# Step 2: 회사 문서 업로드
echo -e "\n[Step 2] 회사 문서 업로드..."
UPLOAD_COMPANY=$(curl -s -F "file=@data/company_docs/삼성SDS_회사소개서.pdf" \
  "$BASE_URL/api/upload_company?session_id=$SESSION_ID")
echo "Response: $UPLOAD_COMPANY"

# Step 3: 분석 실행
echo -e "\n[Step 3] 분석 실행..."
ANALYZE=$(curl -s -X POST "$BASE_URL/api/analyze?session_id=$SESSION_ID")
echo "Response: $ANALYZE"

# GO/NO-GO 점수 확인
SCORE=$(echo $ANALYZE | jq -r '.go_no_go_score // empty')
if [ ! -z "$SCORE" ]; then
  echo "✅ GO/NO-GO 점수: $SCORE"
  if [ $(echo "$SCORE >= 90" | bc) -eq 1 ]; then
    echo "✅ HIGH MATCH 확인 (90점 이상)"
  else
    echo "⚠️  예상보다 낮은 점수"
  fi
else
  echo "❌ GO/NO-GO 점수 없음"
fi

echo -e "\n=========================================="
echo "TS-001 E2E 검증 완료"
echo "=========================================="
