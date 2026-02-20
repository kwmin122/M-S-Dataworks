# KiraBot 인수인계 가이드 (Codex CLI용)

작성일: 2026-02-19  
프로젝트 경로: `/Users/min-kyungwook/Downloads/기업전용챗봇세분화`

---

## 1) 프로젝트 한줄 요약
M&S Solutions의 `KiraBot`은 회사 문서 + 분석 대상 문서를 업로드하면, RFx/제안서 기준 매칭·요약·근거 참조·챗 질의를 한 화면에서 처리하는 B2B 문서 분석 도구다.

---

## 2) 현재 아키텍처 (실행 기준)

### 프론트
- React/Vite: `/frontend/kirabot`
- 주요 화면:
  - 랜딩: Hero/Features/Solutions/Pricing/Footer
  - 로그인 모달: Google OAuth 시작
  - 워크스페이스: 좌측 문서 미리보기 + 우측 챗/분석

### 백엔드
- FastAPI: `/services/web_app/main.py`
- 주요 API:
  - 인증: `/auth/google/login`, `/auth/google/callback`, `/auth/me`, `/auth/logout`
  - 세션: `/api/session`, `/api/session/stats`
  - 문서: `/api/company/upload`, `/api/company/clear`, `/api/analyze/upload`, `/api/analyze/text`
  - 챗: `/api/chat`
  - 사용량: `/api/usage/me`, `/api/admin/usage`

### RAG/매칭 엔진
- `engine.py` (ChromaDB + OpenAI 임베딩)
- `rfx_analyzer.py` (요건 추출)
- `matcher.py` (요건 매칭 + 3강도 의견)
- 근거 하이라이트/참조 로직 포함

### 레거시
- Streamlit 코드(`app.py`)는 여전히 존재하고 기능도 많음(관리/실험/의견 A/B 등).
- 현재 사용자-facing 기본 플로우는 React + FastAPI 기준으로 운용 중.

---

## 3) 왜 이렇게 바꿨는지 (핵심 의사결정)

1. **사용자 API 키 입력 제거, 서버 내장 키 방식**
- B2B 데모/파일럿에서 사용자에게 키 입력 요구 시 전환율이 급락함.
- 서버에 `OPENAI_API_KEY` 고정 + 할당량(Quota)로 비용 통제.

2. **Structured Output 엄격화**
- JSON 파싱 실패 줄이기 위해 `json_schema strict` 사용.
- 분석/매칭/챗 응답 포맷 안정성 개선.

3. **오프토픽 차단/정책 라우팅**
- “배고파” 같은 비업무 질의에 도메인 답변 생성 문제를 차단.

4. **의견 기능(3강도)**
- 사실 요약과 별개로 실무형 코멘트를 제공해 데모 설득력 강화.
- `balanced` 선생성, 나머지는 lazy+cache 전략.

5. **랜딩-워크스페이스 통합 UX**
- 사이트/제품 간 문맥 단절을 줄이기 위해 한 프로젝트로 결합.

---

## 4) 최근 완료된 작업 (요약)

### 인증/세션
- Google OAuth 백엔드 라우트 동작 연결.
- 프론트 로그인 모달과 `/auth/google/login` 연동.
- 네비 우측:
  - 비로그인: `로그인` + `Kira bot 실행하기`
  - 로그인 후: `로그아웃` 버튼 노출.

### 브랜드/문구
- `M&S 데이터웍스` 표기 -> `M&S Solutions`로 주요 영역 반영.
- 랜딩 헤드라인 줄바꿈 깨짐 이슈 보정.
- CTA 표기 `Kira bot 실행하기`로 통일.
- 상단 메뉴 영문화: `Product`, `Solutions`, `Pricing`.

### 푸터/법적 페이지
- 푸터 항목 정리:
  - 제거: API 연동, 보안
  - 유지: 제품/회사 기본 항목
- `개인정보처리방침`, `이용약관` 실페이지 추가:
  - `/frontend/kirabot/components/PrivacyPolicy.tsx`
  - `/frontend/kirabot/components/TermsOfService.tsx`
- 로그인 모달의 약관 문구도 해당 페이지로 연결.

### 워크스페이스 UI
- 업로드 영역 통일:
  - 기존 불균형(회사 등록 크게, 분석 문서 선택 작게) 해소
  - `회사 문서 등록`/`분석 문서 등록`을 2열 동일 스타일 카드로 통합.
- 하단 액션 버튼도 2열 동일 너비로 통일.

### Failed to fetch 대응
- 프론트 API 레이어 네트워크 예외 메시지 개선:
  - `/frontend/kirabot/services/kiraApiService.ts`
- CORS 허용 범위 보강:
  - `3000/5173/8080`, `localhost/127.0.0.1`, `null` 대응
  - `/services/web_app/main.py`, `.env`, `.env.example`
- **중요 버그 수정**: Chroma 임베딩 충돌(default vs openai) 시 자동 fallback 컬렉션 전환
  - `/engine.py`
  - 충돌 시 `collection_name__openai`로 자동 생성/전환.

---

## 5) 현재 이슈/주의사항

1. **`Failed to fetch`의 실제 원인은 2종**
- 진짜 네트워크/CORS 문제
- 백엔드 500 문제(임베딩 충돌/초기화 실패)  
→ 현재 둘 다 방어 로직 적용했음.

2. **Python 실행 환경 주의**
- `.venv/bin/python`에는 `fastapi`가 없을 수 있음.
- 현재 로컬에서 `python3.1 services/web_app/main.py`로 실행해야 정상인 환경이 있었음.

3. **`.env` 민감정보**
- 키 값은 문서/커밋/대화에 노출 금지.

---

## 6) 로컬 실행 방법 (현재 권장)

### 백엔드
```bash
cd /Users/min-kyungwook/Downloads/기업전용챗봇세분화
python3.1 services/web_app/main.py
```

### 프론트
```bash
cd /Users/min-kyungwook/Downloads/기업전용챗봇세분화/frontend/kirabot
npm run dev -- --host 127.0.0.1 --port 3000
```

### 필수 점검
```bash
curl -i http://localhost:8000/healthz
```

### 프론트 env 확인
`/frontend/kirabot/.env.local`
```env
VITE_KIRA_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_LOGIN_URL=http://localhost:8000/auth/google/login
VITE_AUTH_ME_URL=http://localhost:8000/auth/me
```

---

## 7) 다음 AI가 바로 할 일 (우선순위)

1. **E2E 안정화**
- 실제 파일 업로드 -> 분석 -> 챗 질의 -> 근거 페이지 이동까지 1회 완주.
- 브라우저 콘솔 에러 0건 목표.

2. **로그아웃 UX 최종**
- 로그아웃 후 모달/세션/뷰 상태가 항상 일관적인지 확인.

3. **정책/약관 고도화**
- 회사 실제 사업자정보(상호, 주소, 연락처, 개인정보책임자) 반영.
- 법무 검토 전제 문구 정리.

4. **백엔드 실행환경 통일**
- `.venv`에 FastAPI 포함되게 requirements 재정비 또는 실행 스크립트 고정.

5. **배포 준비**
- Railway 기준 환경변수 템플릿 정리.
- 프론트 API URL/쿠키/콜백 URL 정합성 점검.

---

## 8) Codex CLI에 붙여넣을 인수인계 프롬프트

```text
다음 프로젝트를 이어서 작업해줘.

[프로젝트]
- 경로: /Users/min-kyungwook/Downloads/기업전용챗봇세분화
- 프론트: /frontend/kirabot (React/Vite)
- 백엔드: /services/web_app/main.py (FastAPI)

[현재 상태]
1) Google OAuth 로그인/로그아웃 라우트 연결됨 (/auth/google/login, /auth/google/callback, /auth/me, /auth/logout)
2) 네비/브랜드 문구 일부 변경 완료
   - 메뉴: Product / Solutions / Pricing
   - 브랜드: M&S Solutions 표기 반영
3) 푸터에서 API 연동/보안 제거, 개인정보처리방침/이용약관 실제 페이지 연결 완료
4) 워크스페이스 업로드 UI 통일 완료
   - 회사 문서 등록/분석 문서 등록 2열 카드형
5) Failed to fetch 대응 작업 완료
   - kiraApiService 네트워크 에러 메시지 개선
   - CORS 확장
   - engine.py의 Chroma embedding conflict 자동 전환 패치

[주의]
- .env 비밀키 절대 출력 금지.
- 현재 환경에서 .venv python에 fastapi가 없을 수 있으므로, 실행 전 python 경로 확인 필요.
- 백엔드 포트는 8000 기준.

[요청 작업]
1) E2E 테스트(업로드/분석/챗/근거이동) 수행 후 실패 지점 고쳐줘.
2) 로그인/로그아웃 UX를 더 명확하게 정리해줘(상태 전환 깜빡임, 에러 문구 포함).
3) 프론트 시각 일관성(버튼/간격/카드 정렬)을 한번 더 다듬어줘.
4) 변경 후 npm build + 핵심 API 헬스체크 결과를 보고해줘.

[검증 명령]
- backend: python3.1 services/web_app/main.py
- frontend: cd frontend/kirabot && npm run dev -- --host 127.0.0.1 --port 3000
- health: curl -i http://localhost:8000/healthz
```

---

## 9) 참고 파일
- `/services/web_app/main.py`
- `/engine.py`
- `/frontend/kirabot/App.tsx`
- `/frontend/kirabot/components/Dashboard.tsx`
- `/frontend/kirabot/components/Navbar.tsx`
- `/frontend/kirabot/components/Footer.tsx`
- `/frontend/kirabot/components/PrivacyPolicy.tsx`
- `/frontend/kirabot/components/TermsOfService.tsx`
- `/frontend/kirabot/services/kiraApiService.ts`
- `/frontend/kirabot/services/authService.ts`

