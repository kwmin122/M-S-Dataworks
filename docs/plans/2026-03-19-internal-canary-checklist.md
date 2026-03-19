# Bid Studio Internal Canary Checklist

## 목적
실서버 배포 전, 내부 사용자가 주요 경로를 직접 확인한다.
각 항목을 실행하고 결과를 기록한다.

---

## 사전 준비
- [ ] `VITE_STUDIO_VISIBLE=true` 설정 확인
- [ ] `VITE_CHAT_GENERATION_CUTOVER=false` 설정 확인 (Phase 1)
- [ ] `OPENAI_API_KEY` 설정 확인
- [ ] PostgreSQL 서버 정상 기동
- [ ] 프론트엔드 빌드 + 배포 완료

---

## 1. Studio 진입 검증

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 1.1 | Navbar에서 "입찰 문서 AI 작성" 클릭 | `/studio` 페이지 정상 렌더 | |
| 1.2 | ProductHub에서 "Studio 열기" 클릭 | `/studio` 이동 | |
| 1.3 | Hero CTA "입찰 문서 AI 작성" 클릭 | `/studio` 이동 | |
| 1.4 | 모바일 Navbar 드롭다운 | Studio 링크 노출 + 클릭 이동 | |
| 1.5 | 미인증 사용자 `/studio` 접근 | 로그인 리다이렉트 | |

---

## 2. 프로젝트 생성 + RFP 분석

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 2.1 | "새 프로젝트" 클릭 | 프로젝트 생성, rfp stage로 이동 | |
| 2.2 | RFP 텍스트 입력 (협상형) | 분석 성공, 스냅샷 생성 | |
| 2.3 | RFP 텍스트 입력 (견적형) | 분석 성공, 요건 추출 | |

---

## 3. 패키지 분류 검증

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 3.1 | 협상형 + 발표평가 공고 분류 | `service/negotiated` + **presentation 포함** | |
| 3.2 | 수의계약/견적 공고 분류 | `negotiated` **아님** (pq 등) | |
| 3.3 | 수의계약 공고 분류 | **presentation 미포함** | |
| 3.4 | 물품 공고 분류 | `goods/*` + evidence 중심 | |
| 3.5 | 공사 공고 분류 | `construction/*` | |

---

## 4. 문서 생성 검증

### 4.1 제안서 (proposal)
| 확인 항목 | 결과 |
|----------|------|
| 생성 버튼 클릭 → 생성 시작 | |
| 생성 완료 (status=completed) | |
| 섹션 미리보기 표시 | |
| generation contract 보기 → 실제 입력값 표시 | |

### 4.2 수행계획서 (execution_plan)
| 확인 항목 | 결과 |
|----------|------|
| doc_type selector에서 "수행계획서/WBS" 선택 | |
| 생성 완료 | |
| WBS tasks 미리보기 표시 | |

### 4.3 실적기술서 (track_record)
| 확인 항목 | 결과 |
|----------|------|
| "실적기술서" 선택 → 생성 | |
| records + personnel 미리보기 | |

### 4.4 발표자료 (presentation)
| 확인 항목 | 결과 |
|----------|------|
| "발표자료(PPT)" 선택 → 생성 | |
| slides 목록 + Q&A 미리보기 | |
| .pptx 다운로드 링크 동작 | |

---

## 5. 회사 자산 + 스타일

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 5.1 | 회사 역량 stage 진입 | profile/실적/인력 입력 가능 | |
| 5.2 | staging → shared promote | shared DB에 반영 | |
| 5.3 | 스타일 생성 | project-scoped style 생성 | |
| 5.4 | 스타일 pin | generation contract에 반영 | |

---

## 6. 체크리스트 + Evidence

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 6.1 | 체크리스트 stage 진입 | 항목 목록 + 완성도 % 표시 | |
| 6.2 | generated → verified 전환 | 상태 변경 정상 | |
| 6.3 | missing → waived 전환 | 면제 처리 정상 | |
| 6.4 | evidence 파일 업로드 | 파일 선택 → 업로드 → uploaded 전환 | |
| 6.5 | evidence 파일 다운로드 | 다운로드 endpoint 동작 | |

---

## 7. Review / Relearn

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 7.1 | 검토 stage 진입 | 현재 revision 로드 + 편집 가능 | |
| 7.2 | 수정 저장 | user_edited revision 생성 | |
| 7.3 | diff 보기 | 원본 vs 수정 비교 표시 | |
| 7.4 | 수정 패턴 학습 | 새 style skill 파생 | |
| 7.5 | 새 스타일 적용 + 재생성 | contract skill id 변경 + 내용 변화 | |

---

## 8. Chat Legacy 검증 (Phase 1 필수)

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 8.1 | Chat에서 공고 검색 | 정상 동작 | |
| 8.2 | Chat에서 문서 분석 | 분석 결과 표시 | |
| 8.3 | Chat에서 inline 생성 버튼 | 기존 버튼 유지 (handoff CTA 없음) | |
| 8.4 | Chat에서 제안서 생성 | inline 생성 정상 동작 | |

---

## 9. Chat Handoff 검증 (Phase 2 전용)

| # | 시나리오 | 확인 항목 | 결과 |
|---|---------|----------|------|
| 9.1 | `VITE_CHAT_GENERATION_CUTOVER=true` 설정 후 | | |
| 9.2 | Chat 분석 결과에서 CTA | "Studio에서 입찰 문서 작성" 노출 | |
| 9.3 | CTA 클릭 | Studio 프로젝트 생성 + 이동 | |
| 9.4 | Studio에서 분석 결과 확인 | 재분석 없이 스냅샷 연결됨 | |
| 9.5 | Legacy 버튼 숨김 확인 | inline 생성 버튼 미노출 | |

---

## 판단 기준

### Pass 조건
- 섹션 1~8 전체 통과 (Phase 1)
- 섹션 9 전체 통과 (Phase 2)
- 서버 500 에러 0건
- 분류 false positive 0건 (테스트 공고 기준)

### Fail 시 대응
- blocking issue → rollback (runbook 참조)
- non-blocking issue → 기록 후 hotfix 검토
- 분류 이슈 → package_classifier.py 키워드 조정

---

## 결과 기록

검증 완료 후 아래를 기록:
- 날짜:
- 검증자:
- Phase:
- Pass/Fail:
- 발견된 이슈:
- 조치:
