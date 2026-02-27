# PDF 뷰어 업그레이드 설계

## 목표

현재 연속 스크롤 + 확대 미동작 PDF 뷰어를 **한 페이지씩 보기 + 정상 줌 + 페이지 내비게이션**으로 업그레이드.

## 현재 문제

1. **모든 페이지 동시 렌더**: 50페이지 PDF → 50개 `<Page>` 컴포넌트 → 느림 + 메모리 낭비
2. **확대 미동작**: `pageWidth = containerWidth * zoom` → 가로 오버플로만 발생, 실질적 확대 안됨
3. **페이지 내비게이션 없음**: 현재 페이지 번호 표시 없음, 이전/다음 버튼 없음
4. **페이지 직접 이동 불가**: 참조 클릭 외에 특정 페이지로 갈 방법 없음

## 설계

### 단일 페이지 렌더링

- `<Page pageNumber={currentPage} />` 1개만 렌더 (현재: numPages개 전부)
- `currentPage` state로 현재 보는 페이지 관리
- 참조(reference) 클릭 시 `page` prop → `setCurrentPage(page)` 자동이동

### 확대/축소

- `transform: scale(zoom)` + `transformOrigin: 'top center'`
- 외부: `overflow-auto` 스크롤 컨테이너 → 확대 시 자연스러운 스크롤
- `width`는 항상 컨테이너 너비에 맞춤 (fit-to-width)
- ZOOM_STEPS: [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

### 툴바

```
[← 이전] [ 3 / 15 ] [다음 →]   |   [−] [100%] [+]   |   [⬇ 다운로드]
```

- 페이지 번호 클릭 → input 전환 → Enter로 해당 페이지 점프
- 첫/마지막 페이지에서 이전/다음 비활성화

### 키보드 단축키

| 키 | 동작 |
|----|------|
| ← / ↑ | 이전 페이지 |
| → / ↓ | 다음 페이지 |
| + / = | 확대 |
| - | 축소 |
| 0 | 줌 리셋 |
| Home | 첫 페이지 |
| End | 마지막 페이지 |

### 유지 기능

- **자동 페이지 이동**: `page` prop 변경 시 해당 페이지로 이동
- **노란 형광펜**: `currentPage === page`일 때 `customTextRenderer`로 키워드 하이라이트
- **참조 텍스트 카드**: 상단 amber 카드
- **HWP/DOCX 텍스트 뷰어**: 변경 없음
- **기타 포맷 다운로드 카드**: 변경 없음

### 변경 파일

| 파일 | 변경 |
|------|------|
| `frontend/kirabot/components/chat/context/DocumentViewer.tsx` | PdfViewer 전면 리팩토링 |

단일 파일 변경. 외부 API/타입 변경 없음.
