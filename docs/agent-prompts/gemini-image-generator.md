# Gemini 3.1 Pro — 이미지 생성 프롬프트

> 나노바나나 프로 페이지에서 모델을 "Gemini 3.1 Pro"로 설정 후 사용합니다.

---

## 기본 스타일 가이드

KiraBot의 디자인 톤:
- **색상**: 파란색 계열 (primary-600 #4F46E5 ~ primary-800 #3730A3), 슬레이트 회색
- **스타일**: 깔끔한 SaaS, 모던 비즈니스, 라운드 코너
- **분위기**: 신뢰감, 전문성, AI 기술력

---

## 프롬프트 템플릿 (용도별 복사 사용)

### 1. 히어로 일러스트레이션

```
Create a modern, clean illustration for a B2B SaaS landing page hero section.

Theme: AI-powered public procurement bid analysis platform
Style: Flat illustration, isometric or 2.5D perspective
Color palette: Primary blue (#4F46E5), light slate backgrounds, white accents
Elements to include:
- A laptop or dashboard screen showing charts/analysis
- Document icons (PDF, bid notices) flowing into the system
- AI/neural network visual element (subtle, not overwhelming)
- Korean government building silhouette (optional, subtle background)

Mood: Professional, trustworthy, technologically advanced
Dimensions: 16:9 landscape, suitable for web hero banner
No text in the image.
Background: Transparent or light gradient (#F8FAFC to white)
```

### 2. 기능 카드 아이콘

```
Create a set of 10 minimal flat icons for a SaaS feature showcase.
Each icon should be 128x128px, single color (#4F46E5 blue) on transparent background.
Style: Rounded, modern, consistent stroke width (2px equivalent)

Icons needed:
1. Document analysis (magnifying glass + document)
2. AI matching (puzzle pieces connecting)
3. Bid search (search bar + list)
4. Smart alerts (bell + sparkle)
5. Auto-download (cloud + download arrow)
6. Multi-document support (stacked files: PDF, HWP, Excel)
7. Chat Q&A (speech bubbles)
8. GO/NO-GO decision (checkmark in shield)
9. Report generation (clipboard + chart)
10. Email notification (envelope + clock)

Consistent style across all icons. No text.
```

### 3. 상세 페이지 배경/패턴

```
Create a subtle geometric pattern for a SaaS web application background.
Style: Very light, barely visible pattern on white (#FFFFFF) background
Elements: Hexagons, dots, thin connecting lines
Color: Light blue-gray (#E2E8F0) at 20-30% opacity
Usage: Tiling background pattern for dashboard/detail pages
Dimensions: 400x400px seamless tile
Minimal, professional, non-distracting
```

### 4. 빈 상태(Empty State) 일러스트

```
Create a friendly, minimal illustration for an empty state page.
Theme: "No search results found" or "Start your first analysis"
Style: Flat illustration, soft colors, warm feeling
Color palette: Blue (#4F46E5) primary, light gray accents
Elements: A character or abstract shape looking/searching, empty box or list
Mood: Encouraging, not sad — "Let's get started!"
Dimensions: 1:1 square, 400x400px
No text in the image.
Transparent background.
```

---

## 사용 방법

1. 나노바나나 프로 페이지 열기
2. 모델: **Gemini 3.1 Pro** 선택
3. 위 템플릿 중 필요한 것을 복사하여 입력
4. 생성된 이미지 다운로드
5. 프로젝트 폴더에 저장: `frontend/kirabot/public/images/`
6. Claude Code에 이미지 경로 전달

```bash
# Claude Code에서 사용
# Task tool → subagent_type: "asset-integrator"
# prompt: "이미지 /path/to/image.png를 Hero 섹션에 추가해줘"
```

---

## 이미지 네이밍 규칙

| 용도 | 파일명 패턴 | 예시 |
|------|------------|------|
| 히어로 | `hero-{description}.webp` | `hero-ai-analysis.webp` |
| 기능 아이콘 | `icon-{feature}.svg` | `icon-smart-alert.svg` |
| 배경 패턴 | `bg-{type}.png` | `bg-hexagon-pattern.png` |
| 빈 상태 | `empty-{context}.svg` | `empty-no-results.svg` |
