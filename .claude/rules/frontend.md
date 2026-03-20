---
paths:
  - "frontend/**"
  - "*.tsx"
  - "*.ts"
---

## MANDATORY

### Chat UI 구조
```
ChatLayout.tsx (Sidebar + ChatArea + ContextPanel)
  ├── Sidebar.tsx — 대화 목록 + 새 대화 + 이름 변경/삭제
  ├── ChatArea.tsx — 메시지 스트림 + 입력창
  └── ContextPanel.tsx — 우측 패널 (문서 미리보기, 공고 상세)
```

### 대화 FSM (`ConversationPhase`)
```
greeting → bid_search_input → bid_search_results → bid_analyzing → doc_chat
         → doc_upload_company → doc_upload_target → doc_analyzing → doc_chat
         → bid_eval_running → bid_eval_results
```

### 규칙
- 기존 Tailwind 클래스 재사용, 신규 className 최소화
- JSX 다중 형제 조건부 렌더링: `{condition && (<>...</>)}` Fragment 사용
- `useConversationFlow.ts`의 FSM 전환 순서 보존
- 상태 변경은 `ChatContext.tsx` dispatch 기반으로 수행

### 메시지 타입 (7종)
`text`, `button_choice`, `bid_card_list`, `analysis_result`, `inline_form`, `file_upload`, `status`

## PREFER
- 프론트엔드 사전 검증에 의존하지 않고 백엔드에서도 필수 필드 + 타입 체크
