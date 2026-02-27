# 회사 문서 관리 + 업로드 Undo 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 회사 문서 개별 삭제, 파일 목록 조회, 업로드 Undo, 단계 되돌리기를 구현한다.

**Architecture:** RAG Engine에 문서 단위 삭제/목록 메서드 → FastAPI에 list/delete 엔드포인트 → React 채팅 버블 파일카드 + 컨텍스트 패널 회사문서 탭.

**Tech Stack:** Python 3.13 (FastAPI, ChromaDB), TypeScript (React 19, Vite, Tailwind CSS)

---

## Task 1: RAG Engine — `delete_document()` + `list_documents()`

**Files:**
- Modify: `engine.py:420-456` (STEP 5: 유틸리티 섹션에 추가)

**Step 1: `delete_document` 구현**

`engine.py`의 `clear_collection()` 메서드 바로 위에 다음 두 메서드를 추가한다:

```python
def delete_document(self, source_file: str) -> int:
    """특정 source_file의 모든 청크를 삭제한다.

    Args:
        source_file: 삭제할 문서의 source_file 메타데이터 값

    Returns:
        삭제된 청크 수
    """
    results = self.collection.get(where={"source_file": source_file})
    ids = results.get("ids", [])
    if not ids:
        return 0
    self.collection.delete(ids=ids)
    self._bm25_dirty = True
    print(f"🗑️ 문서 삭제: {source_file} ({len(ids)}개 청크)")
    return len(ids)

def list_documents(self) -> list[dict[str, Any]]:
    """업로드된 문서 목록을 source_file별로 집계하여 반환한다.

    Returns:
        [{"source_file": "xxx.pdf", "chunks": 15}, ...]
    """
    all_data = self.collection.get(include=["metadatas"])
    doc_map: dict[str, int] = {}
    for meta in (all_data.get("metadatas") or []):
        sf = meta.get("source_file", "unknown")
        doc_map[sf] = doc_map.get(sf, 0) + 1
    return [{"source_file": k, "chunks": v} for k, v in sorted(doc_map.items())]
```

**Step 2: 검증**

```bash
python3 -c "
from engine import RAGEngine
rag = RAGEngine(collection_name='test_delete', persist_directory='/tmp/test_chroma')
rag.add_text_directly('hello world', source_name='doc1.pdf')
rag.add_text_directly('foo bar', source_name='doc2.pdf')
print('before:', rag.list_documents())
deleted = rag.delete_document('doc1.pdf')
print(f'deleted: {deleted}')
print('after:', rag.list_documents())
rag.clear_collection()
"
```

Expected: `before` 2개 문서, `deleted: 1`, `after` 1개 문서.

**Step 3: 커밋**

```bash
git add engine.py
git commit -m "feat(engine): add delete_document and list_documents methods"
```

---

## Task 2: FastAPI — `/api/company/list`, `/api/company/delete`, upload 응답 확장

**Files:**
- Modify: `services/web_app/main.py:1340-1380`

**Step 1: `CompanyDeletePayload` 모델 추가**

`SessionPayload` 근처에 추가:

```python
class CompanyDeletePayload(BaseModel):
    session_id: str
    source_file: str
```

**Step 2: `/api/company/list` 엔드포인트 추가**

`/api/company/clear` 바로 위에:

```python
@app.get("/api/company/list")
def list_company_documents(session_id: str) -> dict[str, Any]:
    session = _get_or_create_session(session_id)
    docs = session.rag_engine.list_documents()

    # 디스크 파일과 매칭하여 URL 생성
    upload_dir = ROOT_DIR / "data" / "web_uploads" / session.session_id / "company"
    for doc in docs:
        # source_file은 파싱된 파일명 — 디스크에서 매칭되는 파일 찾기
        matched_file = None
        if upload_dir.exists():
            for f in upload_dir.iterdir():
                if f.name.endswith(doc["source_file"]) or doc["source_file"] in f.name:
                    matched_file = f.name
                    break
        doc["url"] = f"/api/files/{session.session_id}/company/{matched_file}" if matched_file else ""

    return {
        "ok": True,
        "documents": docs,
        "total_chunks": sum(d["chunks"] for d in docs),
    }
```

**Step 3: `/api/company/delete` 엔드포인트 추가**

```python
@app.post("/api/company/delete")
def delete_company_document(payload: CompanyDeletePayload) -> dict[str, Any]:
    session = _get_or_create_session(payload.session_id)
    deleted = session.rag_engine.delete_document(payload.source_file)

    if deleted == 0:
        raise HTTPException(status_code=404, detail="해당 문서를 찾을 수 없습니다.")

    # 디스크에서도 삭제 (source_file 이름 포함하는 파일)
    upload_dir = ROOT_DIR / "data" / "web_uploads" / session.session_id / "company"
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            if f.name.endswith(payload.source_file) or payload.source_file in f.name:
                f.unlink(missing_ok=True)
                break

    # 매칭 결과 무효화
    session.latest_matching_result = None

    remaining = session.rag_engine.get_stats().get("total_documents", 0)
    return {
        "ok": True,
        "deleted_chunks": deleted,
        "remaining_chunks": remaining,
    }
```

**Step 4: `/api/company/upload` 응답에 `documents` 추가**

기존 `upload_company_documents` 함수의 return에 `documents` 필드 추가:

```python
    stats = session.rag_engine.get_stats()
    return {
        "ok": True,
        "uploaded_files": uploaded_names,
        "fileUrls": file_urls,
        "added_chunks": total_chunks,
        "company_chunks": stats.get("total_documents", 0),
        "documents": session.rag_engine.list_documents(),  # NEW
    }
```

**Step 5: 문법 확인**

```bash
python3 -m py_compile services/web_app/main.py && echo "OK"
```

**Step 6: 커밋**

```bash
git add services/web_app/main.py
git commit -m "feat(api): add company document list/delete endpoints"
```

---

## Task 3: 프론트엔드 API 클라이언트 + 타입

**Files:**
- Modify: `frontend/kirabot/types.ts:295-297`
- Modify: `frontend/kirabot/services/kiraApiService.ts:85-92`

**Step 1: 타입 추가** (`types.ts`)

`Conversation` 인터페이스의 `companyDocUrls` 타입 아래에:

```typescript
export interface CompanyDocument {
  source_file: string;
  chunks: number;
  url: string;
}
```

`Conversation` 인터페이스에 필드 추가:

```typescript
export interface Conversation {
  // ... 기존 필드 ...
  companyDocuments?: CompanyDocument[];  // NEW — 서버에서 받은 문서 목록
}
```

**Step 2: API 함수 추가** (`kiraApiService.ts`)

`clearCompanyDocuments` 함수 아래에:

```typescript
export async function listCompanyDocuments(sessionId: string): Promise<{ documents: CompanyDocument[]; total_chunks: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/list?session_id=${encodeURIComponent(sessionId)}`);
  return parseJson<{ documents: CompanyDocument[]; total_chunks: number }>(response);
}

export async function deleteCompanyDocument(sessionId: string, sourceFile: string): Promise<{ deleted_chunks: number; remaining_chunks: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, source_file: sourceFile }),
  });
  return parseJson<{ deleted_chunks: number; remaining_chunks: number }>(response);
}
```

`uploadCompanyDocuments` 반환 타입에 `documents` 추가:

```typescript
export async function uploadCompanyDocuments(
  sessionId: string,
  files: File[],
): Promise<{ company_chunks: number; added_chunks: number; fileUrls?: string[]; documents?: CompanyDocument[] }> {
```

(import에 `CompanyDocument` 추가 필요)

**Step 3: 빌드 확인**

```bash
cd frontend/kirabot && npx tsc --noEmit 2>&1 | head -20
```

**Step 4: 커밋**

```bash
git add frontend/kirabot/types.ts frontend/kirabot/services/kiraApiService.ts
git commit -m "feat(frontend): add company doc list/delete API client + types"
```

---

## Task 4: CompanyDocCard 컴포넌트

**Files:**
- Create: `frontend/kirabot/components/chat/messages/CompanyDocCard.tsx`

**Step 1: 컴포넌트 작성**

```tsx
import React, { useState, useEffect, useCallback } from 'react';
import { FileText, X, Undo2, Plus } from 'lucide-react';
import type { CompanyDocument } from '../../../types';

interface CompanyDocCardProps {
  documents: CompanyDocument[];
  onDelete: (sourceFile: string) => void;
  onAddMore?: () => void;
  /** 방금 업로드한 파일명들 (Undo 대상) */
  justUploaded?: string[];
  onUndo?: () => void;
}

const CompanyDocCard: React.FC<CompanyDocCardProps> = ({
  documents,
  onDelete,
  onAddMore,
  justUploaded,
  onUndo,
}) => {
  const [undoVisible, setUndoVisible] = useState(!!justUploaded?.length);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Undo 5초 타이머
  useEffect(() => {
    if (!justUploaded?.length) return;
    setUndoVisible(true);
    const timer = setTimeout(() => setUndoVisible(false), 5000);
    return () => clearTimeout(timer);
  }, [justUploaded]);

  const handleDelete = useCallback((sf: string) => {
    if (confirmDelete === sf) {
      onDelete(sf);
      setConfirmDelete(null);
    } else {
      setConfirmDelete(sf);
      setTimeout(() => setConfirmDelete(null), 3000);
    }
  }, [confirmDelete, onDelete]);

  if (!documents.length) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-2 max-w-sm">
      <p className="text-xs font-medium text-slate-500 mb-1">
        등록된 회사 문서 ({documents.length})
      </p>
      {documents.map((doc) => {
        const isJustUploaded = justUploaded?.includes(doc.source_file);
        return (
          <div
            key={doc.source_file}
            className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm transition-colors ${
              isJustUploaded ? 'bg-kira-50 border border-kira-200' : 'bg-slate-50'
            }`}
          >
            <FileText size={14} className="text-slate-400 flex-shrink-0" />
            <span className="flex-1 truncate text-slate-700">{doc.source_file}</span>
            <span className="text-xs text-slate-400 flex-shrink-0">{doc.chunks}</span>
            <button
              type="button"
              onClick={() => handleDelete(doc.source_file)}
              className={`p-0.5 rounded transition-colors ${
                confirmDelete === doc.source_file
                  ? 'text-red-600 bg-red-50'
                  : 'text-slate-300 hover:text-red-500'
              }`}
              title={confirmDelete === doc.source_file ? '다시 클릭하면 삭제' : '삭제'}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}

      <div className="flex items-center gap-2 pt-1">
        {undoVisible && onUndo && (
          <button
            type="button"
            onClick={() => { onUndo(); setUndoVisible(false); }}
            className="flex items-center gap-1 rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100 transition-colors"
          >
            <Undo2 size={12} /> 취소
          </button>
        )}
        {onAddMore && (
          <button
            type="button"
            onClick={onAddMore}
            className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <Plus size={12} /> 문서 추가
          </button>
        )}
      </div>
    </div>
  );
};

export default CompanyDocCard;
```

**Step 2: 빌드 확인**

```bash
cd frontend/kirabot && npx tsc --noEmit 2>&1 | head -10
```

**Step 3: 커밋**

```bash
git add frontend/kirabot/components/chat/messages/CompanyDocCard.tsx
git commit -m "feat(ui): add CompanyDocCard component with delete + undo"
```

---

## Task 5: useConversationFlow — 삭제/Undo/뒤로 핸들러

**Files:**
- Modify: `frontend/kirabot/hooks/useConversationFlow.ts`

**Step 1: import 추가**

파일 상단 imports에 `deleteCompanyDocument`, `listCompanyDocuments` 추가:

```typescript
import * as api from '../services/kiraApiService';
// api 모듈에 이미 포함됨 — 직접 import 불필요
```

**Step 2: 새 액션 타입 추가**

`UserAction` 타입에 추가 (기존 파일에서 `UserAction` 타입 위치 찾기):

```typescript
| { type: 'delete_company_doc'; sourceFile: string }
| { type: 'undo_company_upload'; sourceFiles: string[] }
| { type: 'go_back' }
```

**Step 3: 'files_uploaded' → company phase 핸들러에 `documents` 저장**

`case 'files_uploaded':` 내부에서 company upload 성공 후 `updateConv`에 `companyDocuments` 추가:

기존 코드 (line ~498):
```typescript
updateConv({ companyChunks: result.company_chunks, companyDocUrls: [...existingDocs, ...newCompanyDocs] });
```

변경:
```typescript
updateConv({
  companyChunks: result.company_chunks,
  companyDocUrls: [...existingDocs, ...newCompanyDocs],
  companyDocuments: result.documents || [],
  _justUploadedFiles: files.map(f => f.name),
});
```

**Step 4: `delete_company_doc` 액션 핸들러 추가**

`case 'header_add_company':` 뒤에:

```typescript
case 'delete_company_doc': {
  const { sourceFile } = action;
  const sid = conversation.sessionId;
  if (!sid) break;

  try {
    const result = await api.deleteCompanyDocument(sid, sourceFile);
    // 문서 목록 갱신
    const docs = conversation.companyDocuments?.filter(d => d.source_file !== sourceFile) || [];
    const urls = conversation.companyDocUrls?.filter(d => !d.name.includes(sourceFile)) || [];
    updateConv({
      companyChunks: result.remaining_chunks,
      companyDocuments: docs,
      companyDocUrls: urls,
    });
    pushText(`"${sourceFile}" 문서가 삭제되었습니다. (남은 청크: ${result.remaining_chunks})`);

    // 분석 결과 있으면 자동 rematch
    if (result.remaining_chunks > 0 && conversation.phase === 'doc_chat') {
      pushStatus('loading', '삭제 후 자격 요건을 재평가하고 있어요...');
      try {
        const rematchResult = await api.rematchWithCompanyDocs(sid);
        removeLastStatus();
        push({
          id: msgId(),
          role: 'bot',
          type: 'analysis_result',
          timestamp: Date.now(),
          analysis: rematchResult,
          opinionMode: conversation.opinionMode,
        } as AnalysisResultMessage);
      } catch {
        removeLastStatus();
      }
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '삭제 실패';
    pushStatus('error', msg);
  }
  break;
}

case 'undo_company_upload': {
  const { sourceFiles } = action;
  const sid = conversation.sessionId;
  if (!sid) break;

  for (const sf of sourceFiles) {
    try {
      await api.deleteCompanyDocument(sid, sf);
    } catch { /* 일부 실패 무시 */ }
  }
  // 목록 새로 가져오기
  try {
    const listResult = await api.listCompanyDocuments(sid);
    updateConv({
      companyChunks: listResult.total_chunks,
      companyDocuments: listResult.documents,
    });
    pushText('업로드가 취소되었습니다.');
  } catch { /* ignore */ }
  break;
}

case 'go_back': {
  const phase = conversation.phase;
  if (phase === 'doc_upload_target') {
    setPhase('doc_upload_company');
    pushText('회사 문서 업로드 단계로 돌아왔습니다.');
  } else if (phase === 'doc_upload_company') {
    setPhase('greeting');
  }
  break;
}
```

**Step 5: 빌드 확인**

```bash
cd frontend/kirabot && npx tsc --noEmit 2>&1 | head -20
```

**Step 6: 커밋**

```bash
git add frontend/kirabot/hooks/useConversationFlow.ts
git commit -m "feat(flow): add delete, undo, go_back action handlers"
```

---

## Task 6: 컨텍스트 패널 — 회사 문서 관리 탭

**Files:**
- Modify: `frontend/kirabot/components/ContextPanel.tsx` (또는 관련 패널 컴포넌트)

**Step 1: 회사 문서 섹션 추가**

ContextPanel 내부에 회사 문서가 있을 때 보여줄 섹션을 추가한다. 기존 `type: 'documents'` 케이스에서 회사 문서 탭을 렌더링:

```tsx
{companyDocuments.length > 0 && (
  <div className="border-t border-slate-200 pt-3 mt-3">
    <h3 className="text-xs font-semibold text-slate-500 mb-2 px-1">
      회사 문서 ({companyDocuments.length})
    </h3>
    <div className="space-y-1.5">
      {companyDocuments.map((doc) => (
        <div key={doc.source_file} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 group">
          <FileText size={14} className="text-slate-400" />
          <span className="flex-1 text-sm text-slate-700 truncate">{doc.source_file}</span>
          <span className="text-xs text-slate-400">{doc.chunks}</span>
          <button
            onClick={() => onAction?.({ type: 'delete_company_doc', sourceFile: doc.source_file })}
            className="opacity-0 group-hover:opacity-100 p-0.5 text-slate-300 hover:text-red-500 transition-all"
            title="삭제"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
    <div className="flex gap-2 mt-2 px-1">
      <button
        onClick={() => onAction?.({ type: 'header_add_company' })}
        className="text-xs text-kira-600 hover:text-kira-700 font-medium"
      >
        + 문서 추가
      </button>
    </div>
  </div>
)}
```

정확한 위치는 ContextPanel.tsx의 구조에 따라 결정. `companyDocuments`는 conversation에서 가져온다.

**Step 2: 빌드 확인 + 시각 확인**

```bash
cd frontend/kirabot && npm run build 2>&1 | tail -5
```

**Step 3: 커밋**

```bash
git add frontend/kirabot/components/
git commit -m "feat(ui): add company document management to context panel"
```

---

## 검증 체크리스트

모든 태스크 완료 후:

1. `npm run build` — 프론트엔드 빌드 성공
2. `python3 -m py_compile engine.py && python3 -m py_compile services/web_app/main.py` — 백엔드 문법 OK
3. `pytest tests/ -q` — 기존 테스트 138+ passed (기존 3 실패는 pre-existing)
4. 로컬 서버 시작 → 회사문서 2개 업로드 → 목록 확인 → 1개 삭제 → Undo 테스트
