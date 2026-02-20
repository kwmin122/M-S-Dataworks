# Google OAuth E2E 체크리스트 (Local)

## 0) 사전 준비
- Google Cloud Console OAuth 클라이언트 생성 완료
- `Authorized JavaScript origins`: `http://localhost:3000`
- `Authorized redirect URIs`: `http://localhost:8000/auth/google/callback`
- OAuth 동의화면에 테스트 사용자(Gmail) 등록

## 1) 환경변수 확인
- `/Users/min-kyungwook/Downloads/기업전용챗봇세분화/.env`
  - `WEB_API_PORT=8000`
  - `GOOGLE_OAUTH_CLIENT_ID=...`
  - `GOOGLE_OAUTH_CLIENT_SECRET=...`
  - `GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback`
  - `GOOGLE_OAUTH_POST_LOGIN_URL=http://localhost:3000/`
  - `AUTH_COOKIE_SECURE=0`
- `/Users/min-kyungwook/Downloads/기업전용챗봇세분화/frontend/kirabot/.env.local`
  - `VITE_KIRA_API_BASE_URL=http://localhost:8000`
  - `VITE_GOOGLE_LOGIN_URL=http://localhost:8000/auth/google/login`
  - `VITE_AUTH_ME_URL=http://localhost:8000/auth/me`

## 2) 서버 실행
### 터미널 A (FastAPI)
```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화"
python services/web_app/main.py
```

### 터미널 B (Frontend)
```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화/frontend/kirabot"
npm run dev
```

## 3) 브라우저 수동 E2E
1. `http://localhost:3000` 접속
2. `Kira 실행` 클릭
3. `Google 계정으로 계속하기` 클릭
4. Google 로그인/동의 완료
5. `http://localhost:3000`으로 복귀 확인
6. 대시보드 자동 진입 확인
7. DevTools Application/Cookies에서 `kira_auth` 존재 확인
8. 새로고침(F5) 후 로그인 유지 확인

## 4) API 점검
- `GET http://localhost:8000/auth/me` 응답
  - 기대: `{"authenticated": true, "user": {...}}`

## 5) 실패 시 점검 포인트
- `redirect_uri_mismatch`:
  - Google Console URI와 `.env` `GOOGLE_OAUTH_REDIRECT_URI` 완전 일치 여부
  - `http/https`, 포트, trailing slash 확인
- 로그인 후 다시 랜딩으로만 돌아오고 인증 안 됨:
  - 브라우저 쿠키 차단 여부
  - `AUTH_COOKIE_SECURE=0` 여부(local http)
- `Google 로그인 시작 실패`:
  - `GOOGLE_OAUTH_CLIENT_ID/SECRET` 누락 여부
