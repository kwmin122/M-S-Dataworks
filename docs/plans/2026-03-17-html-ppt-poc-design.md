# HTML PPT PoC — C-lite 설계 + 구현 계획

## 목표

실제 공고 1건 기준으로 **6장 HTML 슬라이드 프리뷰**를 생성하고,
동일 입력으로 만든 기존 PPTX와 **side-by-side 비교**할 수 있게 한다.

**비교 기준 3개:**
1. 시각 품질
2. 메시지 선명도
3. 회사 맞춤화 정도

**지금 하지 않는 것:**
- HTML → PPTX 변환 체인
- 웹 편집기
- WBS 연결
- 콘텐츠 생성 전면 재설계

---

## Source of Truth

### `presentation_slides_v1` JSON 스키마

```jsonc
{
  "schema": "presentation_slides_v1",
  "metadata": {
    "title": "사업명",
    "company_name": "회사명",
    "generated_at": "2026-03-17T12:00:00Z",
    "rfp_title": "RFP 제목",
    "total_slides": 6,
    "duration_min": 30
  },
  "theme": {
    "primary_color": "#003764",    // KRDS Blue 900
    "accent_color": "#0066CC",
    "text_color": "#444444",       // Gray 700
    "bg_color": "#FFFFFF",
    "font_family": "Pretendard, sans-serif"
  },
  "slides": [
    {
      "type": "cover",
      "title": "사업명",
      "subtitle": "제안사 회사명",
      "date": "2026.03",
      "logo_url": null
    },
    {
      "type": "agenda",
      "title": "목차",
      "items": ["사업 이해", "수행 전략", "기술 방안", "수행 체계", "기대 효과"]
    },
    {
      "type": "content",
      "title": "슬라이드 제목",
      "message": "핵심 메시지 1줄",
      "body": "본문 마크다운",
      "bullets": ["요점 1", "요점 2"],
      "speaker_notes": "발표자 노트"
    },
    {
      "type": "comparison",
      "title": "AS-IS vs TO-BE",
      "left_label": "현재",
      "right_label": "제안",
      "left_items": ["문제점 1", "문제점 2"],
      "right_items": ["해결책 1", "해결책 2"]
    },
    {
      "type": "timeline",
      "title": "추진 일정",
      "phases": [
        {"name": "1단계", "period": "1~3월", "tasks": ["요구분석", "설계"]},
        {"name": "2단계", "period": "4~6월", "tasks": ["개발", "테스트"]}
      ]
    },
    {
      "type": "closing",
      "title": "감사합니다",
      "contact": "담당자 연락처",
      "message": "마무리 메시지"
    }
  ],
  "qna": [
    {"question": "예상질문", "answer": "모범답변", "category": "기술"}
  ]
}
```

**기존 SlideContent와의 관계:**
- `phase2_models.SlideContent` → `presentation_slides_v1.slides[]`로 변환
- 기존 PPTX 경로는 SlideContent → ppt_assembler 그대로 유지 (fallback)
- HTML 경로는 slides JSON → React 컴포넌트 렌더링

---

## 아키텍처

```
ppt_orchestrator.py
  ├─ plan_slides() → SlideContent[] (기존)
  ├─ extract_slide_content() (기존)
  ├─ ppt_assembler.assemble_pptx() → .pptx (기존 fallback)
  └─ NEW: slides_to_json() → presentation_slides_v1 JSON
       └─ API 응답에 포함 → 프론트엔드로 전달

프론트엔드:
  PptViewer.tsx
    ├─ 기존: PPTX 다운로드 링크
    └─ NEW: HTML 슬라이드 프리뷰 (SlideRenderer.tsx)
         ├─ CoverSlide.tsx
         ├─ AgendaSlide.tsx
         ├─ ContentSlide.tsx
         ├─ ComparisonSlide.tsx
         ├─ TimelineSlide.tsx
         └─ ClosingSlide.tsx
```

---

## 구현 계획 (5 Tasks)

### Task 1: Slide JSON 스키마 + 변환 함수

**Files:**
- `rag_engine/slide_schema.py` (신규)
- `rag_engine/tests/test_slide_schema.py` (신규)

**내용:**
- `presentation_slides_v1` Pydantic 모델 정의
- `slides_to_json(slides: list[SlideContent], metadata: dict) -> dict` 변환 함수
- 기존 SlideContent → 새 JSON 스키마 매핑

**검증:** 6개 슬라이드 타입 변환 테스트

---

### Task 2: API 응답에 slides JSON 추가

**Files:**
- `rag_engine/ppt_orchestrator.py` (수정)
- `rag_engine/main.py` (수정 — /api/generate-ppt 응답에 slides_json 추가)

**내용:**
- ppt_orchestrator 반환값에 `slides_json` 필드 추가
- 기존 PPTX 생성은 그대로 유지
- API 응답: `{pptx_filename, slides_json, slide_count, ...}`

**검증:** API 호출 시 slides_json이 응답에 포함되는지

---

### Task 3: HTML 슬라이드 렌더러 (React)

**Files:**
- `frontend/kirabot/components/slides/SlideRenderer.tsx` (신규)
- `frontend/kirabot/components/slides/CoverSlide.tsx` (신규)
- `frontend/kirabot/components/slides/AgendaSlide.tsx` (신규)
- `frontend/kirabot/components/slides/ContentSlide.tsx` (신규)
- `frontend/kirabot/components/slides/ComparisonSlide.tsx` (신규)
- `frontend/kirabot/components/slides/TimelineSlide.tsx` (신규)
- `frontend/kirabot/components/slides/ClosingSlide.tsx` (신규)
- `frontend/kirabot/components/slides/slideTheme.ts` (신규 — KRDS CSS 토큰)

**내용:**
- 16:9 비율 슬라이드 (960×540 viewport, CSS scale)
- KRDS 디자인 토큰 (색상, 폰트, 여백)
- 6개 슬라이드 타입별 레이아웃
- 좌우 화살표 네비게이션
- 발표자 노트 토글

**검증:** Storybook 또는 직접 렌더링으로 6개 타입 시각 확인

---

### Task 4: PptViewer에 HTML 프리뷰 연결

**Files:**
- `frontend/kirabot/components/settings/documents/PptViewer.tsx` (수정)
- `frontend/kirabot/hooks/useConversationFlow.ts` (수정 — slides_json 저장)

**내용:**
- slides_json을 localStorage에 저장 (기존 kira_last_presentation 확장)
- PptViewer: 탭 전환 (HTML 프리뷰 | PPTX 다운로드)
- SlideRenderer에 slides JSON 전달

**검증:** PPT 생성 후 문서 탭에서 HTML 프리뷰 표시

---

### Task 5: Side-by-side 비교 + 회귀 테스트

**내용:**
- 실제 공고 1건으로 기존 PPTX + 새 HTML 동시 생성
- 비교 기준 3개 (시각/메시지/맞춤화) 주관 평가
- rag_engine 전체 회귀
- 프론트엔드 타입체크

**완료 기준:**
- HTML 6장 프리뷰가 DocumentWorkspace에서 렌더링
- 기존 PPTX 다운로드 정상 동작 (fallback)
- 전체 테스트 green

---

## 리스크

| 리스크 | 완화 |
|--------|------|
| HTML 프리뷰가 기대보다 안 좋을 수 있음 | PoC라서 빠르게 판단, 안 좋으면 중단 |
| slides JSON 스키마 변경 시 프론트+백 모두 수정 | v1 스키마를 충분히 넓게 정의 |
| 기존 PPTX 경로 회귀 | fallback으로 유지, 건드리지 않음 |

## 수정 파일 요약

| 파일 | Task |
|------|------|
| `rag_engine/slide_schema.py` | 1 (신규) |
| `rag_engine/tests/test_slide_schema.py` | 1 (신규) |
| `rag_engine/ppt_orchestrator.py` | 2 |
| `rag_engine/main.py` | 2 |
| `frontend/.../slides/SlideRenderer.tsx` | 3 (신규) |
| `frontend/.../slides/*.tsx` (6개) | 3 (신규) |
| `frontend/.../slides/slideTheme.ts` | 3 (신규) |
| `frontend/.../PptViewer.tsx` | 4 |
| `frontend/.../useConversationFlow.ts` | 4 |
