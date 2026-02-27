# 관리자 페이지 설계

## 목표

`bill.min122@gmail.com` Google 로그인 사용자를 관리자로 설정하고, **사용량 대시보드 + 알림 설정 관리** 관리자 페이지 제공.

## 인증

### 관리자 판별

- 백엔드: 기존 `_admin_usernames()` 활용 (환경변수 `ADMIN_USERNAMES`)
- `ADMIN_USERNAMES=bill.min122` 설정
- `/auth/me` 응답에 `isAdmin: boolean` 필드 추가

### 프론트엔드 접근 제어

- `AdminRoute` 래퍼 컴포넌트: `user.isAdmin`이 아니면 `/chat`으로 리다이렉트
- 관리자만 사이드바/설정 메뉴에 "관리자" 링크 표시

## 페이지 구성

### 1. 사용량 대시보드 (`/admin`)

**API**: 기존 `/api/admin/usage` 활용 (이미 구현됨)

반환 데이터:
- `overview`: 오늘/이번달 chat/analyze 횟수
- `by_actor`: 사용자별 사용량 (최근 300건)

**UI**:
- 상단: 통계 카드 4개 (오늘 채팅, 오늘 분석, 월간 채팅, 월간 분석)
- 하단: 사용자별 테이블 (사용자명, 채팅 수, 분석 수, 최근 활동)

### 2. 알림 관리 (`/admin/alerts`)

**새 API 엔드포인트**:
- `GET /api/admin/alerts` — 모든 alert config + state 목록
- `DELETE /api/admin/alerts/{config_id}` — 알림 설정 삭제
- `POST /api/admin/alerts/{config_id}/send-now` — 즉시 발송

**UI**:
- 알림 규칙 카드 목록
- 각 카드: 이메일, 키워드, 스케줄, 활성 상태, 마지막 발송 시각
- 삭제 버튼 + 즉시 발송 버튼

## 네비게이션

- 관리자 로그인 시 사이드바 하단에 "관리자" 아이콘 링크 표시
- `/admin` → 사용량 대시보드
- `/admin/alerts` → 알림 관리
- 탭으로 전환

## 변경 파일

| 파일 | 변경 |
|------|------|
| `services/web_app/main.py` | `/auth/me`에 `isAdmin` 추가, 알림 관리 API 3개 |
| `frontend/kirabot/types.ts` | `User`에 `isAdmin` 추가 |
| `frontend/kirabot/App.tsx` | `/admin` 라우트 + `AdminRoute` 래퍼 |
| `frontend/kirabot/components/admin/AdminDashboard.tsx` | 사용량 대시보드 (신규) |
| `frontend/kirabot/components/admin/AdminAlerts.tsx` | 알림 관리 (신규) |
| `frontend/kirabot/components/layout/Sidebar.tsx` | 관리자 링크 (조건부) |
| `frontend/kirabot/services/kiraApiService.ts` | admin API 클라이언트 |
