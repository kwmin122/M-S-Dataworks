# Kira 병합 작업 문서 (AI Studio 사이트 + 기존 분석엔진)

## 1. 확인한 원본(사용자 제공)

`/Users/min-kyungwook/Downloads/kirabot` 내부를 기준으로 확인했습니다.

- `README.md`: AI Studio에서 생성한 React/Vite 앱 실행 안내
- `App.tsx`: 랜딩/대시보드 뷰 전환 구조
- `components/Hero.tsx`: Spline 3D 히어로 섹션
- `components/Dashboard.tsx`: 기존 Mock/Gemini 데모 대시보드
- `services/geminiService.ts`: Gemini 직접 호출 로직(병합 후 미사용)

## 2. 병합 목표

- Streamlit UI를 직접 노출하지 않고, AI Studio 기반 웹사이트(React)에서 바로 실행
- 기존 Python 분석 엔진(`rfx_analyzer.py`, `matcher.py`, `engine.py`)은 그대로 재사용
- 프론트는 API 호출로 업로드/분석/결과 확인을 수행

## 3. 병합 결과 구조

- 프론트: `frontend/kirabot`
- 웹 API: `services/web_app/main.py`
- 분석 엔진: 프로젝트 루트의 기존 Python 모듈 재사용

## 4. 구현 Step-by-step

1. AI Studio 소스를 프로젝트로 편입
- `/Users/min-kyungwook/Downloads/kirabot` → `frontend/kirabot`

2. 백엔드 API 추가
- `services/web_app/main.py` 생성
- 세션, 회사문서 업로드/초기화, 문서 분석 API 구현

3. 프론트 API 연동
- `frontend/kirabot/services/kiraApiService.ts` 추가
- `frontend/kirabot/components/Dashboard.tsx`를 Mock에서 실제 API 호출형으로 교체

4. 랜딩/브랜드 병합
- `Navbar`, `Hero`, `Footer`를 M&S KiraBot 톤으로 조정

5. 빌드 오류 제거
- `frontend/kirabot/index.html`의 importmap 제거
- `frontend/kirabot/index.css` 추가 및 `index.tsx`에서 import

## 5. 실행 방법

### 5-1. Python API 서버
```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화"
pip install -r requirements.txt
python services/web_app/main.py
```

### 5-2. React 프론트
```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화/frontend/kirabot"
npm install
printf "VITE_KIRA_API_BASE_URL=http://localhost:8010\n" > .env.local
npm run dev
```

브라우저: `http://localhost:3000`

## 6. 사용 플로우

1. 랜딩에서 `Kira 실행` 진입
2. 회사 문서 업로드(복수)
3. 분석 문서 업로드(단일)
4. 적합도/추천/요건 매칭/Kira 의견 확인

## 7. 알려진 범위

- 현재 로그인은 게스트 모드 기준으로 동작
- Streamlit UI는 병합 경로에서 제외 (분석 엔진만 API로 재사용)
- `services/geminiService.ts`는 남아 있으나 현재 실행 흐름에서 사용하지 않음
