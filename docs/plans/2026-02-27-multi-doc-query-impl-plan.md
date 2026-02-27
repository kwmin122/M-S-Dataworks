# 다중 문서 질의 + @멘션 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** @멘션 자동완성으로 특정 문서 지정 질문, 서수 자동감지, 문서 간 비교 기능 구현.

**Architecture:** 프론트 @멘션 UI → 백엔드 `source_files` 필터 → ChromaDB `where` 필터 → LLM 라벨링 컨텍스트.

**Tech Stack:** Python 3.13 (FastAPI, ChromaDB), TypeScript (React 19, Vite, Tailwind CSS)

---

## Task 1: 백엔드 — ChatPayload에 `source_files` + `_resolve_doc_scope()` + 필터링

**Files:**
- Modify: `services/web_app/main.py`

### Step 1: `ChatPayload` 확장

기존 `ChatPayload` 모델에 `source_files` 필드 추가:

```python
class ChatPayload(BaseModel):
    session_id: str
    message: str
    source_files: list[str] | None = None  # NEW: 특정 문서 필터
```

### Step 2: `_resolve_doc_scope()` 함수 추가

`_build_chat_context()` 위에 추가:

```python
import re as _re

_ORDINAL_MAP: list[tuple[_re.Pattern, int]] = [
    (_re.compile(r"(?:첫\s*번째|첫째|1\s*번째|첫|제\s*1)"), 0),
    (_re.compile(r"(?:두\s*번째|둘째|2\s*번째|제\s*2)"), 1),
    (_re.compile(r"(?:세\s*번째|셋째|3\s*번째|제\s*3)"), 2),
    (_re.compile(r"(?:네\s*번째|넷째|4\s*번째|제\s*4)"), 3),
    (_re.compile(r"(?:다섯\s*번째|5\s*번째|제\s*5)"), 4),
]
_LAST_PAT = _re.compile(r"(?:마지막|최근|맨\s*끝)")
_COMPARE_PAT = _re.compile(r"(?:비교|가장|중에서|어떤\s*문서|어느\s*문서|모든\s*문서|전체\s*문서|n개)")
_DOC_CONTEXT_PAT = _re.compile(r"(?:문서|파일|자료|서류)")


def _resolve_doc_scope(
    message: str,
    explicit_files: list[str] | None,
    company_docs: list[str],
    rfx_docs: list[str],
) -> tuple[list[str] | None, bool]:
    """메시지에서 문서 범위를 결정한다.

    Returns:
        (source_files, is_compare)
        - source_files: 필터할 문서명 리스트 (None이면 전체)
        - is_compare: 비교 모드 여부
    """
    # 1. 프론트엔드 명시 지정 → 최우선
    if explicit_files:
        if "*" in explicit_files:
            return None, True  # 전체 비교
        return explicit_files, len(explicit_files) > 1

    all_docs = company_docs + rfx_docs
    if not all_docs:
        return None, False

    # 2. 비교 키워드 감지
    if _COMPARE_PAT.search(message) and _DOC_CONTEXT_PAT.search(message):
        return None, True

    # 3. 서수 감지
    for pat, idx in _ORDINAL_MAP:
        if pat.search(message) and _DOC_CONTEXT_PAT.search(message):
            if idx < len(all_docs):
                return [all_docs[idx]], False

    # 4. 마지막 문서
    if _LAST_PAT.search(message) and _DOC_CONTEXT_PAT.search(message):
        return [all_docs[-1]], False

    # 5. 파일명 직접 언급
    for doc in all_docs:
        name_no_ext = doc.rsplit(".", 1)[0] if "." in doc else doc
        if name_no_ext in message or doc in message:
            return [doc], False

    return None, False
```

### Step 3: `_build_chat_context()` 수정

기존 함수에 `source_files` 파라미터 추가:

```python
def _build_chat_context(
    session: WebRuntimeSession,
    message: str,
    source_files: list[str] | None = None,
    is_compare: bool = False,
) -> tuple[str, str, list[dict]]:
```

검색 시 `filter_metadata` 적용:

```python
    # 비교 모드: 문서별 개별 검색
    if is_compare:
        all_docs = session.rag_engine.list_documents()
        for doc_info in all_docs:
            sf = doc_info["source_file"]
            results = session.rag_engine.search(message, top_k=6,
                filter_metadata={"source_file": sf})
            company_context_text += f"\n=== 문서: {sf} ===\n"
            for r in results:
                page_num = _extract_page_number(r)
                company_context_text += f"[{sf}, 페이지 {page_num}]\n{r.text}\n---\n"
    elif source_files:
        # 특정 문서만 검색
        for sf in source_files:
            results = session.rag_engine.search(message, top_k=12,
                filter_metadata={"source_file": sf})
            for r in results:
                page_num = _extract_page_number(r)
                company_context_text += f"[{sf}, 페이지 {page_num}]\n{r.text}\n---\n"
    else:
        # 기존: 전체 검색
        for result in session.rag_engine.search(message, top_k=12):
            # ... 기존 코드 유지

    # rfx_rag_engine도 동일 패턴 적용 (source_files 필터)
```

### Step 4: `chat_with_references` 엔드포인트 수정

```python
    # 문서 범위 결정
    company_docs = [d["source_file"] for d in session.rag_engine.list_documents()]
    rfx_docs = [d["source_file"] for d in session.rfx_rag_engine.list_documents()]
    scope_files, is_compare = _resolve_doc_scope(
        message, payload.source_files, company_docs, rfx_docs
    )

    company_context_text, rfx_context_text, fallback_refs = _build_chat_context(
        session, message, source_files=scope_files, is_compare=is_compare,
    )
```

응답에 `scoped_to` 추가:

```python
    response = {
        # ... 기존 필드 ...
        "scoped_to": scope_files,  # NEW
    }
```

### Step 5: 시스템 프롬프트에 문서 목록 추가

`_generate_chat_answer_with_tools()` 내 시스템 프롬프트에:

```python
    doc_list_str = ""
    if company_docs or rfx_docs:
        doc_list_str = "\n\n사용 가능한 문서:\n"
        for i, d in enumerate(company_docs, 1):
            doc_list_str += f"  {i}. [회사] {d}\n"
        for i, d in enumerate(rfx_docs, len(company_docs) + 1):
            doc_list_str += f"  {i}. [공고] {d}\n"
```

### Step 6: 검증

```bash
python3 -m py_compile services/web_app/main.py && echo "OK"
pytest -q 2>&1 | tail -5
```

### Step 7: 커밋

```bash
git add services/web_app/main.py
git commit -m "feat(api): add source_files filter + ordinal detection for multi-doc queries"
```

---

## Task 2: 프론트엔드 타입 + API 확장

**Files:**
- Modify: `frontend/kirabot/types.ts`
- Modify: `frontend/kirabot/services/kiraApiService.ts`

### Step 1: 타입 추가 (`types.ts`)

```typescript
export interface DocMention {
  sourceFile: string;
  label: string;  // 표시용 (파일명 또는 "전체 비교")
  type: 'company' | 'rfx';
}
```

기존 `Conversation` 인터페이스에:
```typescript
  activeDocFilter?: string[] | null;  // @멘션으로 선택된 문서
```

### Step 2: API 함수 수정 (`kiraApiService.ts`)

`chatWithReferences` 함수에 `sourceFiles` 추가:

```typescript
export async function chatWithReferences(
  sessionId: string,
  message: string,
  sourceFiles?: string[],
): Promise<ChatResponse & { scoped_to?: string[] }> {
  const body: Record<string, unknown> = { session_id: sessionId, message };
  if (sourceFiles?.length) body.source_files = sourceFiles;
  // ...
}
```

### Step 3: 빌드 확인

```bash
cd frontend/kirabot && npx tsc --noEmit 2>&1 | head -10
```

### Step 4: 커밋

```bash
git add frontend/kirabot/types.ts frontend/kirabot/services/kiraApiService.ts
git commit -m "feat(frontend): add source_files types and API parameter"
```

---

## Task 3: ChatInput @멘션 자동완성 UI

**Files:**
- Modify: `frontend/kirabot/components/chat/ChatInput.tsx`

### Step 1: @멘션 상태 관리

```typescript
const [mentionOpen, setMentionOpen] = useState(false);
const [mentionQuery, setMentionQuery] = useState('');
const [mentionIndex, setMentionIndex] = useState(0);
const [docTags, setDocTags] = useState<DocMention[]>([]);
```

### Step 2: 입력 변경 핸들러

`onChange`에서 `@` 감지:

```typescript
const handleInputChange = (value: string) => {
  setText(value);
  // @ 감지: 마지막 @부터 현재 커서까지
  const lastAt = value.lastIndexOf('@');
  if (lastAt >= 0) {
    const query = value.slice(lastAt + 1);
    // 공백이 없으면 멘션 중
    if (!query.includes(' ') && !query.includes('\n')) {
      setMentionOpen(true);
      setMentionQuery(query);
      setMentionIndex(0);
      return;
    }
  }
  setMentionOpen(false);
};
```

### Step 3: 문서 목록 필터링

```typescript
const allDocs: DocMention[] = [
  ...(conversation?.companyDocuments || []).map(d => ({
    sourceFile: d.source_file,
    label: d.source_file,
    type: 'company' as const,
  })),
  // rfx 문서도 추가 (conversation.uploadedFileName 등)
];

const filteredDocs = mentionQuery
  ? allDocs.filter(d => d.label.toLowerCase().includes(mentionQuery.toLowerCase()))
  : allDocs;

// "전체 문서 비교" 옵션 추가
const mentionOptions = [
  ...filteredDocs,
  { sourceFile: '*', label: '전체 문서 비교', type: 'company' as const },
];
```

### Step 4: 드롭다운 UI

```tsx
{mentionOpen && mentionOptions.length > 0 && (
  <div className="absolute bottom-full left-0 right-0 mb-1 rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden z-50 max-h-48 overflow-y-auto">
    <div className="px-3 py-1.5 text-xs font-medium text-slate-400 border-b border-slate-100">
      문서 선택
    </div>
    {mentionOptions.map((doc, i) => (
      <button
        key={doc.sourceFile}
        type="button"
        onClick={() => handleMentionSelect(doc)}
        className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors ${
          i === mentionIndex ? 'bg-kira-50 text-kira-700' : 'text-slate-700 hover:bg-slate-50'
        }`}
      >
        <span className="text-xs">{doc.type === 'company' ? '🏢' : '📋'}</span>
        <span className="flex-1 truncate">{doc.label}</span>
        {doc.sourceFile === '*' && <span className="text-xs">🔄</span>}
      </button>
    ))}
  </div>
)}
```

### Step 5: 선택 핸들러

```typescript
const handleMentionSelect = (doc: DocMention) => {
  // @쿼리 부분을 태그로 교체
  const lastAt = text.lastIndexOf('@');
  const before = text.slice(0, lastAt);
  setDocTags(prev => [...prev, doc]);
  setText(before);  // @ 이전 텍스트만 남김
  setMentionOpen(false);
  inputRef.current?.focus();
};
```

### Step 6: 태그 칩 렌더링

입력창 위에:

```tsx
{docTags.length > 0 && (
  <div className="flex flex-wrap gap-1 px-3 pt-2">
    {docTags.map((tag, i) => (
      <span key={i} className="inline-flex items-center gap-1 rounded-full bg-kira-100 text-kira-700 px-2.5 py-0.5 text-xs font-medium">
        @{tag.label}
        <button type="button" onClick={() => setDocTags(prev => prev.filter((_, j) => j !== i))}
          className="text-kira-400 hover:text-kira-600">
          <X size={12} />
        </button>
      </span>
    ))}
  </div>
)}
```

### Step 7: 키보드 네비게이션

`onKeyDown`에서:

```typescript
if (mentionOpen) {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    setMentionIndex(prev => Math.min(prev + 1, mentionOptions.length - 1));
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    setMentionIndex(prev => Math.max(prev - 1, 0));
  } else if (e.key === 'Enter') {
    e.preventDefault();
    handleMentionSelect(mentionOptions[mentionIndex]);
  } else if (e.key === 'Escape') {
    setMentionOpen(false);
  }
  return;
}
```

### Step 8: 전송 시 태그 반영

```typescript
const handleSubmit = () => {
  const sourceFiles = docTags.map(t => t.sourceFile);
  onAction({
    type: 'text_submitted',
    text,
    sourceFiles: sourceFiles.length > 0 ? sourceFiles : undefined,
  });
  setText('');
  setDocTags([]);
};
```

### Step 9: 빌드 확인

```bash
cd frontend/kirabot && npx tsc --noEmit && npm run build 2>&1 | tail -5
```

### Step 10: 커밋

```bash
git add frontend/kirabot/components/chat/ChatInput.tsx
git commit -m "feat(ui): add @mention autocomplete for document targeting"
```

---

## Task 4: useConversationFlow — sourceFiles 전달

**Files:**
- Modify: `frontend/kirabot/hooks/useConversationFlow.ts`

### Step 1: 채팅 전송 시 sourceFiles 전달

`handleUserText` 함수에서 `chatWithReferences` 호출 시 `sourceFiles` 전달:

```typescript
const handleUserText = async (text: string, sourceFiles?: string[]) => {
  // ... 기존 코드 ...
  const response = await api.chatWithReferences(sid, text, sourceFiles);
  // 응답에 scoped_to가 있으면 메시지에 포함
};
```

### Step 2: `ask_about_doc` 액션 추가

```typescript
case 'ask_about_doc': {
  // CompanyDocCard에서 "질문하기" 클릭 시
  // ChatInput에 @태그 자동 삽입 — dispatch를 통해
  updateConv({ activeDocFilter: [action.sourceFile] });
  break;
}
```

### Step 3: 커밋

```bash
git add frontend/kirabot/hooks/useConversationFlow.ts
git commit -m "feat(flow): pass sourceFiles through chat pipeline"
```

---

## Task 5: CompanyDocCard — "질문하기" 버튼 + MessageBubble 배지

**Files:**
- Modify: `frontend/kirabot/components/chat/messages/CompanyDocCard.tsx`
- Modify: `frontend/kirabot/components/chat/messages/MessageBubble.tsx`

### Step 1: CompanyDocCard에 💬 버튼

각 문서 행에 `MessageCircle` 아이콘 버튼 추가:

```tsx
import { FileText, X, Undo2, Plus, MessageCircle } from 'lucide-react';

// 기존 삭제 버튼 앞에:
<button
  type="button"
  onClick={() => onAskAbout?.(doc.source_file)}
  className="p-0.5 rounded text-slate-300 hover:text-kira-500 transition-colors"
  title="이 문서에 질문"
>
  <MessageCircle size={14} />
</button>
```

Props에 추가:
```typescript
onAskAbout?: (sourceFile: string) => void;
```

### Step 2: MessageBubble에 `scoped_to` 배지

봇 응답 메시지에 `scoped_to`가 있을 때:

```tsx
{message.scoped_to?.length > 0 && (
  <div className="flex items-center gap-1 mt-1 text-xs text-slate-400">
    <FileText size={10} />
    기반 문서: {message.scoped_to.join(', ')}
  </div>
)}
```

### Step 3: 커밋

```bash
git add frontend/kirabot/components/chat/messages/CompanyDocCard.tsx frontend/kirabot/components/chat/messages/MessageBubble.tsx
git commit -m "feat(ui): add ask-about-doc button + scoped_to badge"
```

---

## 검증 체크리스트

1. `@` 타이핑 → 문서 드롭다운 표시, 필터링 동작
2. 문서 선택 → 태그 칩 표시, ✕로 제거 가능
3. 태그 있는 상태에서 전송 → 해당 문서만 검색 확인
4. "첫번째 문서에서 요구사항" → 서수 감지 → 해당 문서만 검색
5. "전체 문서 비교" → 비교 모드 → 문서별 라벨링 답변
6. CompanyDocCard 💬 클릭 → ChatInput에 태그 자동 삽입
7. 봇 응답에 "기반 문서: xxx.pdf" 배지 표시
8. 태그 없이 일반 질문 → 기존과 동일하게 전체 검색
9. `npm run build` 성공
10. `pytest -q` 기존 테스트 통과
