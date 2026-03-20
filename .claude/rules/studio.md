---
paths:
  - "services/web_app/api/studio.py"
  - "services/web_app/services/package_classifier.py"
  - "frontend/kirabot/components/studio/**"
  - "frontend/kirabot/services/studioApi.ts"
---

## CRITICAL
- Chat=탐색, Studio=정식 생산 경로 — 이 경계를 유지
- shared CompanyDB 오염 방지 — promote 전에는 staging만
- 신규 사용자 자동 org 생성 — 첫 API 접근 시 1회

## MANDATORY

### 제품 경계
- package classifier → company/style 연결 → generated docs + evidence checklist → review/relearning
- 입찰 제출 패키지 Studio (용역+물품+공사) — 제안서 작성기가 아님

### Classifier
- hard guard: 수의/견적 우선 분기 + PPT evidence gate
- 발표자료는 발표평가 명시 근거 있을 때만 포함
- review_required: confidence < 0.65 시 UI 경고
- regression corpus: 18건 parametrized (확장 운영)

### Feature Flags
- `VITE_STUDIO_VISIBLE` — Studio UI 노출 (Navbar/Hero/ProductHub)
- `VITE_CHAT_GENERATION_CUTOVER` — Chat→Studio handoff 전환
- 둘 다 빌드 타임 변수 (Dockerfile ARG)

### Slice 현황 (2026-03-20)
- Slice 1-5 완료, Ops Hardening 완료
- Production 배포됨 (Railway)
- Phase 1 운영 중 (Studio 노출, Chat cutover off)
- 195 BE tests, 109 FE tests, 18 corpus cases
