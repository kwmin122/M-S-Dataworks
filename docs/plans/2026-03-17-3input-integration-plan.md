# 3입력 통합 생성기 — 구현 계획 v2

## 문제 정의

사용자가 채팅에서 올린 3개 입력(공고서/회사 역량 문서/과거 제안서)이
생성 버튼(WBS/PPT/제안서/실적기술서)에서 실제로 안 쓰이고 있음.

```
사용자 기대: 회사 문서 등록 → 생성 품질 향상
실제 동작:   회사 문서 → session RAG (채팅/매칭용만)
             생성 버튼 → CompanyDB (비어있음) → 제네릭 결과
```

## 코드 경로 확인 결과

### 현재 WBS 생성 체인

```
프론트엔드: generateExecutionPlan()
  → POST /api/proposal/generate-wbs {session_id, company_id, use_pack}
  → web_app/main.py:2916  generate_wbs_proxy()
    → session.latest_rfx_analysis (공고 ✅)
    → session.rag_engine (회사 문서 ❌ 안 읽음)
    → _proxy_to_rag("POST", "/api/generate-wbs", {rfx_result, company_id})
  → rag_engine/main.py:757
    ├─ use_pack=true  → document_orchestrator.generate_document() (line 784)
    │   └─ company_context = build_company_context() ← CompanyDB 기반
    └─ use_pack=false → wbs_orchestrator.generate_wbs() (line 862)
        └─ company_db=_get_company_db() ← CompanyDB 기반
```

### 핵심 API 시그니처

- `RAGEngine.search(query, top_k=5, filter_metadata=None) → list[SearchResult]`
- `SearchResult.text: str, .score: float, .source_file: str`
- collection 인자 없음, filter_metadata로 구분 가능

---

## 구현 체크리스트

### P0: 생성 진실화 로그

**파일:** `rag_engine/wbs_orchestrator.py`

- [ ] `generate_wbs()` 시작 시 logger.info로 입력 상태 기록:
  ```python
  logger.info(
      "wbs_generation_inputs: company_id=%s use_pack=%s "
      "profile_md=%d company_context=%d session_context=%d knowledge=%d",
      company_id, use_pack,
      len(profile_md), len(company_context),
      len(company_session_context), len(knowledge_texts),
  )
  ```
- [ ] WbsResult dataclass는 수정하지 않음 (응답 구조 유지)
- [ ] pack 경로: `rag_engine/main.py:784` 부근에도 동일 로그

**검증:** Railway 로그에서 `wbs_generation_inputs` 검색 가능

---

### P1: 세션 회사 문서 → 생성 브리지 (WBS만 먼저)

#### Step 1: web_app에서 세션 회사 청크 추출

**파일:** `services/web_app/main.py`

- [ ] 헬퍼 함수 추가:
  ```python
  def _extract_session_company_context(session, rfx_title: str = "", max_chars: int = 3000) -> str:
      """세션 RAG에서 회사 문서 관련 청크를 추출하여 텍스트로 반환."""
      if not session.rag_engine:
          return ""
      try:
          query = f"{rfx_title} 회사 역량 실적 인력 강점"
          results = session.rag_engine.search(query, top_k=6)
          # score cutoff: 너무 관련 없는 청크 제외
          relevant = [r for r in results if r.score >= 0.3]
          texts = [r.text for r in relevant if r.text]
          combined = "\n\n".join(texts)
          return combined[:max_chars]
      except Exception as exc:
          logger.debug("Session company context extraction skipped: %s", exc)
          return ""
  ```

- [ ] `generate_wbs_proxy()` (line 2916) 수정:
  ```python
  async def generate_wbs_proxy(payload):
      session = _get_or_create_session(payload.session_id)
      ...
      rfx_dict = _build_rfx_dict(session.latest_rfx_analysis)

      # NEW: 세션 회사 문서 청크 추출
      company_session_context = _extract_session_company_context(
          session, rfx_title=rfx_dict.get("title", ""),
      )

      return await _proxy_to_rag(
          "POST", "/api/generate-wbs",
          {
              "rfx_result": rfx_dict,
              "methodology": payload.methodology,
              "use_pack": payload.use_pack,
              "company_id": payload.company_id,
              "company_session_context": company_session_context,  # NEW
          },
          timeout=300,
      )
  ```

#### Step 2: rag_engine API에 파라미터 추가

**파일:** `rag_engine/main.py`

- [ ] `GenerateWbsRequest` (line 750)에 추가:
  ```python
  company_session_context: str = ""
  ```

- [ ] `use_pack=true` 경로 (line 771)에서 병합:
  ```python
  company_context = build_company_context(...)
  if req.company_session_context:
      company_context += "\n\n## 사용자가 등록한 회사 참고 문서:\n" + req.company_session_context
  ```

- [ ] `use_pack=false` 경로 (line 862)에서 전달:
  ```python
  result = await asyncio.to_thread(
      _generate_wbs,
      ...,
      company_session_context=req.company_session_context,  # NEW
  )
  ```

#### Step 3: wbs_orchestrator에서 병합

**파일:** `rag_engine/wbs_orchestrator.py`

- [ ] `generate_wbs()` 시그니처에 `company_session_context: str = ""` 추가
- [ ] company_context 빌드 후 병합:
  ```python
  if company_session_context:
      company_context += "\n\n## 사용자가 등록한 회사 참고 문서:\n" + company_session_context[:3000]
  ```

#### 검증

- [ ] 회사 문서 없이 WBS 생성 → 로그: `session_context=0`
- [ ] 회사 문서 등록 후 WBS 생성 → 로그: `session_context>0`
- [ ] 결과 DOCX에 회사 역량 반영 여부 확인
- [ ] rag_engine 전체 테스트 green

---

### P1 확장: 나머지 3개 생성기 (WBS 검증 후)

동일 패턴으로:

| 생성기 | web_app 프록시 | rag_engine 엔드포인트 |
|--------|---------------|---------------------|
| 제안서 | `generate_proposal_v2_proxy` | `/api/generate-proposal-v2` |
| PPT | `generate_ppt_proxy` | `/api/generate-ppt` |
| 실적기술서 | `generate_track_record_proxy` | `/api/generate-track-record` |

각각:
1. web_app: `_extract_session_company_context()` 호출
2. rag_engine 요청 모델: `company_session_context` 추가
3. orchestrator: company_context에 병합

---

### P1.5: UX 문구 진실화

**파일:** `frontend/kirabot/hooks/useConversationFlow.ts`

- [ ] 회사 문서 등록 안내 문구 수정 (P1 적용 후):
  ```
  현재: "회사 문서를 등록해주세요"
  변경: "분석에 참고할 회사 자료를 등록해주세요.
        (등록한 자료는 생성 기능에도 반영됩니다)"
  ```
- [ ] 생성 완료 시 세션 컨텍스트 사용 여부 표시:
  ```
  "회사 참고자료 반영됨 ✓" (company_session_context > 0일 때)
  ```

---

### P2: WBS 범용화

**선행 확인:** 사용자가 실제로 `use_pack=true`를 타는지 `false`를 타는지 P0 로그로 확인

**use_pack=false (legacy)인 경우:**

**파일:** `rag_engine/wbs_planner.py`

- [ ] 시스템 프롬프트 (line 152):
  "공공조달 IT 프로젝트" → "공공사업 수행계획"
- [ ] 방법론 감지 (line 156-168):
  - enum 유지하되, 프롬프트에서 "IT 개발" 프레임 제거
  - "이 사업의 성격에 맞는 방법론" 으로 변경
- [ ] 템플릿 (line 24-46):
  - 강제 적용 → "참고 예시" 격하
  - 프롬프트: "이 사업의 특성에 맞는 단계/태스크를 직접 설계하세요. 아래는 IT 사업의 참고 예시입니다."
- [ ] role (line 319):
  "PM/PL/개발자/QA/DBA" → "사업에 적합한 역할 (예: PM, 연구원, 분석관, 개발자 등)"

**use_pack=true인 경우:**
- pack/detect/domain_dict 경로 개선이 우선
- wbs_planner 재작성 불필요

---

### P3: HTML PPT PoC (별도 Phase)

P0~P2 완료 후 진행. 설계 문서: `docs/plans/2026-03-17-html-ppt-poc-design.md`

---

## 수정 파일 요약

| Phase | 파일 | 변경 |
|-------|------|------|
| P0 | `rag_engine/wbs_orchestrator.py` | logger.info 추가 |
| P0 | `rag_engine/main.py:784` | pack 경로 로그 추가 |
| P1 | `services/web_app/main.py` | `_extract_session_company_context()` + 4개 프록시 수정 |
| P1 | `rag_engine/main.py` | GenerateWbsRequest.company_session_context + 2경로 병합 |
| P1 | `rag_engine/wbs_orchestrator.py` | company_session_context 파라미터 + 병합 |
| P1.5 | `frontend/.../useConversationFlow.ts` | 문구 수정 |
| P2 | `rag_engine/wbs_planner.py` | IT 하드코딩 제거 + 범용화 |

## 완료 기준

1. **P0**: 로그에서 `wbs_generation_inputs` 확인 가능
2. **P1**: 회사 문서 등록 후 WBS → 결과에 회사 역량 반영 + `session_context>0`
3. **P1.5**: UI 문구가 정확한 기대치 설정
4. **P2**: "치유농업 연구용역" → IT가 아닌 연구 단계 생성
5. **전체**: rag_engine tests green, frontend tsc clean
