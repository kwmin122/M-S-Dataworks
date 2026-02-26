# Alert Management UX Improvements

**Goal:** 이메일에 설정 변경 링크 추가 + 설정>일반에 알림 요약 카드 추가

## 1. 이메일 하단 링크

확인 이메일(`_send_confirmation_email`) + 알림 이메일(`_send_alert_email`) 하단에:
- "알림 설정을 변경하거나 해제하려면" + 링크
- URL: `{APP_BASE_URL}/settings/alerts`
- 환경변수: `APP_BASE_URL` (기본값: `https://kirabot.co.kr`)

## 2. 설정 > 일반 알림 요약

`SettingsGeneral.tsx`에 알림 설정 요약 카드:
- 설정 있으면: 상태 + 이메일 + 빈도 + 규칙 수 + [변경] + [해제] 버튼
- 설정 없으면: "알림 미설정" + [설정하기] 버튼
- localStorage `kirabot_alert_session_id`로 config 조회

## 변경 파일

- `services/web_app/main.py` — 이메일 HTML 하단 링크
- `frontend/kirabot/components/settings/SettingsGeneral.tsx` — 알림 카드
