# KiraBot Frontend (AI Studio Source + Kira Engine Merge)

이 폴더는 AI Studio에서 만든 React UI를 기준으로, Kira Python 분석 엔진 API(`services/web_app/main.py`)와 연결한 프론트엔드입니다.

## 로컬 실행

1. 프론트 의존성 설치
```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화/frontend/kirabot"
npm install
```

2. API 서버 주소 설정 (`.env.local`)
```bash
VITE_KIRA_API_BASE_URL=http://localhost:8010
# 권장: OAuth도 같은 FastAPI 포트 사용
VITE_GOOGLE_LOGIN_URL=http://localhost:8010/auth/google/login
VITE_AUTH_ME_URL=http://localhost:8010/auth/me
```

3. 개발 서버 실행
```bash
npm run dev
```

## 백엔드 연동 엔드포인트

- `POST /api/session`
- `POST /api/session/stats`
- `POST /api/company/upload`
- `POST /api/company/clear`
- `POST /api/analyze/upload`
- `POST /api/chat`

백엔드는 프로젝트 루트의 `services/web_app/main.py`를 사용합니다.
