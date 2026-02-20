# M&S 데이터웍스 Kira 문서 분석 어시스턴트

근거 기반 문서 분석 + 자격 매칭 엔진을 웹사이트에서 직접 실행할 수 있도록 구성한 프로젝트입니다.

## 핵심 변경 (v7)
- 서버 내장 OpenAI 키 고정(`OPENAI_API_KEY`), 사용자 API 키 입력 UI 제거
- OpenAI Structured Outputs strict 모드 기본 적용(`OPENAI_STRICT_JSON_ONLY=1`)
- 사용량 quota 강제(일일 chat / 월간 analyze) + 관리자 사용량 대시보드 추가
- 임베딩 모델 고정: `text-embedding-3-small`
- 소셜 로그인 우선 구조(`AUTH_MODE=social_only`)
- 문서 업로드 UX 개선(분석할 문서/회사 문서 분리, F5 복원 체감 강화)
- 문서 초기화(확인 2단계 + 쿨다운)
- PDF 뷰어 의존성 preflight(`PDF_VIEWER_REQUIRED=1`)
- 의견 3강도 + 균형형 A/B 실험 로깅
- 관리자 대시보드(RBAC, KPI 7/30/90, CSV, 임계치 알림)
- AI Studio React 사이트(`frontend/kirabot`)와 Kira Python 엔진 API 병합

## 아키텍처
- `frontend/kirabot` : AI Studio 기반 React 웹사이트
- `services/web_app/main.py` : React + Kira 엔진 연결 API
- `services/auth_gateway/main.py` : 소셜 로그인/Auth Gateway

인증 토큰은 URL 파라미터로 전달하지 않고, `POST /auth/session/exchange` + `HttpOnly` 쿠키 방식으로만 처리합니다.

## 빠른 시작 (웹 병합 경로)
```bash
pip install -r requirements.txt
python services/web_app/main.py
```

별도 터미널:
```bash
cd frontend/kirabot
npm install
printf "VITE_KIRA_API_BASE_URL=http://localhost:8010\n" > .env.local
npm run dev
```

## Streamlit 경로(레거시 유지)
```bash
streamlit run app.py
```

## Auth Gateway 실행 (선택)
```bash
pip install -r services/auth_gateway/requirements.txt
python services/auth_gateway/main.py
```

### Auth Gateway API
- `POST /auth/session/exchange`
  - 입력: Supabase `access_token`(POST body), `provider`, `redirect_path`
  - 동작: JWKS 기반 JWT 검증 후 내부 세션 발급, `kira_auth` HttpOnly 쿠키 설정
- `POST /auth/logout`
  - 동작: 내부 세션 무효화 + 쿠키 삭제
- `GET /healthz`
  - 동작: 헬스체크

## 필수 환경변수
`.env.example`를 복사해서 `.env`를 만든 뒤 값 설정:
- OpenAI: `OPENAI_API_KEY`
- Strict JSON: `OPENAI_STRICT_JSON_ONLY=1`
- Quota: `QUOTA_*` (`QUOTA_CHAT_DAILY_LIMIT`, `QUOTA_ANALYZE_MONTHLY_LIMIT` 등)
- Social/Auth: `AUTH_MODE`, `SOCIAL_LOGIN_GOOGLE_URL`, `SOCIAL_LOGIN_KAKAO_URL`, `SOCIAL_AUTH_LOGOUT_URL`
- Supabase JWT verify: `SUPABASE_JWKS_URL`, `SUPABASE_ISSUER`, `SUPABASE_AUDIENCE`
- PDF 의존성 강제: `PDF_VIEWER_REQUIRED=1`
- 문서 초기화 보호: `COMPANY_DOC_DELETE_COOLDOWN_SECONDS=60`

## UX 동작 요약
- 비로그인 상태: 웰컴 카드 + 소셜 로그인 버튼 표시
- 로그인 상태: 저장된 회사 문서 목록 즉시 복원(API 키 없어도 목록 표시)
- 회사 문서:
  - 업로드
  - 저장 문서 재색인
  - 문서 초기화(버튼 2회 확인 + 1분 쿨다운)
- 분석 문서:
  - 업로드 후 분석
  - 분석 중 안내 문구: "문서 길이에 따라 수 분이 걸릴 수 있습니다"
- 추천 질문:
  - 2열 카드형 버튼
  - 긴 문장 자동 줄바꿈

## PDF 뷰어 운영 정책
- 기본: `PDF_VIEWER_REQUIRED=1`
- 필수 모드에서 `streamlit-pdf-viewer`가 누락되면 분석 시작 차단 + 운영 오류 표시
- 선택 모드(`PDF_VIEWER_REQUIRED=0`)에서만 폴백 렌더 허용

## Kira 의견 (Phase 1.5)
- 사실 요약(`summary`)과 의견 블록 분리
- 강도: `보수적 / 균형 / 공격적`
- `balanced`는 기본 선생성, 나머지는 첫 선택 시 lazy 생성 + 캐시
- 균형형 A/B 실험
  - A: 결론 우선형
  - B: 리스크 관리형
- 실험 로그: `reports/opinion_experiment.jsonl`
- 면책문구 고정 출력

## 관리자 대시보드
- 권한: `super_admin`, `operator`
- KPI 기간: 7/30/90일
- CSV 내보내기: 사용자/업로드/사용량/정책/의도/최근이벤트/알림
- 임계치 알림: 차단율 급증, 실패율 증가
- 사용량 탭: 오늘/이번달(chat, analyze) + 사용자/세션별 사용량

## 테스트
```bash
pytest -q
python -m py_compile app.py matcher.py chat_router.py rfx_analyzer.py document_parser.py
```

## Railway 실배포 전 체크
```bash
python scripts/run_railway_predeploy_checklist.py \
  --base-url https://your-domain.com \
  --out reports/railway_predeploy_checklist.md
```

자동 체크:
1. py_compile
2. pytest 핵심셋
3. 소셜 로그인 URL(구글/카카오) 상태 확인
4. `/tool` 접속 상태 확인
5. `streamlit_pdf_viewer` import 확인

수동 체크:
1. 소셜 로그인 후 `/tool` 자동 진입
2. 회사 문서 업로드 후 F5 시 목록 유지
3. 문서 초기화 쿨다운 동작
4. 추천 질문 모바일 오버플로우 없음
5. 문서유형/정책 UI 미노출
