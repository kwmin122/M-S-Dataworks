# JSON Schema Contracts

B2B SaaS 입찰 분석 플랫폼에서 사용되는 JSON 컬럼 데이터의 스키마 계약을 명시합니다. 이 규약을 통해 각 마이크로서비스 간의 파싱 비용을 낮추고 안정적인 모델 호환성을 보장합니다.

---

## 1. `Organization.companyFacts`

RAG 시스템이 결정론적으로 입찰 가능성을 판단하기 위해 필요한 기업 제원 및 기본 팩트 정보입니다.

### Data Structure (JSON)

```json
{
  "_meta": {
    "schemaVersion": "1.0",
    "updatedAt": "2026-02-20T12:00:00Z",
    "source": "manual_input" // "manual_input", "crawler", "admin_override" 등
  },
  "facts": {
    "region": "경기도",
    "foundationDate": "2015-05-01",
    "capital": 100000000,
    "licenses": [
      {
        "code": "0037",
        "name": "정보통신공사업"
      },
      {
        "code": "1468",
        "name": "소프트웨어사업자"
      }
    ],
    "certifications": [
      "직접생산확인증명서(CCTV)",
      "여성기업"
    ],
    "pastPerformances": [
      {
        "category": "정보통신",
        "amountLastYear": 500000000
      }
    ]
  }
}
```

### 필수 키 규칙
- `_meta`: 스키마 버전(`schemaVersion`) 및 소스를 강제로 포함해야 합니다. 파싱 전 버전 호환성을 보장합니다.
- `facts`: 실제 데이터 딕셔너리로, 면허(`licenses`)나 지역(`region`) 같은 1차 필터링용 속성은 최상위 레벨에 위치해야 합니다.

---

## 2. `NoticeScore.details`

해당 기업이 어떠한 이유로 입찰에 탈락하거나 성공할 수 있는지 상세 근거를 RAG 모델이 정리한 출력 결과입니다.

### Data Structure (JSON)

```json
{
  "_meta": {
    "schemaVersion": "1.0",
    "engineVersion": "v1.2.0-hybrid-bm25",
    "evaluatedAt": "2026-02-20T12:05:00Z"
  },
  "evaluation": {
    "missingLicenses": [
      "출판사신고(코드: 1526)"
    ],
    "insufficientCapital": false,
    "regionMismatch": false,
    "confidenceScore": 0.95
  },
  "rawOutput": {
    "matchedChunks": [
      "공동수급(분담이행) 허용하며, 정보통신공사업과 출판사신고를 모두 갖출 것."
    ]
  }
}
```

### 필수 키 규칙
- `_meta`: 여기서는 `engineVersion`을 두어 RAG 엔진 모델이 개선될 때 어떤 모델을 사용해 평가했는지 이력 추적이 가능하게 합니다.
- `evaluation`: 시스템 모니터링 대시보드나 프론트엔드에서 바로 보여줄 수 있는 boolean/array 값들로 정규화된 키만 담습니다.
- `rawOutput`: 디버깅용으로 실제 RAG 매칭에 사용된 청크나 원시 로그를 기록합니다.
