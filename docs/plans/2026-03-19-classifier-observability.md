# Classifier Observability & Regression Corpus

## 1. Structured Log Format

분류 이벤트는 `package_classifier.py` logger에 기록됩니다.

```
Package classified: domain=service method=negotiated confidence=0.85 items=15
Private contract/quotation detected → classified as pq (not negotiated)
```

### 추가 관찰용 SQL 쿼리

```sql
-- 분류 결과 분포 (domain × method)
SELECT
  detail_json->>'procurement_domain' as domain,
  detail_json->>'contract_method' as method,
  count(*)
FROM audit_logs
WHERE action = 'package_classified'
GROUP BY 1, 2
ORDER BY 3 DESC;

-- review_required 비율
SELECT
  (detail_json->>'confidence')::float < 0.65 as low_confidence,
  count(*)
FROM audit_logs
WHERE action = 'package_classified'
GROUP BY 1;

-- presentation 포함률
SELECT
  doc_type,
  count(*)
FROM document_runs
WHERE doc_type = 'presentation'
GROUP BY 1;

-- handoff 성공률
SELECT
  action,
  count(*)
FROM audit_logs
WHERE action IN ('studio_handoff_from_chat', 'studio_project_created')
GROUP BY 1;

-- generation 실패율
SELECT
  status,
  count(*)
FROM document_runs
GROUP BY 1;
```

## 2. Regression Corpus

### 구조
- 위치: `services/web_app/tests/test_package_classifier.py` → `_REGRESSION_CORPUS`
- 형식: parametrized pytest fixture
- 각 케이스: `(name, analysis_json, summary_md, expected_domain, expected_method, expected_presentation)`

### 현재 corpus (18건) — 목표 15~20건 달성

| # | 이름 | domain | method | PPT |
|---|------|--------|--------|-----|
| 1 | 공사 수의계약 (오수관로) | construction | pq | No |
| 2 | 감리 견적 (학교 네트워크) | service | pq | No |
| 3 | 협상+발표 IT (CCTV) | service | negotiated | Yes |
| 4 | IT용역 협상 (학사행정) | service | negotiated | - |
| 5 | 적격심사 (도서관 유지보수) | service | pq | No |
| 6 | 물품 (PC 구매) | goods | - | - |
| 7 | 공사 (청사 리모델링) | construction | - | - |
| 8 | 정보통신공사 실제 | construction | - | - |
| 9 | IoT 서비스 | service | - | - |
| 10 | 발표 없는 IT 유지보수 | service | pq | No |
| 11 | ISP 컨설팅 발표형 | service | negotiated | Yes |
| 12 | 전기공사 적격심사 | construction | pq | No |
| 13 | 통신공사 시공형 | construction | - | No |
| 14 | 물품 서버/PC 납품 | goods | - | No |
| 15 | SW 라이선스 구매 | goods | - | No |
| 16 | 감리용역 협상 발표없음 | service | negotiated | No |
| 17 | 연구용역 발표형 | service | negotiated | Yes |
| 18 | 소액수의 물품 | goods | pq | No |

### 새 오분류 편입 규칙
1. 운영 중 오분류 발견 → 이슈로 기록
2. 해당 공고의 분석 데이터를 `_REGRESSION_CORPUS`에 추가
3. 기대값 라벨링 (domain, method, presentation)
4. 테스트 통과 확인 후 hotfix 커밋

### 목표
- 최소 15~20건 **(현재 18건 — 목표 달성)**
- 카테고리별 최소 2건씩 **(달성)**

## 3. review_required 체계

### 기준
- `confidence < 0.65` → `review_required = True`
- 신뢰도가 낮으면 Studio PackageStage에 경고 배너 표시

### UI 표시
- "자동 분류 확신 낮음 — 검토가 필요합니다"
- warnings 목록 표시 (domain/method 점수 낮음 등)

### API 응답
```json
{
  "procurement_domain": "service",
  "contract_method": "negotiated",
  "confidence": 0.55,
  "review_required": true,
  "matched_signals": ["domain:용역", "method:기술평가"],
  "warnings": ["domain 점수 낮음 (4)"],
  "package_items": [...]
}
```
