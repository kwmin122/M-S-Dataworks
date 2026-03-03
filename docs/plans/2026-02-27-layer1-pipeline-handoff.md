# Layer 1 학습 파이프라인 핸드오프

**작성일**: 2026-02-27
**목적**: 공공조달 제안서 작성의 보편적 법칙을 구조화된 지식으로 벡터DB에 저장

## 소스 현황

| 채널 | 수량 | 상태 |
|------|------|------|
| YouTube | 55편 (검증) + 10편 (수동 큐레이션) | URL 수집 완료 |
| 공식 문서 | 37건 + 2건 (수동 업로드 PDF) | URL/파일 수집 완료 |
| 블로그 | 58건 | URL 수집 완료, 추가 불필요 |

## 5단계 파이프라인

1. **소스 텍스트 수집**: youtube-transcript-api + Whisper, document_parser.py, trafilatura
2. **LLM Pass 1 — 지식 추출**: GPT-4o-mini, 7카테고리 JSON 추출
3. **LLM Pass 2 — 중복제거 + 모순 해소**: 3단계 (AGREE/CONDITIONAL/CONFLICT)
4. **벡터DB 구축**: ChromaDB 2-Collection (proposal_knowledge + proposal_templates)
5. **프롬프트 주입**: Layer 1 검색 → 프롬프트 어셈블리

## 기술 결정

- RAG over Fine-tuning (비용 1/10, 즉시 업데이트, 소스 추적)
- LLM: GPT-4o-mini (Pass 1+2 합산 $7)
- 임베딩: text-embedding-3-small (기존 engine.py와 동일)
- 소스 그레이드 가중치: S=4, A=3, B=2, C=1
- applicable_conditions 필수 (조건 없이 "항상 적용" 최소화)
- confidence 0.5 미만 자동 제거

## 파일 구조

```
data/layer1/
  sources/                ← 소스 URL/메타데이터 JSON
  raw_transcripts/        ← YouTube 자막 텍스트
  raw_documents/          ← 공식 문서 파싱 텍스트
  raw_blogs/              ← 블로그 본문 텍스트
  extracted/              ← Pass 1 결과 (knowledge.jsonl)
  refined/                ← Pass 2 결과 (knowledge_refined.jsonl)
  conflicts/              ← 모순 플래그 항목 (사람 리뷰용)

scripts/
  layer1_collect_youtube.py
  layer1_collect_blogs.py
  layer1_extract_knowledge.py
  layer1_refine_knowledge.py
  layer1_build_vectordb.py
  layer1_search_test.py
```

## 비용 추정

- YouTube 자막: 무료 (youtube-transcript-api)
- Whisper (자막 없는 10편): ~$2
- LLM Pass 1+2 (150만 토큰): ~$7
- 임베딩: ~$1
- **합계: $10 미만**

## 품질 기준

- confidence 0.5 미만 자동 제거
- applicable_conditions 필수
- 소스 역추적 가능 (source_url, source_title 보존)
- "제안서는 잘 써야 합니다" 같은 일반론 제거

## 검증 (나중)

- Golden Test 공고 10건 선정
- Layer 1 적용 전 vs 후 비교
- 목표: 커버리지 30%+ 향상, 치명적 실수 0건
