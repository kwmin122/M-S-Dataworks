# Slice 4 Validation & Rollout Notes

## 0. Real-World Validation Results (2026-03-19)

### 검증 환경
- Python: anaconda python 3.13
- LLM: gpt-4o-mini (OPENAI_API_KEY from ~/Desktop/MS_SOLUTIONS/.env)
- DB: PostgreSQL localhost:5434

### Doc A: 공사 — 오수관로 단가공사
- **파일**: `[화성시 동탄구 공고 제2026 22호]2026년 동탄구 오수관로 흡입준설...단가공사.hwp`
- **파싱**: HWP 파싱 성공 (20,171 chars)
- **분석**: Title "2026년 동탄구 오수관로 흡입준설, CCTV, 송연조사, 비굴착보수 단가공사", 3개 요건 추출
- **분류**: `construction/negotiated` (conf=0.70)
- **패키지**: 13개 (generated 3 + evidence 6 + price 2 + admin 2)
- **이슈**: 수의계약 견적 제출 공고인데 `negotiated`로 분류 + PPT 생성 대상 포함. 실제로는 발표 없는 공고일 가능성 높음 → **false positive risk**
- **결론**: 분석/분류 파이프라인 동작 확인. 분류 정확도 개선 필요 (수의계약 vs 협상계약 구분)

### Doc B: 감리용역 — 학교 네트워크 공사 감리
- **파일**: `[공고문] [9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역.hwp`
- **파싱**: HWP 파싱 성공 (17,795 chars)
- **분석**: Title "[9권역]학교 유무선 네트워크개선 3차 정보통신공사 감리용역", 4개 요건 추출
- **분류**: `service/negotiated` (conf=0.55)
- **패키지**: 15개 (generated 4 + evidence 7 + price 2 + admin 2)
- **이슈**: 견적 제출 공고인데 negotiated 분류. confidence 0.55로 낮음
- **결론**: 용역 분류 맞으나 계약 방식 정확도 낮음

### Doc C: IT용역 — CCTV 감시 시스템 구축 (HWPX)
- **파일**: `공고문-CCTV 감시 시스템 구축 및 유지보수 관리 운영.hwpx`
- **파싱**: HWPX 파싱 성공 (5,088 chars) — 이번 세션에서 HWPX 지원 추가
- **분석**: Title "CCTV 감시 시스템 구축 및 유지보수 관리·운영", 7개 요건 추출
- **분류**: `service/negotiated` (conf=0.75)
- **패키지**: 15개 (generated 4 + evidence 7 + price 2 + admin 2)
- **이슈**: 이 공고는 실제 협상계약 + 발표평가 명시 → 분류 정확. 가장 이상적인 Studio 대상
- **결론**: 분석/분류/패키지 모두 적절. Studio full cycle 최적 후보

### 검증 요약

| 항목 | Doc A (공사) | Doc B (감리) | Doc C (IT/HWPX) |
|------|-------------|-------------|-----------------|
| 파싱 | HWP ✅ | HWP ✅ | HWPX ✅ (신규) |
| 분석 | ✅ 3요건 | ✅ 4요건 | ✅ 7요건 |
| 분류 domain | construction ✅ | service ✅ | service ✅ |
| 분류 method | negotiated ⚠️ | negotiated ⚠️ | negotiated ✅ |
| 패키지 | 13개 | 15개 | 15개 |
| PPT 포함 적절성 | ⚠️ false positive | ⚠️ 미확인 | ✅ 발표평가 있음 |

### Known Issues from Validation
1. **수의계약 견적 공고를 negotiated로 분류** — 수의계약 vs 협상계약 구분 로직 필요
2. **PPT false positive** — 발표평가 없는 공고에도 PPT 생성 대상 포함
3. **HWPX 지원 추가됨** — document_parser.py에 ZIP+XML 기반 HWPX 파싱 구현
4. **LLM 기반 생성은 미검증** — 분석/분류까지 확인, proposal/WBS/PPT 생성은 API 키 + 서버 기동 필요

---

## 1. Validation Scenarios (계획)

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
| `VITE_STUDIO_VISIBLE` | `true` (default) | Studio 자체 노출 (Navbar, ProductHub) |
| `VITE_CHAT_GENERATION_CUTOVER` | `false` | Chat 분석 결과에서 Studio handoff CTA 노출 |
| `studioEnabled` (App.tsx) | `true` | ProductHub에서 Studio 카드 활성화 (VITE_STUDIO_VISIBLE과 연동 권장) |

### Enable Order
1. `studioEnabled=true` (이미 적용됨) — ProductHub에서 Studio 접근 가능
2. `VITE_CHAT_GENERATION_CUTOVER=true` — Chat에서 "Studio에서 입찰 문서 작성" CTA 활성화
3. Legacy inline generation 버튼은 flag off 시 유지 — 안전한 fallback

### Rollback Steps
1. `VITE_CHAT_GENERATION_CUTOVER` 환경변수 제거 또는 `false` 설정
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
- 내부 사용자 (개발팀, QA) 먼저 `VITE_CHAT_GENERATION_CUTOVER=true`
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
