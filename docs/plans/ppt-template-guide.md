# PPT 디자인 가이드 (KRDS 기반 공공기관 표준)

> 원본: `data/templates/공공기관_PPT_디자인가이드_KRDS.pdf`
> 참고: 대한민국 정부 디자인 시스템(krds.go.kr), 전자정부 웹사이트 품질관리 지침, WCAG 2.1 AA

---

## 01. 디자인 철학 및 7대 원칙

1. **사용자 중심** — 청중의 의사결정을 돕는 명확한 구조
2. **포용적 접근** — 색상 대비, 폰트 크기 등 접근성 기준 준수
3. **기관 개별성** — 해당 기관 CI를 정확히 반영
4. **간결성** — 슬라이드당 핵심 메시지 1개 원칙
5. **명료성** — 전문용어 최소화, 직관적 시각화
6. **맥락 적합** — 보고 상황에 맞는 정보 깊이 조절
7. **신뢰 구축** — 출처 명시, 데이터 기반 근거

---

## 02. 색상 시스템 (Color System)

최대 3색 원칙. 배경은 흰색/연회색, 텍스트는 짙은 회색.

### PRIMARY — 정부 청색 (Government Blue)

| 토큰 | HEX | 용도 |
|---|---|---|
| Blue 900 | `#003764` | 제목 바, 표지 배경 (가장 진한 주색) |
| Blue 800 | `#004A8F` | 보조 강조 |
| Blue 700 | `#005DB8` | 호버/액티브 |
| Blue 600 | `#0070E0` | 링크, 강조 텍스트 |
| Blue 500 | `#1A85FF` | 아이콘, 불릿 |
| Blue 400 | `#4DA3FF` | 차트 보조색 |
| Blue 100 | `#E6F0FF` | 연한 배경, 카드 배경 |
| Blue 50  | `#F0F6FF` | 가장 연한 배경 |

### NEUTRAL — 무채색 (Grayscale)

| 토큰 | HEX | 용도 |
|---|---|---|
| Gray 900 | `#1A1A1A` | 제목 텍스트 |
| Gray 700 | `#444444` | 본문 텍스트 |
| Gray 500 | `#888888` | 캡션, 보조 텍스트 |
| Gray 200 | `#E5E5E5` | 구분선, 테두리 |

### SEMANTIC — 의미 색상 (Status Colors)

| 토큰 | HEX | 용도 |
|---|---|---|
| Red | `#E8402D` | 경고/감소 |
| Green | `#0D8050` | 성공/증가 |
| Orange | `#E07B54` | 주의/진행중 |
| Teal | `#0D6E6E` | 보조 강조 |

### 접근성 기준
- 큰 텍스트(18pt+): 명암비 3:1 이상
- 작은 텍스트: 명암비 4.5:1 이상
- WCAG AA 준수 필수

---

## 03. 타이포그래피 시스템 (Typography)

폰트는 2~3개로 제한. 제목은 고딕 Bold, 본문은 고딕 Regular.

### 폰트 우선순위

| 순위 | 폰트 | 특징 |
|---|---|---|
| 1순위 추천 | **Pretendard** | KRDS 공식 표준 서체, 가독성 최우수, 무료 배포 |
| 2순위 대안 | **S-Core Dream** | 공공기관 다수 사용, 9가지 굵기 지원 |
| 3순위 대안 | **NanumSquare Neo** | 네이버 제작, 높은 호환성, 기본 고딕 대안 |

### 폰트 크기 체계 (Type Scale)

| 요소 | 크기 | 굵기 | 예시 |
|---|---|---|---|
| 표지 제목 | 36~40pt | ExtraBold | 공공기관 보고서 |
| 슬라이드 제목 | 24~28pt | Bold | 주요 사업 현황 |
| 소제목 | 18~20pt | SemiBold | 분기별 실적 분석 |
| 본문 | 14~16pt | Regular | 본문 텍스트 예시입니다 |
| 캡션/출처 | 10~12pt | Light | 출처: 통계청, 2025 |

---

## 04. 슬라이드 레이아웃 구조 (Layout Grid)

- **비율**: 16:9 고정 (1920x1080px)
- **3단 구조**: 상단(제목 바) - 중앙(콘텐츠) - 하단(로고/페이지)

### 영역별 사양

| 영역 | 높이 | 내용 |
|---|---|---|
| 상단: 제목 바 | 48px | 슬라이드 제목 + 페이지 번호 (Blue 900 배경, 흰색 텍스트) |
| 중앙: 콘텐츠 | 나머지 | 본문, 차트, 표, KPI 카드 등 |
| 하단: 푸터 | 28px | [기관 로고/명칭] + CONFIDENTIAL |

### 간격 규칙

| 속성 | 값 |
|---|---|
| 여백 (padding) | 24~32px |
| 콘텐츠 간격 (gap) | 16px |
| 모서리 (border-radius) | 4~8px |

---

## 05. 슬라이드 템플릿 6종

### A. 표지 슬라이드 (COVER)
- 진한 파랑(Blue 900) 전면 배경
- 중앙: 사업 제목 (36~40pt, ExtraBold, 흰색)
- 하단: 기관명 · 부서명 + 날짜
- 구분선(accent bar) 삽입

### B. 목차 슬라이드 (TOC)
- 상단: 제목 바 ("목차")
- 본문: 번호(01, 02, 03...) + 섹션명 목록
- 번호는 Blue 600(#0070E0) 강조

### C. 콘텐츠 슬라이드 (CONTENT)
- 상단: 제목 바 (Blue 900 배경)
- 좌측: 소제목 바(Blue 100 배경) + 텍스트/불릿
- 우측 또는 하단: 차트/다이어그램 가능
- 1슬라이드 1메시지 원칙

### D. 데이터/차트 슬라이드 (DATA)
- 상단: 제목 바 (Blue 900 배경)
- KPI 카드 (2~4개 가로 배치):
  - 큰 숫자 (36pt+ Bold)
  - 레이블 (14pt Regular)
  - 증감 표시 (Green/Red + 화살표)
- 하단: 차트 영역

### E. 마무리/감사 슬라이드 (CLOSING)
- 진한 파랑(Blue 900) 전면 배경
- 중앙: "감사합니다" (36~44pt, Bold, 흰색)
- 하단: 부서명 | 전화번호 | 이메일
- 구분선(accent bar) 삽입

### F. 간지(구분) 슬라이드 (DIVIDER)
- 좌측: Blue 900 세로 바 + 섹션 번호 (큰 Bold 흰색)
- 우측: 섹션 제목 (24~28pt Bold) + 설명 텍스트

---

## 06. 데이터 시각화 & 컴포넌트

### 막대 그래프
- 막대 간격 균일
- 색상 4단계 이내 (Blue 400~900)
- Y축 레이블 필수
- 출처 하단 표기

### 표 (Table)
- 헤더 행: Blue 900 배경 + 흰색 텍스트
- 교대 행: 연회색(#F0F6FF) 배경 적용
- 숫자: 우측 정렬 권장
- 테두리: 최소화 (Gray 200)

### KPI 카드
- 카드 배경: 흰색 또는 Blue 50
- 핵심 숫자: 36pt+ Bold (Blue 900 또는 Gray 900)
- 레이블: 14pt Regular (Gray 500)
- 증감 표시: +는 Green(#0D8050), -는 Red(#E8402D) + 화살표 아이콘

---

## 07. 디자인 규칙: DO / DON'T

### DO
- 기관 CI 색상을 주색으로 일관 사용
- 슬라이드당 핵심 메시지 1개만 전달
- 데이터에 출처와 기준 날짜 명시
- 충분한 여백과 고대비 색상 조합 확보
- 직사각형·원형 등 기본 도형으로 구성

### DON'T
- 4가지 이상 색상 혼합 사용 금지
- 장식적 클립아트, 워드아트 사용 금지
- 슬라이드에 텍스트 과밀 배치 금지
- 불필요한 애니메이션/전환 효과 금지
- 저해상도 이미지, 그라데이션 과다 금지

---

## 08. 접근성 체크리스트 (WCAG AA)

- [ ] 텍스트 명암비 4.5:1 이상 확인
- [ ] 본문 폰트 14pt 이상 사용
- [ ] 색상만으로 정보 구분하지 않음
- [ ] 차트에 패턴/레이블 병행 사용
- [ ] 모든 이미지에 대체 텍스트 설정
- [ ] 슬라이드 읽기 순서 논리적 설정
- [ ] 중요 정보를 색상+형태+텍스트로 표현
- [ ] 표에 헤더 행/열 올바르게 지정
- [ ] 링크 텍스트에 URL 의미 설명 포함

---

## ppt_assembler.py 매핑 (코드 적용용)

### 색상 매핑 (DEFAULT_COLORS → KRDS)

```python
KRDS_COLORS = {
    "primary":    RGBColor(0x00, 0x37, 0x64),  # Blue 900 — 제목 바, 표지
    "secondary":  RGBColor(0x00, 0x4A, 0x8F),  # Blue 800 — 보조 강조
    "accent":     RGBColor(0x00, 0x70, 0xE0),  # Blue 600 — 링크, 강조
    "text_dark":  RGBColor(0x1A, 0x1A, 0x1A),  # Gray 900 — 제목
    "text_body":  RGBColor(0x44, 0x44, 0x44),  # Gray 700 — 본문
    "text_light": RGBColor(0xFF, 0xFF, 0xFF),  # White — 반전 텍스트
    "text_caption": RGBColor(0x88, 0x88, 0x88), # Gray 500 — 캡션
    "bg_light":   RGBColor(0xF0, 0xF6, 0xFF),  # Blue 50 — 연한 배경
    "bg_card":    RGBColor(0xE6, 0xF0, 0xFF),  # Blue 100 — 카드 배경
    "border":     RGBColor(0xE5, 0xE5, 0xE5),  # Gray 200 — 구분선
    "success":    RGBColor(0x0D, 0x80, 0x50),  # Green — 증가
    "danger":     RGBColor(0xE8, 0x40, 0x2D),  # Red — 감소
    "warning":    RGBColor(0xE0, 0x7B, 0x54),  # Orange — 주의
    "info":       RGBColor(0x0D, 0x6E, 0x6E),  # Teal — 보조
}
```

### 폰트 매핑

```python
KRDS_FONTS = {
    "primary": "Pretendard",        # 1순위
    "fallback1": "S-Core Dream",    # 2순위
    "fallback2": "NanumSquare Neo", # 3순위
}

KRDS_TYPE_SCALE = {
    "cover_title": {"size": 40, "weight": "ExtraBold"},
    "slide_title": {"size": 26, "weight": "Bold"},
    "subtitle":    {"size": 20, "weight": "SemiBold"},
    "body":        {"size": 15, "weight": "Regular"},
    "caption":     {"size": 11, "weight": "Light"},
}
```

### 레이아웃 매핑 (Inches 기준, 10x7.5 슬라이드)

```python
KRDS_LAYOUT = {
    "slide_width": Inches(10),     # 16:9
    "slide_height": Inches(7.5),
    "title_bar_height": Inches(0.67),  # 48px @ 72dpi
    "footer_height": Inches(0.39),     # 28px
    "margin": Inches(0.44),            # 32px
    "content_gap": Inches(0.22),       # 16px
    "corner_radius": Inches(0.08),     # 6px
}
```
