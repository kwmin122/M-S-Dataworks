# Bid Studio Staged Rollout Runbook

## 목적
Bid Studio를 공식 생성 경로로 안전하게 전환한다.
한 번에 100% 컷오버하지 않고, 단계별로 노출 → 관찰 → 확대한다.

---

## Phase 1: Studio 노출 (Internal Canary)

### 환경 설정
```env
VITE_STUDIO_VISIBLE=true        # Studio UI 노출 (Navbar, Hero, ProductHub)
VITE_CHAT_GENERATION_CUTOVER=false  # Chat 생성은 legacy 유지
```

### 기대 동작
- 사용자가 Navbar/ProductHub에서 "입찰 문서 AI 작성" 진입 가능
- `/studio` 직접 접근 가능
- Chat에서 분석 후 기존 inline 생성 버튼 유지 (handoff CTA 없음)
- Studio와 Chat이 독립적으로 공존

### 관찰 포인트
| 지표 | 확인 방법 | 기대값 |
|------|----------|--------|
| Studio 접근 가능 | `/studio` 페이지 로드 | 정상 렌더 |
| 프로젝트 생성 | "새 프로젝트" 버튼 클릭 | 프로젝트 생성 + rfp stage |
| RFP 분석 | 텍스트 입력 → 분석 | 스냅샷 생성, 요건 추출 |
| 패키지 분류 | 분석 후 분류 | domain/method + items |
| 문서 생성 | proposal 생성 시도 | run/revision 생성 |
| legacy Chat 정상 | Chat에서 기존 분석/생성 | 변화 없음 |

### 기간
- 최소 2~3일 내부 사용

### 판단 기준
- Studio 진입 → 프로젝트 생성 → 분석 → 분류 → 생성 정상 동작
- Chat legacy path에 회귀 없음
- 서버 에러/500 없음

---

## Phase 2: Chat Handoff 활성화 (Limited Cutover)

### 환경 설정
```env
VITE_STUDIO_VISIBLE=true
VITE_CHAT_GENERATION_CUTOVER=true   # Chat 생성 CTA → Studio handoff
```

### 기대 동작
- Chat 분석 결과에서 기존 inline 생성 버튼 대신 "Studio에서 입찰 문서 작성" CTA 표시
- CTA 클릭 → Studio 프로젝트 자동 생성 + 스냅샷 연결 → `/studio/projects/:id` 이동
- Studio에서 package → company → style → generate 순서대로 진행 가능
- Legacy inline 생성 버튼은 숨겨짐 (코드 삭제 아님 — flag off로 복구 가능)

### 관찰 포인트
| 지표 | 확인 방법 | 기대값 |
|------|----------|--------|
| Handoff CTA 노출 | Chat 분석 후 결과 확인 | "Studio에서 입찰 문서 작성" 버튼 |
| 프로젝트 생성 | CTA 클릭 | Studio project + snapshot 생성 |
| 페이지 이동 | handoff 후 | `/studio/projects/:id` 로드 |
| 분석 재사용 | Studio 진입 후 | 분석 결과 이미 존재 (재분석 불필요) |
| 생성 동작 | Studio generate stage | proposal/WBS/PPT 정상 |
| 수의계약 분류 | 견적 공고 분석 | `pq`로 분류 (negotiated 아님) |
| PPT 포함/제외 | 발표 없는 공고 | presentation 미포함 |
| PPT 포함 | 발표 있는 공고 | presentation 포함 |

### 기간
- Phase 1 이후 최소 1주

### 판단 기준
- Handoff 성공률 > 95%
- 잘못된 분류 리포트 0건 또는 known issue 범위 내
- 사용자가 Studio에서 문서 생성까지 완료 가능

---

## Phase 3: Full Rollout

### 환경 설정
```env
VITE_STUDIO_VISIBLE=true
VITE_CHAT_GENERATION_CUTOVER=true
```
(Phase 2와 동일 — 단, 전체 사용자 대상)

### 판단 기준
- Phase 2에서 1주간 이상 무사고
- 사용자 피드백에서 blocking issue 없음
- 분류 정확도가 수용 가능 범위

### 이후 정리
- Legacy inline 생성 코드 제거 검토 (Phase 3 안정화 후)
- `useConversationFlow.ts`의 legacy generation case handlers 정리

---

## Rollback 절차

### 즉시 롤백 (< 5분)
1. `.env`에서 `VITE_CHAT_GENERATION_CUTOVER=false` 설정
2. 프론트엔드 재빌드: `cd frontend/kirabot && npm run build`
3. 배포 (또는 서버 재시작)
4. 결과: Chat에서 legacy inline 생성 버튼 복구, Studio는 직접 접근으로만 사용 가능

### Studio 완전 숨김 (심각한 이슈 시)
1. `.env`에서 `VITE_STUDIO_VISIBLE=false` 추가
2. 프론트엔드 재빌드 + 배포
3. 결과: Navbar, Hero, ProductHub에서 Studio 링크 숨김
4. 주의: `/studio` URL 직접 접근은 여전히 가능 (route 자체는 남아있음)

### 서버 측 롤백
- Studio API (`/api/studio/*`)는 별도 router이므로 서버 재시작 없이 프론트만 롤백 가능
- 백엔드 롤백이 필요한 경우: 이전 커밋으로 `git checkout` 후 재배포

---

## 모니터링 체크리스트

### 서버 로그
```bash
# Studio 관련 에러
grep -i "studio\|handoff\|classify" logs/app.log | grep -i "error\|fail"

# 분류 결과 확인
grep "Package classified" logs/app.log | tail -20

# Generation 실패
grep "document_generation_failed" logs/app.log
```

### DB 확인
```sql
-- Studio 프로젝트 수
SELECT count(*) FROM bid_projects WHERE project_type = 'studio';

-- Handoff 프로젝트 (Chat에서 전환)
SELECT count(*) FROM audit_logs WHERE action = 'studio_handoff_from_chat';

-- 분류 결과 분포
SELECT
  params_json->>'doc_type' as doc_type,
  count(*)
FROM document_runs
GROUP BY 1;

-- PPT 생성 건수 (false positive 모니터링)
SELECT count(*) FROM document_runs WHERE doc_type = 'presentation';
```

### 사용자 행동
- Studio 진입 후 이탈률 (프로젝트 생성만 하고 생성 안 함)
- 문서 생성 완료율 (run status = 'completed' 비율)
- Relearn 사용률 (style_skill_relearned audit 건수)

---

## 알려진 제한사항

| 항목 | 상태 | 영향 |
|------|------|------|
| 수의계약 → pq 분류 | 의도적 근사치 | PackageStage에 "적격심사"로 표시될 수 있음 |
| PPT gate strict | 보수적 | 발표평가 공고에서 키워드 누락 시 PPT 미포함 가능 |
| HWPX 파싱 | 신규 지원 | 일부 구형 HWPX에서 텍스트 추출 불완전 가능 |
| evidence 다운로드 UI | 백엔드만 | 프론트 다운로드 버튼 미연결 |
| relearn profile 성장 | append-only | 반복 relearn 시 profile 무한 성장 |
| edit_distance | positional 근사치 | 편집률 과대 표시 가능 |
