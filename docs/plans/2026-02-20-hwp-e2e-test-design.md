# HWP 공고문 E2E 테스트 설계

**날짜**: 2026-02-20
**목적**: 나라장터 HWP 공고문([9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역)을 실제 파이프라인으로 테스트

---

## 배경

- HWP 파일: `/Users/min-kyungwook/Downloads/[공고문] [9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역.hwp`
- 공고: 경기도고양교육지원청 제2026-69호
- 유형: 소액 수의계약 (43,417,000원)
- 핵심 자격: 엔지니어링사업(정보통신) 또는 기술사사무소(정보통신) 면허 + 고양·파주 소재지

---

## 아키텍처

```
HWP 공고문 파일
    ↓
document_parser._parse_hwp()   [신규] olefile + zlib + 레코드 파싱
    ↓
ParsedDocument (text ~9,000자)
    ↓
RFxAnalyzer.analyze(text)       [기존] GPT-4o-mini
    ↓
RFxAnalysisResult
  자격요건:
  - 엔지니어링사업(정보통신) 면허 → CUSTOM metric → LLM fallback
  - 주된 영업소 소재지 고양·파주  → CUSTOM metric → LLM fallback
  - 조달청 입찰참가자격등록        → CUSTOM metric → LLM fallback
    ↓
Company A txt ─┐
               ├── RAGEngine (별도 collection) → QualificationMatcher
Company B txt ─┘
    ↓
결과 출력 + reports/smoke_hwp_결과.json
```

---

## 컴포넌트

| 파일 | 변경 | 내용 |
|------|------|------|
| `document_parser.py` | 수정 | `_parse_hwp()` 추가, `parse()`에 `.hwp` 분기 |
| `tests/test_hwp_parser.py` | 신규 | HWP 파싱 단위 테스트 (LLM 미호출) |
| `testdata/company_a_goyang.txt` | 신규 | 고양시 소재 + 정보통신 면허 보유 (적격) |
| `testdata/company_b_seoul.txt` | 신규 | 서울 소재 + 면허 없음 (비적격) |
| `scripts/smoke_test_hwp_rfx.py` | 신규 | 전체 파이프라인 E2E 실행 |

---

## HWP 파서 기술 세부

**포맷**: HWP 5.x = OLE Compound Document
- 스트림 경로: `BodyText/Section0`
- 압축: `zlib.decompress(data, -15)` (raw deflate, 헤더 없음)
- 레코드 구조: 4바이트 태그 (type = bits[0:9], size = bits[20:31])
- 텍스트 레코드: type == 67 (HWPTAG_PARA_TEXT) → UTF-16-LE 디코딩
- 가비지 필터: 한글/영문/숫자/공통 기호 외 문자 정규식 제거

**검증 완료**: olefile로 9,049자 추출 성공, 공고문 내용 정상 확인.

---

## 더미 회사 프로필

### Company A (적격)
- 상호: (주)고양정보통신엔지니어링
- 소재지: 경기도 고양시 일산서구 대화동 123-45
- 면허: 엔지니어링산업진흥법에 의한 엔지니어링사업(정보통신) 신고번호 IT-2018-045231
- 실적: 학교 무선네트워크 감리용역 3건 (2023, 2024, 2025년 완료)
- 조달청: 입찰참가자격 등록번호 20180451234

### Company B (비적격)
- 상호: (주)서울아이티컨설팅
- 소재지: 서울특별시 강남구 테헤란로 123
- 면허: 없음 (IT 컨설팅 사업만 운영)
- 실적: IT 컨설팅 프로젝트 5억원 수행
- 조달청: 미등록

---

## 기대 결과

| 요건 | Company A (고양시) | Company B (서울) |
|------|-------------------|-----------------|
| 엔지니어링(정보통신) 면허 | MET | NOT_MET |
| 소재지 고양·파주 | MET | NOT_MET |
| 조달청 입찰자격등록 | MET | NOT_MET |
| **종합** | **적격** | **비적격** |

---

## 주의사항

1. `.env` 파일에 `OPENAI_API_KEY` 필요 (실제 LLM 호출)
2. 이 문서의 자격요건은 금액 기준 없음 → ConstraintEvaluator CUSTOM 경로 테스트
3. HWP 파서는 HWP 5.x 전용 (HWP 3.x, HWPX는 별도 처리 필요)
