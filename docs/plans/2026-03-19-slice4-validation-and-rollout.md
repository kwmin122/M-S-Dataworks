# Slice 4 Validation & Rollout Notes

## 1. Validation Scenarios

### Scenario A: 협상형 일반용역 (IT 시스템 구축)
- **공고 유형**: 협상에 의한 계약, 기술제안 발표 평가 포함
- **패키지 분류 예상**: service/negotiated
- **생성 대상 문서**:
  - [x] proposal (기술 제안서)
  - [x] execution_plan (수행계획서/WBS)
  - [x] presentation (발표자료/PPT)
  - [x] track_record (실적기술서)
  - [ ] evidence (증빙 — 사업자등록증, 경험증명서 등)
- **검증 포인트**:
  - package classifier가 generated_document 4개 + evidence/administrative N개 생성
  - 각 doc_type별 generation contract에 snapshot/company/style 정보 포함
  - PPT가 proposal + execution_plan revision을 입력으로 사용
  - review/relearn 루프 동작 (proposal 편집 → diff → style derive)
- **예상 수동 개입**:
  - 증빙 서류 (사업자등록증, 경험증명서 등) 수동 업로드 필요
  - 발표시간/슬라이드 수 조정은 현재 서버 기본값 사용
- **위험**:
  - WBS 프롬프트가 비-IT 도메인에서는 아직 약할 수 있음
  - PPT의 execution_plan 활용은 section-level merge로 제한적

### Scenario B: 발표 없는 패키지형 공고 (PQ/적격심사)
- **공고 유형**: 적격심사 또는 가격경쟁형
- **패키지 분류 예상**: service/pq 또는 goods/lowest_price
- **생성 대상 문서**:
  - [x] proposal 또는 execution_plan (필요 시)
  - [ ] presentation — NOT required (패키지에서 제외되어야 함)
  - [ ] evidence 중심
- **검증 포인트**:
  - package classifier가 presentation을 ready_to_generate로 만들지 않음
  - evidence 업로드 + checklist 완성도 추적이 핵심 경로
  - presentation 미생성 시 checklist %가 100%에 도달 가능
- **예상 수동 개입**:
  - 대부분 증빙 업로드 수동
- **위험**:
  - classifier가 발표 없는 공고에도 presentation을 포함할 가능성 (false positive)

### Scenario C: 물품 구매 공고
- **공고 유형**: 물품 구매, 카탈로그/규격서 중심
- **패키지 분류 예상**: goods/lowest_price 또는 goods/adequacy
- **생성 대상 문서**:
  - [ ] proposal — 보통 불필요
  - [ ] execution_plan — 불필요
  - [ ] presentation — 불필요
  - [ ] evidence (규격서, 인증서, 카탈로그 등) — 수동 업로드
- **검증 포인트**:
  - package classifier가 generated_document를 최소화
  - evidence/administrative 위주 패키지 구성
  - checklist 상태 전환이 evidence 업로드 중심으로 동작
- **예상 수동 개입**:
  - 거의 모든 서류 수동 업로드
- **위험**:
  - Studio가 evidence-only 공고에서도 유용한지 — 생성할 문서가 없으면 Studio 가치 제한적

## 2. Known Limitations

| 항목 | 상태 | 비고 |
|------|------|------|
| LLM 호출 없이 검증 | 불가 | Mock 테스트는 통과하나 실제 LLM 품질은 배포 후 확인 필요 |
| evidence 파일 다운로드 | 백엔드 있음, 프론트 CTA 미연결 | evidence download_evidence endpoint 존재 |
| PPT HTML preview | 미구현 | slide metadata summary만 가능 |
| 수행계획 → PPT enrichment | section merge만 | 간트차트/타임라인 이미지는 미전달 |
| relearn convergence | append-only | 반복 relearn 시 profile 무한 성장 가능 |
| edit_distance | 근사치 (positional) | difflib.SequenceMatcher 미사용 |

## 3. Rollout Strategy

### Feature Flags

| Flag | 기본값 | 의미 |
|------|--------|------|
| `VITE_STUDIO_CUTOVER` | `false` | Chat 분석 결과에서 Studio handoff CTA 노출 |
| `studioEnabled` (App.tsx) | `true` | ProductHub에서 Studio 카드 활성화 |

### Enable Order
1. `studioEnabled=true` (이미 적용됨) — ProductHub에서 Studio 접근 가능
2. `VITE_STUDIO_CUTOVER=true` — Chat에서 "Studio에서 입찰 문서 작성" CTA 활성화
3. Legacy inline generation 버튼은 flag off 시 유지 — 안전한 fallback

### Rollback Steps
1. `VITE_STUDIO_CUTOVER` 환경변수 제거 또는 `false` 설정
2. 프론트엔드 재빌드 → 배포
3. Legacy inline generation 즉시 복원 (코드 삭제 안 했으므로)
4. Studio route (`/studio`)는 여전히 접근 가능 (직접 URL)

### 100% Cutover 가능한가?
**아직 아닙니다.** Staged rollout을 권장합니다.

이유:
- 실제 LLM 품질 검증 미완 (mock 테스트만)
- evidence 다운로드 UI 미연결
- edit_distance 근사치
- PPT execution_plan enrichment 제한적

권장:
- 내부 사용자 (개발팀, QA) 먼저 `VITE_STUDIO_CUTOVER=true`
- 1~2주 사용 후 피드백 수집
- 주요 이슈 없으면 전체 전환

## 4. Test Coverage Summary

| 영역 | 테스트 수 | 범위 |
|------|----------|------|
| Backend total | 165 passed, 3 skipped | Studio API + package + generate + relearn |
| Frontend total | 109 passed | 12 test files, all stages |
| TypeScript | clean | No errors |
| Handoff endpoint | backend tested | handoff-from-chat creates project + snapshot |
| Feature flag | frontend conditional | cutover flag controls CTA rendering |
