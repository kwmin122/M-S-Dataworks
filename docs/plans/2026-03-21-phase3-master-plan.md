# Phase 3 마스터 계획

> "사용자가 틀린 분류와 애매한 품질을 스스로 통제할 수 있고,
> 문서가 실제 제출 가능한 수준인지 시스템이 끝까지 책임지는 제품"

## 현재 상태 (Phase 1+2 완료)

- 커밋: `b956272` / `36c3736` / `98dac35`
- 테스트: FE 129, BE 214, RAG 434 — P0/P1 0건
- 완료: 10/17 요구사항

## Phase 3 구조

```
Phase 3A: 문서 품질 완성 ─── 사용자가 돈을 내는 핵심 가치
Phase 3B: 운영 완성 ──────── 통제 가능한 SaaS
Phase 3C: 최종 출시 게이트 ── 실전 검증
```

---

## Phase 3A: 문서 품질 완성

### 3A-1. WBS Quality (요구사항 #7)

**현재 문제:**
- IT 편향 (방법론 감지가 SW 중심)
- xlsx/png/docx 산출물 간 일관성 미보장
- 크리티컬 패스 없음
- 간트차트 한글 폰트 서버 환경 깨짐

**Exit Criteria:**
- [ ] 비-IT 공고(건설 감리, 물품 납품)에서 합리적 WBS 생성
- [ ] XLSX 태스크 목록 ↔ 간트차트 PNG ↔ DOCX 텍스트 간 데이터 일치
- [ ] 일정, 역할, 산출물, 마일스톤이 모두 포함
- [ ] 간트차트 한글 폰트 서버 환경 대응 (NanumGothic fallback)
- [ ] Quality Gate `doc_type=execution_plan` 차원 추가 (일정 현실성, 역할-태스크 매핑)

**구현:**
1. wbs_orchestrator.py — 도메인 감지 + 범용 방법론 매핑
2. wbs_assembler.py — 간트차트 폰트 fallback 체인
3. quality_gate.py — execution_plan 전용 체크 추가
4. 테스트: IT/건설/물품 3종 공고로 WBS 생성 + 품질 검증

### 3A-2. Presentation Quality (요구사항 #9)

**현재 문제:**
- 슬라이드 구조가 획일적 (모든 공고에 동일 템플릿)
- 콘텐츠 매칭이 서브스트링 기반 (부정확)
- 발표 근거 없는 공고에서 false positive
- 슬라이드 오버플로우 미처리

**Exit Criteria:**
- [ ] `_has_presentation_evidence()` false → PPT 생성 불가 (UI에서도 차단)
- [ ] 슬라이드 플랜이 공고 도메인에 맞춤화
- [ ] RFP + proposal + WBS + company context 4개 소스 통합 반영
- [ ] 콘텐츠 오버플로우 시 자동 분할 (8줄 초과 → continuation slide)
- [ ] Quality Gate `doc_type=presentation` 차원 추가

**구현:**
1. ppt_slide_planner.py — 도메인 인식 슬라이드 구조
2. ppt_content_extractor.py — NLP 기반 섹션-슬라이드 매칭 (서브스트링 → 키워드 점수)
3. ppt_assembler.py — 오버플로우 자동 분할
4. GenerateStage.tsx — 발표 근거 없으면 PPT 옵션 비활성화
5. quality_gate.py — presentation 전용 체크 추가

### 3A-3. Multi-Doc Relearn (요구사항 #10)

**현재 문제:**
- relearn이 proposal 전용
- WBS/PPT 편집 → 학습 루프 미닫힘
- "쓸수록 좋아지는 제품" 약속이 proposal에만 적용

**Exit Criteria:**
- [ ] WBS 편집 → diff → style derive → repin → regenerate 루프 동작
- [ ] PPT는 slide-level diff가 복잡하므로 v1은 스킵 (Phase 4)
- [ ] track_record는 선택/순서 편집 → 다음 생성 시 반영
- [ ] relearn API가 doc_type 파라미터를 받아 proposal/execution_plan 분기

**구현:**
1. ReviewStage.tsx — doc_type selector 추가 (현재 proposal 고정)
2. studio.py relearn endpoint — doc_type 파라미터 지원
3. auto_learner.py — execution_plan diff 패턴 학습
4. 테스트: WBS 편집 → relearn → 재생성 시 변경 반영 확인

---

## Phase 3B: 운영 완성

### 3B-1. Operational Observability (요구사항 #14)

**현재 문제:**
- 생성 성공/실패율 추적 없음
- classifier override 빈도 추적 없음
- 저품질 출력 식별 불가
- corpus 개선 피드백 루프 없음

**Exit Criteria:**
- [ ] 운영자 대시보드 (admin 전용 페이지)
  - 일별 생성 성공/실패/에러율
  - classifier override 빈도 (도메인별)
  - quality_gate 평균 점수 + 등급 분포
  - 사용자별 활동량
- [ ] AuditLog 기반 지표 집계 API
- [ ] classifier override → corpus 자동 편입 루프 설계

**구현:**
1. studio.py — `GET /api/studio/admin/metrics` 집계 엔드포인트
2. AdminDashboard.tsx — 지표 시각화 (차트는 recharts)
3. AuditLog 쿼리 최적화 (인덱스 추가)

### 3B-2. Performance & Cost (요구사항 #16)

**현재 문제:**
- 생성 시간 목표 없음
- 모델별 품질 vs 비용 기준 없음
- 대용량 파일/문서 체감 성능 미관리

**Exit Criteria:**
- [ ] 생성 시간 목표 설정: proposal <3분, WBS <2분, PPT <2분, track_record <1분
- [ ] 타임아웃 기준: 전체 5분, 개별 섹션 90초
- [ ] gpt-4o vs gpt-4o-mini 품질/비용 비교 데이터 (A/B 테스트 3종 공고)
- [ ] 생성 중 프로그레스 표시 (섹션별 진행률)

**구현:**
1. proposal_orchestrator.py — 섹션별 타임아웃 + 진행 콜백
2. GenerateStage.tsx — 프로그레스 바 (섹션 N/M 완료)
3. A/B 테스트 스크립트 확장 (3종 공고 × 2개 모델)

### 3B-3. Commercial Readiness (요구사항 #17)

**현재 문제:**
- 요금제 표시는 있지만 실제 사용량 제어 없음
- 모든 사용자가 동일 접근 권한
- 무료/유료 전환 경계 불명확

**Exit Criteria:**
- [ ] 사용량 카운터: 분석 N회/월, 생성 N회/월
- [ ] FREE 제한: 분석 5회/월, 생성 0회 (열람만)
- [ ] PRO 제한: 무제한 분석, 생성 30회/월
- [ ] 제한 초과 시 UI에서 업그레이드 안내
- [ ] 조직별 학습 자산(CompanyDB, style skills) 격리 확인

**구현:**
1. usage_tracker.py — 조직별 월간 사용량 집계
2. studio.py — 생성 전 quota 체크 미들웨어
3. QuotaGate.tsx — 제한 초과 UI 컴포넌트
4. SubscriptionPage.tsx — 실제 플랜 연동

---

## Phase 3C: 최종 출시 게이트

### Exit Criteria (전부 통과해야 "출시 가능")

**1. 실전 공고 E2E 검증 (5종)**
- [ ] IT 용역 (정보시스템 구축)
- [ ] 감리 (SW 감리)
- [ ] 물품 (장비 납품)
- [ ] 공사 (토목/설비)
- [ ] 발표형 협상 (PPT 포함)

**2. 4종 문서 품질 기준**
- [ ] proposal: quality_gate 75점+ (수 등급)
- [ ] execution_plan: quality_gate 70점+
- [ ] track_record: quality_gate 70점+
- [ ] presentation: quality_gate 70점+

**3. 사용자 흐름 완결성**
- [ ] 생성 실패 → 재시도 → 성공
- [ ] 업로드 실패 → 다른 파일 → 성공
- [ ] 분류 오류 → manual override → 정상 진행
- [ ] 편집 → diff → relearn → 재생성 (proposal + WBS)
- [ ] 이전 revision 복구

**4. 운영자 통제**
- [ ] 대시보드에서 에러율/품질 확인 가능
- [ ] classifier override가 corpus 개선에 반영 가능

**5. 상용 게이트**
- [ ] 무료 사용자: 분석만, 생성 차단
- [ ] PRO 사용자: 전체 기능 동작
- [ ] 사용량 초과 시 업그레이드 안내

---

## 실행 순서 + 커밋 전략

```
3A-1 WBS Quality          ──── 커밋 1 ── 테스트
3A-2 Presentation Quality  ──── 커밋 2 ── 테스트
3A-3 Multi-Doc Relearn     ──── 커밋 3 ── 테스트
                           ──── ✅ Phase 3A checkpoint

3B-1 Observability         ──── 커밋 4 ── 테스트
3B-2 Performance & Cost    ──── 커밋 5 ── 테스트
3B-3 Commercial Readiness  ──── 커밋 6 ── 테스트
                           ──── ✅ Phase 3B checkpoint

3C   Final Release Gate    ──── E2E 검증 ── 배포
                           ──── ✅ 출시
```

각 커밋은 독립적으로 배포 가능해야 합니다.
커밋 간 회귀 없음을 테스트로 보장합니다.

---

## 하지 말아야 할 것

- dead surface를 둔 채 새 기능부터 계속 붙이기
- review_required를 경고만 보여주고 끝내기
- 영업 문서 기준으로 완료 선언하기
- PPT preview 같은 눈에 보이는 기능을 trust gap보다 앞세우기
- Phase 3A/3B/3C를 한 번에 밀어넣기

---

*Last updated: 2026-03-21*
