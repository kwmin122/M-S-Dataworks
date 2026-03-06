# 전체 입찰 프로세스 자동화 파이프라인 설계 (WIP)

> **상태: 설계 진행 중** — Section 1 아키텍처 제시 완료, Section 2~5 미완

## 요구사항

| 항목 | 결정 |
|------|------|
| **대상** | 멀티테넌트 (여러 회사에 적용) |
| **채널** | 1차: 이메일(Brevo) + 웹 대시보드. 2차: 카카오톡 알림톡 |
| **모니터링** | 30분 주기 (기존 스케줄러 유지) |
| **자동화 범위** | 승인 → 분석 → 독소조항 → 문서 생성 전체, 중간 개입 가능 |
| **독소조항** | 자격적합도 + 계약 리스크 + 입찰 전략 판단 (포괄적) |
| **회사 DB** | 비어있음, 온보딩 UI 필요 |
| **접근법** | B: 이벤트 기반 파이프라인 + SQLite 상태 관리. 향후 C(n8n)로 확장 |

## 워크플로우

```
나라장터 신규 공고 모니터링 (30분 주기)
  → 회사 역량 매칭 점수 자동 분석 (company_db + matcher)
  → 적합 공고 알림 (이메일 + 웹 대시보드)
  → 담당자 승인/거절
  → [승인 시] RFP 자동 다운로드 + 분석
  → 독소조항/리스크 분석 + 입찰 전략 판단
  → 제안서 DOCX + PPT + WBS 초안 자동 생성
  → 담당자 검토/수정
```

## Section 1: 전체 아키텍처 & 상태 머신

### 파이프라인 스테이지 (7단계)

```
[SCAN] → [MATCH] → [NOTIFY] → [APPROVE] → [ANALYZE] → [GENERATE] → [REVIEW]
30분주기  매칭점수  알림전송    승인대기     RFP분석+     문서생성     검토/수정
                                          독소조항
```

### 상태 머신 (BidPipelineState)

```
DETECTED → MATCHED → NOTIFIED → APPROVED → ANALYZING → ANALYZED → GENERATING → GENERATED → REVIEWING → COMPLETED
                                    ↓
                                 REJECTED → 종료

                       Any stage → FAILED (재시도 max 3회)
```

### SQLite 테이블

```sql
CREATE TABLE bid_pipeline (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    bid_ntce_no TEXT NOT NULL,
    bid_ntce_nm TEXT,
    state TEXT NOT NULL DEFAULT 'detected',
    match_score REAL,
    match_detail TEXT,          -- JSON
    risk_analysis TEXT,         -- JSON (독소조항)
    strategy_analysis TEXT,     -- JSON (입찰 전략)
    generated_files TEXT,       -- JSON (파일 경로)
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    UNIQUE(company_id, bid_ntce_no)
);

CREATE TABLE company_profile (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    session_id TEXT UNIQUE,
    alert_config TEXT,         -- JSON
    company_data TEXT,         -- JSON
    created_at TEXT NOT NULL
);
```

### 워커 구조

기존 FastAPI lifespan에 `pipeline_worker_loop()` 추가:
- 30초 주기로 처리할 스테이지 확인
- DETECTED → MATCH, APPROVED → ANALYZE, ANALYZED → GENERATE
- FAILED → 재시도 (max 3회)

---

## Section 2: 독소조항/리스크 분석기 (미완)

40년차 이사 관점, 3가지 축:
1. **자격 적합도**: 면허, 실적, 인력 요건 매칭 (기존 rfx_analyzer 확장)
2. **계약 리스크**: 지체상금, 하자보수, 대금지급, 손해배상, 지재권 등
3. **입찰 전략**: 예산 대비 난이도, 경쟁 예상, 배점 전략, 회사 강점 활용도

## Section 3: 알림 + 승인 UX (미완)

## Section 4: 웹 대시보드 (미완)

## Section 5: 회사 온보딩 (미완)

---

*설계 재개 시 Section 2부터 계속*
