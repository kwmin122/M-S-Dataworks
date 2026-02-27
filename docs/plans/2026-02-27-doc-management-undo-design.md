# 회사 문서 관리 + 업로드 Undo 설계

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 회사 문서 개별 삭제, 파일 목록 조회, 업로드 직후 Undo, 단계 되돌리기 구현.

**Architecture:** RAG Engine에 문서 단위 삭제 메서드 추가 → 백엔드 API 3개 신설 → 프론트엔드 채팅 버블 + 컨텍스트 패널 UI 구현.

**Tech Stack:** Python (FastAPI, ChromaDB), TypeScript (React 19, Tailwind CSS)

---

## 현재 상태

| 기능 | 현재 | 목표 |
|------|------|------|
| 회사 문서 업로드 | 추가만 가능 | 추가 + 개별 삭제 |
| 파일 목록 조회 | 불가 (청크 수만) | 파일명 + 청크수 + 업로드시간 |
| 개별 파일 삭제 | 불가 (전체 삭제만) | 파일 지정 삭제 |
| 업로드 Undo | 없음 | 업로드 직후 5초간 취소 버튼 |
| 단계 되돌리기 | 없음 | 문서 업로드 단계에서 뒤로 가기 |

---

## 1. 백엔드: RAG Engine 문서 삭제

### `engine.py` — `delete_document(source_file)` 추가

```python
def delete_document(self, source_file: str) -> int:
    """특정 source_file의 모든 청크를 삭제한다."""
    results = self.collection.get(where={"source_file": source_file})
    if not results["ids"]:
        return 0
    self.collection.delete(ids=results["ids"])
    self._bm25_dirty = True
    return len(results["ids"])
```

### `engine.py` — `list_documents()` 추가

```python
def list_documents(self) -> list[dict]:
    """업로드된 문서 목록 (source_file별 청크 수)."""
    all_meta = self.collection.get(include=["metadatas"])
    doc_map: dict[str, int] = {}
    for meta in all_meta["metadatas"]:
        sf = meta.get("source_file", "unknown")
        doc_map[sf] = doc_map.get(sf, 0) + 1
    return [{"source_file": k, "chunks": v} for k, v in doc_map.items()]
```

---

## 2. 백엔드: API 엔드포인트

### `GET /api/company/list?session_id=xxx`

```json
{
  "ok": true,
  "documents": [
    {"source_file": "회사소개서.pdf", "chunks": 15, "url": "/api/files/.../회사소개서.pdf"},
    {"source_file": "실적증명서.pdf", "chunks": 8, "url": "/api/files/.../실적증명서.pdf"}
  ],
  "total_chunks": 23
}
```

### `POST /api/company/delete`

```json
// Request
{"session_id": "xxx", "source_file": "회사소개서.pdf"}

// Response
{"ok": true, "deleted_chunks": 15, "remaining_chunks": 8}
```

삭제 후 `session.latest_matching_result`를 `None`으로 초기화 (매칭 무효화).

### 기존 `/api/company/upload` 응답 확장

```json
{
  "ok": true,
  "uploaded_files": ["신규문서.pdf"],
  "fileUrls": ["/api/files/.../신규문서.pdf"],
  "added_chunks": 12,
  "company_chunks": 35,
  "documents": [...]  // 전체 문서 목록 추가
}
```

---

## 3. 프론트엔드: 채팅 버블 내 파일 카드

회사문서 업로드 성공 메시지에 파일 카드 목록 표시:

```
┌─────────────────────────────────┐
│ 📄 회사소개서.pdf    15 청크  ✕ │
│ 📄 실적증명서.pdf     8 청크  ✕ │
│                                 │
│ [+ 문서 추가]                   │
└─────────────────────────────────┘
```

- ✕ 클릭 → "삭제하시겠습니까?" 확인 → `/api/company/delete` 호출
- 삭제 후 분석 결과 있으면 자동 rematch
- 업로드 직후에는 "취소" 버튼 5초간 표시 (Undo)

### Undo 동작

1. 업로드 API 응답 수신
2. 버블에 "취소" 버튼 5초간 표시 (카운트다운)
3. 취소 클릭 → 방금 업로드한 파일들만 `/api/company/delete` 호출
4. 5초 경과 → 버튼 사라짐
5. 분석이 이미 시작된 경우 Undo 불가 (버튼 미표시)

---

## 4. 프론트엔드: 컨텍스트 패널 "회사 문서" 탭

기존 컨텍스트 패널 탭(분석문서/회사문서)에 문서 관리 UI 추가:

```
┌── 회사 문서 (2) ─────────────────┐
│                                   │
│ 📄 회사소개서.pdf                 │
│    15 청크 · 2026-02-27          │
│    [미리보기]  [삭제]             │
│                                   │
│ 📄 실적증명서.pdf                 │
│    8 청크 · 2026-02-27           │
│    [미리보기]  [삭제]             │
│                                   │
│ ─────────────────────────────── │
│ [+ 문서 추가]  [전체 삭제]        │
└───────────────────────────────────┘
```

- 미리보기: 기존 DocumentViewer 재사용 (PDF iframe)
- 삭제: 확인 대화상자 후 API 호출
- 전체 삭제: 기존 `/api/company/clear` 호출

---

## 5. 단계 되돌리기 (Back 버튼)

문서 업로드 단계에서 "뒤로" 버튼 추가:

- `doc_upload_company` → 이전 단계로 (greeting 또는 bid_search_results)
- `doc_upload_target` → `doc_upload_company` 또는 이전 단계로
- `doc_analyzing` / `bid_analyzing` → 되돌리기 불가 (LLM 비용 발생 중)

구현: `ChatInput` 영역에 "← 뒤로" 링크 표시 (upload 단계에서만).

---

## 6. 데이터 흐름

```
[사용자: 파일 삭제 클릭]
    ↓
[확인 대화상자]
    ↓ 확인
[POST /api/company/delete {session_id, source_file}]
    ↓
[engine.delete_document(source_file)]
    ↓ ChromaDB: collection.delete(where={source_file})
    ↓ Disk: rm file from /data/web_uploads/{sid}/company/
    ↓ session.latest_matching_result = None
    ↓
[Response: {ok, deleted_chunks, remaining_chunks}]
    ↓
[프론트: 파일 목록 업데이트]
    ↓ 분석 결과 있으면?
[POST /api/rematch] → GO/NO-GO 재평가
```

---

## 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `engine.py` | `delete_document()`, `list_documents()` 추가 |
| `services/web_app/main.py` | `/api/company/list`, `/api/company/delete` 엔드포인트 + upload 응답 확장 |
| `frontend/kirabot/types.ts` | `CompanyDocument` 타입, 메시지 타입 확장 |
| `frontend/kirabot/services/kiraApiService.ts` | `listCompanyDocs()`, `deleteCompanyDoc()` API 클라이언트 |
| `frontend/kirabot/hooks/useConversationFlow.ts` | 업로드 후 파일목록 저장, 삭제 액션 핸들러, Undo 타이머, 뒤로가기 |
| `frontend/kirabot/components/chat/messages/CompanyDocCard.tsx` | 파일 카드 컴포넌트 (삭제 버튼 + Undo) |
| `frontend/kirabot/components/ContextPanel.tsx` | 회사 문서 탭 UI |
| `frontend/kirabot/components/chat/ChatInput.tsx` | 뒤로 버튼 (upload 단계) |

---

## 검증

1. 회사 문서 2개 업로드 → 목록에 2개 표시
2. 1개 삭제 → 남은 1개만 표시, 청크 수 감소
3. 분석 후 삭제 → 자동 rematch 실행
4. 업로드 직후 Undo → 방금 올린 파일만 삭제
5. 5초 후 Undo 버튼 사라짐
6. 뒤로 버튼으로 단계 이동 확인
7. 전체 삭제 → 0개, 매칭 결과 초기화
