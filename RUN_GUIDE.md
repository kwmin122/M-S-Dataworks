# Kira 실행 가이드 (웹 병합 버전)

## 1) 실행 명령어

### 터미널 1: Kira 분석 API 서버
```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화"
pip install -r requirements.txt
python services/web_app/main.py
```

### 터미널 2: AI Studio 기반 React 사이트
```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화/frontend/kirabot"
npm install
printf "VITE_KIRA_API_BASE_URL=http://localhost:8010\n" > .env.local
npm run dev
```

접속: `http://localhost:3000`

## 2) 사용 방법

1. 랜딩에서 `Kira 실행` 클릭
2. `회사 문서 등록` 카드에서 회사 문서 업로드
3. `분석 문서 업로드` 카드에서 대상 문서 업로드
4. `문서 분석 실행` 클릭
5. 왼쪽 패널에서 적합도/요건 매칭/Kira 의견 확인

## 3) 빌드(배포 전)

```bash
cd "/Users/min-kyungwook/Downloads/기업전용챗봇세분화/frontend/kirabot"
npm run build
```

`frontend/kirabot/dist`가 생성되면, `services/web_app/main.py`가 해당 정적 파일을 자동 서빙합니다.
