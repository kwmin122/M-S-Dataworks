# Company Document Pack — 회사별 문서 운영체제 설계

> 날짜: 2026-03-11
> 상태: Approved (아키텍처 + 정량 기준 + 데이터 모델 + PDF 정책 확정)
> 작성: Claude Opus 4.6 + 대표이사 리뷰 4회
> 열린 결정: HWPX SDK 의존 방식

---

## 1. Goals / Non-goals

### Goals

1. **수행계획서 품질을 "표 모음집"에서 "전문 컨설턴트급 산문"으로 끌어올린다.**
   현재 `wbs_generator.py:435`는 산문 1문장 + 표 3개. 목표는 도메인별 고유 구조(연구 9장, IT 10장 등)의 풍부한 서술 문서.

2. **회사별 문서 취향을 제품 자산(Company Pack)으로 축적한다.**
   사용자가 수정할수록 다음 생성이 더 좋아지는 선순환 구조.

3. **모든 도메인(IT/연구/컨설팅/교육)을 범용으로 지원한다.**
   현재 IT 시스템 개발 편향(`wbs_planner.py:24` 워터폴 템플릿)을 제거.

4. **Content First, Render Last — LLM은 내용만, 템플릿 엔진이 양식을 입힌다.**
   현재 `document_assembler.py:30` 공용 스타일 렌더러의 한계를 넘는다.

5. **DOCX/HWPX 양식을 지원된 토큰/템플릿 범위 내에서 높은 충실도로 재현한다.**
   "그대로"가 아닌 high-fidelity reproduction. Pack의 semantic_tokens + renderer mapping이 지원하는 범위 내에서 최대한 원본에 가깝게.

### Non-goals

- 회사별 LLM 파인튜닝 (Phase 5 이후, 데이터 충분 시 검토)
- 실시간 협업 편집 (Google Docs 류)
- PDF 출력 최적화 (DOCX/HWPX → PDF 변환은 사용자 측)
- 프론트엔드 WYSIWYG 편집기 (별도 설계)

---

## 2. Core Concepts

### Company Document Pack

사용자에게는 **"회사 문서 스킬"**, 내부에는 **Versioned Company Document Pack**.

Pack은 회사가 선호하는 문서 구조, 스타일, 어투, 고정 문구, 예시, 렌더링 템플릿을 구조화해 저장한 자산. 생성할 때마다 이 Pack을 참조하여 "그 회사다운" 문서를 만든다.

### Pack 계층

```
_default (기본 Guide Pack)
    ↑ 상속
{company_id} (회사 Pack) — 오버레이 방식으로 기본을 덮어씀
```

회사 Pack이 정의한 필드만 오버라이드. 정의 안 한 필드는 기본 Pack에서 상속.

**상속 병합 알고리즘 (Section ID UPSERT)**:
- `pack.json`, `brand_pack.json`, `semantic_tokens.json`: 필드 단위 shallow merge (회사 필드 우선)
- `sections.json`: **섹션 ID 기반 UPSERT**. 회사 Pack의 각 섹션은 `id`로 매칭하여 기본 Pack의 동일 ID 섹션을 필드 단위 오버라이드. 기본 Pack에 없는 새 `id`는 섹션 추가. 회사 Pack에서 `"disabled": true`를 명시하면 해당 섹션 제거.
- `boilerplate.json`, `exemplars.json`: 회사 Pack 항목을 기본 Pack 위에 concat (중복 id는 회사 우선)
- `domain_dict.json`: 필드 단위 shallow merge (roles/phases/methodologies 배열은 회사 것으로 교체, 둘 다 있을 때)
- `templates/`: 회사 Pack에 파일이 있으면 해당 파일만 오버라이드. 없으면 기본 Pack 파일 사용.

**종결 조건**: `_default` Pack의 `base_pack_ref`는 반드시 `null`. Pack Resolver가 `base_pack_ref === null`을 만나면 병합 체인 종료. `④ _default/{doc_type}/general` fallback에서도 파일이 없으면 `PackNotFoundError` raise.

### Pack 단위

```
{company_id} / {doc_type} / {domain_type}
```

같은 회사라도 연구용역 수행계획서와 IT구축 수행계획서의 스타일이 다를 수 있으므로 도메인까지 분리.

- `doc_type`: execution_plan | proposal | ppt | track_record
- `domain_type`: it_build | research | consulting | education_oda | general

### Content First, Render Last

```
LLM (Section Writer)  →  markdown 콘텐츠  →  Canonical IR  →  Template Renderer  →  DOCX/HWPX
          ↑                                        ↑                    ↑
     Pack 규칙/예시                          canonical_layout      docx_mapping
     Layer 1 지식                                                 hwpx_mapping
     RFP 컨텍스트                                                 base.docx
```

LLM은 절대 최종 파일을 직접 만들지 않는다. 마크다운 산문만 생성하고, 표/차트는 데이터로 전달하며, Template Renderer가 회사 양식에 맞춰 최종 조립한다.

### Semantic Style Tokens

렌더러 독립적인 스타일 토큰 체계. Pack은 semantic token만 정의하고, 각 렌더러(DOCX/HWPX)가 자신의 매핑으로 변환.

```
semantic_tokens.json (렌더러 독립)
    ↓
docx_mapping.json  ─→  python-docx/docxtpl
hwpx_mapping.json  ─→  Hancom SDK
```

---

## 3. Data Model

### 디렉토리 구조

```
data/company_packs/
├── _default/
│   ├── pack.json
│   ├── brand_pack.json
│   ├── semantic_tokens.json
│   ├── execution_plan/
│   │   ├── it_build/
│   │   │   ├── sections.json
│   │   │   ├── boilerplate.json
│   │   │   ├── exemplars.json
│   │   │   ├── domain_dict.json
│   │   │   └── templates/
│   │   │       ├── render_spec.json
│   │   │       ├── canonical_layout.json
│   │   │       ├── docx_mapping.json
│   │   │       ├── hwpx_mapping.json
│   │   │       └── base.docx
│   │   ├── research/
│   │   ├── consulting/
│   │   ├── education_oda/
│   │   └── general/
│   ├── proposal/
│   │   └── (동일 하위 구조)
│   └── ppt/
│
├── {company_id}/
│   ├── pack.json
│   ├── brand_pack.json
│   ├── semantic_tokens.json
│   ├── execution_plan/
│   │   ├── {domain_type}/
│   │   │   ├── sections.json
│   │   │   ├── boilerplate.json
│   │   │   ├── exemplars.json
│   │   │   ├── domain_dict.json
│   │   │   ├── templates/
│   │   │   │   ├── render_spec.json
│   │   │   │   ├── canonical_layout.json
│   │   │   │   ├── docx_mapping.json
│   │   │   │   ├── hwpx_mapping.json
│   │   │   │   ├── source_template.docx
│   │   │   │   └── source_template.hwpx
│   │   │   ├── edit_history/
│   │   │   │   └── edit_{generation_id}.json
│   │   │   ├── originals/
│   │   │   │   └── draft_{generation_id}.json
│   │   │   ├── candidates/
│   │   │   │   └── cand_{candidate_id}.json
│   │   │   ├── pending_review/
│   │   │   │   └── uncertain_{diff_id}.json
│   │   │   └── promotions.json
│   │   └── .../
│   └── evaluations/
│       ├── eval_{generation_id}.json
│       └── summary.json
```

### pack.json

```json
{
  "pack_id": "company_abc_exec_research_v3",
  "company_id": "abc123",
  "company_name": "M&S Solutions",
  "version": 3,
  "status": "active",
  "base_pack_ref": "_default/execution_plan/research",
  "source_documents": [
    {
      "filename": "2025_KOICA_수행계획서.hwpx",
      "uploaded_at": "2026-03-01T09:00:00Z",
      "doc_type": "execution_plan",
      "source_capability": "full"
    }
  ],
  "confidence_scores": {
    "structure_extraction": 0.92,
    "style_extraction": 0.78,
    "boilerplate_extraction": 0.85
  },
  "active_render_targets": ["docx", "hwpx"],
  "human_approved_by": "bill.min122@gmail.com",
  "approved_at": "2026-03-01T10:30:00Z",
  "edit_count": 7,
  "promotion_count": 2,
  "quality_scores": {
    "section_match_rate": 0.85,
    "style_match_rate": 0.72,
    "user_edit_rate": 0.23,
    "approval_time_avg_min": 15,
    "composite_score": 0.81
  },
  "created_at": "2026-03-01T09:00:00Z",
  "updated_at": "2026-03-11T15:30:00Z"
}
```

**Pack status lifecycle:**
```
draft → shadow → active → archived
         │                    ↑
         └── (A/B 비교 후) ──┘ (rollback 시)
```

- `draft`: 추출 직후, 사용자 리뷰 대기
- `shadow`: 실제 생성에 사용하되 기존 active pack과 A/B 비교만. 자동 적용 안 함.
  - **shadow → active 전환 정량 기준**: ① shadow pack으로 최소 3회 생성 완료, ② 3건의 composite_score 평균 >= 기존 active pack 평균 (기존 active가 없으면 >= 0.6), ③ 사용자 최종 승인. ①②③ 모두 충족 시 전환 가능.
- `active`: 생성에 사용. 회사당 doc_type/domain_type별 1개만 active.
- `archived`: 비활성화된 이전 버전.

### brand_pack.json

```json
{
  "company_name": "M&S Solutions",
  "company_name_short": "M&S",
  "logo_path": "logo.png",
  "primary_color": "#003764",
  "secondary_color": "#0070E0",
  "accent_color": "#E07B54",
  "font_primary": "Pretendard",
  "font_fallback": "맑은 고딕",
  "company_intro_short": "공공조달 AI 전문기업 M&S Solutions",
  "company_intro_full": "M&S Solutions는 2024년 설립된 공공조달 AI 전문기업으로...",
  "quality_policy": "ISO 9001 품질경영시스템 기반 프로젝트 관리",
  "footer_text": "M&S Solutions | CONFIDENTIAL",
  "cover_layout": "centered"
}
```

### semantic_tokens.json

```json
{
  "tokens": {
    "title_primary": {"role": "문서 제목", "hierarchy": 0},
    "heading_chapter": {"role": "장 제목", "hierarchy": 1, "numbering": "제{n}장"},
    "heading_section": {"role": "절 제목", "hierarchy": 2, "numbering": "{n}.{m}"},
    "heading_subsection": {"role": "항 제목", "hierarchy": 3, "numbering": "{n}.{m}.{k}"},
    "body_normal": {"role": "본문"},
    "body_emphasis": {"role": "강조 본문"},
    "table_header": {"role": "표 헤더"},
    "table_cell": {"role": "표 본문"},
    "table_total": {"role": "표 합계행"},
    "note_box": {"role": "참고 상자"},
    "tip_box": {"role": "팁 상자"},
    "warning_box": {"role": "주의 상자"},
    "caption": {"role": "표/그림 캡션"},
    "page_header": {"role": "머리글"},
    "page_footer": {"role": "바닥글"},
    "cover_title": {"role": "표지 제목"},
    "cover_subtitle": {"role": "표지 부제"},
    "cover_org": {"role": "표지 기관명"},
    "toc_entry": {"role": "목차 항목"},
    "bullet_l1": {"role": "1단계 목록"},
    "bullet_l2": {"role": "2단계 목록"},
    "numbered_l1": {"role": "1단계 번호목록"}
  }
}
```

### sections.json (연구용역형)

> **주의**: 이 구조는 부록 "연구용역형" 9장 구조와 일치해야 합니다.
> generic IT 구축형 구조와 다르며, 연구 도메인 고유 장(선행연구 검토, 연구방법론, 윤리/IRB, 연구결과 활용/확산)이 포함됩니다.

```json
{
  "document_type": "execution_plan",
  "domain_type": "research",
  "sections": [
    {
      "id": "s01",
      "name": "연구배경 및 목적",
      "level": 1,
      "required": true,
      "weight": 0.10,
      "max_score": 10,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 2000, "max_chars": 5000, "token_budget": 2500},
      "render_validation": {"min_pages": 2, "max_pages": 5, "action_on_violation": "warn"},
      "block_types": ["narrative"],
      "must_include_facts": ["발주기관명", "사업명", "연구목적"],
      "forbidden_patterns": ["~할 것임$", "~인 것으로 사료됨$", "~라고 판단됨$"],
      "evidence_policy": "required",
      "subsections": [
        {
          "id": "s01_1",
          "name": "연구 배경",
          "block_types": ["narrative"],
          "instructions": "발주기관의 정책적 배경, 현재 문제점, 연구 필요성을 RFP에서 추출하여 서술"
        },
        {
          "id": "s01_2",
          "name": "연구 목적 및 범위",
          "block_types": ["narrative"],
          "instructions": "연구의 최종 목표, 기대 산출물, 연구 범위(포함/제외)를 구체적으로 정의"
        }
      ]
    },
    {
      "id": "s02",
      "name": "선행연구 검토",
      "level": 1,
      "required": true,
      "weight": 0.10,
      "max_score": 10,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 2000, "max_chars": 5000, "token_budget": 2500},
      "block_types": ["narrative", "table"],
      "must_include_facts": ["선행연구 현황", "기존연구 한계"],
      "evidence_policy": "required",
      "subsections": [
        {"id": "s02_1", "name": "국내외 선행연구 현황", "instructions": "관련 분야 주요 선행연구 문헌 검토, 연구 동향 정리"},
        {"id": "s02_2", "name": "기존연구 한계 및 시사점", "instructions": "기존 연구의 한계점 분석, 본 연구의 차별성 도출"}
      ]
    },
    {
      "id": "s03",
      "name": "연구방법론",
      "level": 1,
      "required": true,
      "weight": 0.15,
      "max_score": 20,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 2500, "max_chars": 6000, "token_budget": 3000},
      "block_types": ["narrative", "chart"],
      "must_include_facts": ["연구방법", "분석방법"],
      "evidence_policy": "required",
      "subsections": [
        {"id": "s03_1", "name": "연구 설계", "instructions": "연구 유형(혼합연구/질적/양적/실행연구/델파이 등), 연구 프레임워크 제시"},
        {"id": "s03_2", "name": "자료 수집 방법", "instructions": "조사 대상, 표본 설계, 수집 도구(설문/면접/FGI 등) 상세 기술"},
        {"id": "s03_3", "name": "분석 방법", "instructions": "통계분석/질적분석 방법, 분석 도구, 신뢰도/타당도 확보 방안"}
      ]
    },
    {
      "id": "s04",
      "name": "연구내용",
      "level": 1,
      "required": true,
      "weight": 0.25,
      "max_score": 30,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 5000, "max_chars": 15000, "token_budget": 5000},
      "block_types": ["narrative", "table", "chart"],
      "must_include_facts": ["과업별 목표", "수행방법", "산출물"],
      "evidence_policy": "required",
      "fallback_text_policy": "generate_from_rfp",
      "priority": 1,
      "subsections": [
        {
          "id": "s04_auto",
          "name": "(RFP 과업에서 자동 생성)",
          "dynamic": true,
          "instructions": "RFP의 각 과업을 세부 섹션으로 분해. 과업별 연구목표/방법/산출물/기대효과를 서술"
        }
      ]
    },
    {
      "id": "s05",
      "name": "추진일정",
      "level": 1,
      "required": true,
      "weight": 0.10,
      "max_score": 10,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 1500, "max_chars": 4000, "token_budget": 2000},
      "block_types": ["narrative", "table", "chart"],
      "subsections": [
        {"id": "s05_1", "name": "연구 추진 일정", "block_types": ["narrative", "chart"], "instructions": "연구 단계별 마일스톤 중심 일정 서술 + 간트차트"},
        {"id": "s05_2", "name": "WBS 상세", "block_types": ["table"], "render_mode": "data_table", "instructions": "WBS 표 (schedule_planner가 데이터 생성)"}
      ]
    },
    {
      "id": "s06",
      "name": "연구진 구성",
      "level": 1,
      "required": true,
      "weight": 0.10,
      "max_score": 10,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 1500, "max_chars": 4000, "token_budget": 2000},
      "block_types": ["narrative", "table"],
      "subsections": [
        {"id": "s06_1", "name": "연구진 구성", "block_types": ["table"], "render_mode": "data_table", "instructions": "연구책임자(PI), 공동연구자, 연구보조원, 자문위원, 조사원, 통계분석가 등"},
        {"id": "s06_2", "name": "핵심연구인력 역량", "block_types": ["narrative"], "instructions": "PI, co-PI 등 핵심 연구인력의 전문분야/경력/자격을 서술"}
      ]
    },
    {
      "id": "s07",
      "name": "품질관리",
      "level": 1,
      "required": true,
      "weight": 0.08,
      "max_score": 5,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 1000, "max_chars": 3000, "token_budget": 1500},
      "block_types": ["narrative", "table"],
      "subsections": [
        {"id": "s07_1", "name": "연구 품질 관리 체계", "instructions": "연구 데이터 품질, 산출물 검증, 중간보고 등 품질관리 절차"},
        {"id": "s07_2", "name": "산출물 검증 절차"}
      ]
    },
    {
      "id": "s08",
      "name": "연구윤리 및 IRB",
      "level": 1,
      "required": false,
      "weight": 0.05,
      "max_score": 5,
      "conditions": {
        "any_of": [
          {"keyword_in_rfp": ["IRB", "생명윤리", "연구윤리", "인체유래물", "개인정보"]},
          {"keyword_in_rfp": ["설문조사", "면접조사", "FGI", "인터뷰"]}
        ]
      },
      "fallback_text_policy": "use_boilerplate",
      "generation_target": {"min_chars": 800, "max_chars": 2500, "token_budget": 1200},
      "block_types": ["narrative"],
      "subsections": [
        {"id": "s08_1", "name": "연구윤리 준수 계획", "instructions": "IRB 심의, 개인정보 보호, 연구 윤리 준수 방안"},
        {"id": "s08_2", "name": "데이터 관리 계획", "instructions": "연구데이터 수집/보관/폐기 절차, 비식별화 방안"}
      ]
    },
    {
      "id": "s09",
      "name": "연구결과 활용 및 확산",
      "level": 1,
      "required": true,
      "weight": 0.07,
      "max_score": 5,
      "conditions": {"always": true},
      "generation_target": {"min_chars": 800, "max_chars": 2000, "token_budget": 1000},
      "block_types": ["narrative"],
      "subsections": [
        {"id": "s09_1", "name": "정책 활용 방안", "instructions": "연구결과의 정책 반영 경로, 제도 개선 기여 방안"},
        {"id": "s09_2", "name": "확산 및 후속 연구", "instructions": "학술발표, 보고서 배포, 후속 연구 연계 방안"}
      ]
    }
  ]
}
```

**sections.json 스키마 규칙:**

- `render_validation`: optional 필드. 없는 섹션은 Render Validator가 **검사 스킵** (페이지 범위 제한 없음). 필요 시 구현 중 추가.
- `token_budget`: Section Writer LLM 호출 시 **`max_tokens` 파라미터에 직접 매핑**되는 출력 토큰 수 상한. 입력 컨텍스트 예산과 무관. 입력 컨텍스트는 모델 컨텍스트 윈도우 내에서 자동 truncation (exemplar → Layer1 순 축소).
- `boilerplate_mode`는 sections.json에 정의하지 않음. **`boilerplate.json`의 각 항목 `mode` 필드가 유일한 권한**. mode 종류:
  - `prepend`: LLM 생성 텍스트 앞에 고정 문구 삽입
  - `append`: LLM 생성 텍스트 뒤에 고정 문구 삽입
  - `replace`: LLM 생성 텍스트를 고정 문구로 완전 교체 (Section Writer 호출하지 않음)
  - `merge`: LLM에게 고정 문구를 "반드시 포함해야 할 내용"으로 프롬프트에 주입, 생성 텍스트에 자연스럽게 통합

### domain_dict.json (연구용역 예시)

```json
{
  "domain_type": "research",
  "roles": [
    {"id": "pi", "name": "연구책임자", "grade": "특급", "aliases": ["PI", "총괄연구원", "책임연구원"]},
    {"id": "co_pi", "name": "공동연구원", "grade": "고급", "aliases": ["공동PI", "참여연구원"]},
    {"id": "ra", "name": "연구보조원", "grade": "초급", "aliases": ["RA", "연구원"]},
    {"id": "advisor", "name": "자문위원", "grade": "특급", "aliases": ["자문교수", "전문위원"]},
    {"id": "surveyor", "name": "조사원", "grade": "중급", "aliases": ["현장조사원", "면접원"]},
    {"id": "statistician", "name": "통계분석가", "grade": "고급", "aliases": ["데이터분석가"]}
  ],
  "phases": [
    {"id": "design", "name": "연구설계", "aliases": ["연구계획수립", "프레임워크 설계"]},
    {"id": "review", "name": "선행연구 검토", "aliases": ["문헌조사", "선행연구분석"]},
    {"id": "collect", "name": "자료수집", "aliases": ["현장조사", "데이터수집", "설문조사"]},
    {"id": "analyze", "name": "분석/해석", "aliases": ["데이터분석", "결과해석"]},
    {"id": "recommend", "name": "정책제언", "aliases": ["제언도출", "시사점"]},
    {"id": "disseminate", "name": "보고/확산", "aliases": ["결과보고", "확산"]},
    {"id": "closing", "name": "사업종료", "aliases": ["완료보고"]}
  ],
  "methodologies": [
    {"id": "mixed", "name": "혼합연구방법", "aliases": ["mixed methods"]},
    {"id": "qual", "name": "질적연구", "aliases": ["qualitative", "사례연구", "FGI"]},
    {"id": "quant", "name": "양적연구", "aliases": ["quantitative", "설문조사", "통계분석"]},
    {"id": "action", "name": "실행연구", "aliases": ["action research", "참여적 연구"]},
    {"id": "delphi", "name": "델파이조사", "aliases": ["delphi", "전문가패널"]}
  ],
  "deliverables_common": [
    "연구계획서", "문헌조사보고서", "설문지/조사도구",
    "중간보고서", "분석보고서", "최종연구보고서",
    "정책제언서", "데이터셋", "연구윤리심의서"
  ],
  "organization_terms": {
    "committee": ["자문위원회", "연구심의위원회", "운영위원회"],
    "meeting": ["착수보고회", "중간보고회", "최종보고회", "자문회의"]
  },
  "common_risks": [
    {"risk": "설문 응답률 저조", "mitigation": "인센티브 제공 + 온라인/오프라인 병행"},
    {"risk": "현지 접근 제한", "mitigation": "현지 파트너 사전 확보 + 원격 대안"},
    {"risk": "연구윤리 이슈", "mitigation": "사전 IRB 심의 + 동의서 확보"}
  ],
  "quality_frameworks": ["IRB 연구윤리", "연구진실성 검증", "피어리뷰"]
}
```

### boilerplate.json

```json
{
  "boilerplates": [
    {
      "id": "bp_quality_mgmt",
      "section_id": "s06",
      "mode": "prepend",
      "text": "본 연구팀은 ISO 9001 품질경영시스템에 준하는 연구품질관리 체계를 적용하여, 연구 전 과정에서 산출물의 정확성, 완전성, 적시성을 보장합니다.",
      "tags": ["품질관리", "범용"]
    },
    {
      "id": "bp_risk_intro",
      "section_id": "s07",
      "mode": "prepend",
      "text": "사업 수행 과정에서 예상되는 리스크를 사전에 식별하고, 체계적인 대응방안을 수립하여 사업 목표 달성을 보장합니다.",
      "tags": ["리스크", "범용"]
    }
  ]
}
```

### exemplars.json

```json
{
  "exemplars": [
    {
      "id": "ex_001",
      "section_id": "s02_2",
      "domain_type": "education_oda",
      "intent": "차별화 전략 서술 — 현장 경험 기반",
      "text": "본 연구팀은 KOICA 봉사단 교육 현장에서 5년간 축적한 현지 적응형 교수법 노하우를 보유하고 있으며, 이를 기반으로 디지털 전환 시 발생할 수 있는 교육격차를 선제적으로 해소하는 3단계 완충 모델을 제안합니다.",
      "quality_score": 0.9,
      "tags": ["차별화", "실적기반", "구체적"],
      "source_doc_id": "koica_2025_proposal",
      "approved": true,
      "approved_at": "2026-03-01T10:00:00Z"
    },
    {
      "id": "ex_002",
      "section_id": "s01_1",
      "domain_type": "research",
      "intent": "사업 배경 서술 — 문제 인식 중심",
      "text": "최근 5년간 봉사단 교육 만족도는 연평균 3.2% 하락하고 있으며, 특히 ICT 활용 교육 분야에서 현지 인프라 부재(인터넷 보급률 12%)로 인한 교육 효과 저하가 심각한 상황입니다. 이에 KOICA는 디지털 전환을 통해 교육 접근성과 효과성을 동시에 개선하고자 본 연구용역을 추진합니다.",
      "quality_score": 0.85,
      "tags": ["배경", "수치기반", "문제인식"],
      "source_doc_id": null,
      "approved": true
    }
  ]
}
```

### templates/ 하위 파일

#### render_spec.json

```json
{
  "cover_page": true,
  "table_of_contents": true,
  "page_numbering": true,
  "section_rendering": {
    "s04_2": {"render_mode": "data_table", "data_source": "wbs_tasks"},
    "s05_1": {"render_mode": "data_table", "data_source": "personnel"},
    "s07_1": {"render_mode": "data_table", "data_source": "risk_table"}
  },
  "chart_rendering": {
    "s04_1": {"chart_type": "gantt", "data_source": "wbs_tasks"}
  },
  "hwpx_strategy": "sdk_first",
  "hwpx_fallback": "docx_only"
}
```

#### canonical_layout.json (Canonical IR 정의)

```json
{
  "document": {
    "blocks": [
      {"type": "cover", "token": "cover_title", "fields": ["title", "company_name", "date", "issuing_org"]},
      {"type": "toc", "token": "toc_entry", "auto_generate": true},
      {"type": "page_break"},
      {"type": "section_group", "section_id": "s01", "blocks": [
        {"type": "heading", "token": "heading_chapter"},
        {"type": "narrative", "token": "body_normal"},
        {"type": "subsection", "repeat_for_each": "subsections"}
      ]},
      {"type": "section_group", "section_id": "s03", "blocks": [
        {"type": "heading", "token": "heading_chapter"},
        {"type": "narrative", "token": "body_normal"},
        {"type": "dynamic_section_group", "source": "rfp_tasks", "template": {
          "type": "subsection", "blocks": [
            {"type": "heading", "token": "heading_section"},
            {"type": "narrative", "token": "body_normal"},
            {"type": "table", "optional": true}
          ]
        }}
      ]},
      {"type": "section_group", "section_id": "s04", "blocks": [
        {"type": "heading", "token": "heading_chapter"},
        {"type": "narrative", "token": "body_normal"},
        {"type": "chart", "chart_type": "gantt", "data_ref": "wbs_tasks"},
        {"type": "data_table", "data_ref": "wbs_tasks", "columns": ["phase", "task_name", "responsible_role", "start_month", "end_month", "man_months", "deliverables"]}
      ]},
      {"type": "section_group", "section_id": "s05", "blocks": [
        {"type": "heading", "token": "heading_chapter"},
        {"type": "data_table", "data_ref": "personnel", "columns": ["role", "name", "grade", "responsibility", "man_months"]},
        {"type": "narrative", "token": "body_normal", "subsection_id": "s05_2"}
      ]},
      {"type": "section_group", "section_id": "s07", "blocks": [
        {"type": "heading", "token": "heading_chapter"},
        {"type": "narrative", "token": "body_normal"},
        {"type": "data_table", "data_ref": "risk_table", "columns": ["risk", "probability", "impact", "mitigation", "owner"]}
      ]}
    ]
  }
}
```

#### docx_mapping.json

```json
{
  "mappings": {
    "cover_title": {"style": "Title", "font": "Pretendard", "size_pt": 24, "bold": true, "color": "#003764"},
    "heading_chapter": {"style": "Heading 1", "font": "Pretendard", "size_pt": 18, "bold": true, "color": "#003764"},
    "heading_section": {"style": "Heading 2", "font": "Pretendard", "size_pt": 14, "bold": true, "color": "#004A8F"},
    "heading_subsection": {"style": "Heading 3", "font": "Pretendard", "size_pt": 12, "bold": true, "color": "#1A1A1A"},
    "body_normal": {"style": "Normal", "font": "Pretendard", "size_pt": 11, "color": "#444444", "line_spacing": 1.25},
    "body_emphasis": {"style": "Normal", "font": "Pretendard", "size_pt": 11, "bold": true, "color": "#003764"},
    "table_header": {"font": "Pretendard", "size_pt": 10, "bold": true, "color": "#FFFFFF", "bg_color": "#003764"},
    "table_cell": {"font": "Pretendard", "size_pt": 9, "color": "#444444"},
    "table_total": {"font": "Pretendard", "size_pt": 9, "bold": true, "color": "#1A1A1A", "bg_color": "#E6F0FF"},
    "page_header": {"font": "Pretendard", "size_pt": 8, "color": "#888888"},
    "page_footer": {"font": "Pretendard", "size_pt": 8, "color": "#888888"},
    "caption": {"font": "Pretendard", "size_pt": 9, "color": "#666666", "italic": true}
  },
  "page_setup": {
    "top_margin_cm": 2.5,
    "bottom_margin_cm": 2.5,
    "left_margin_cm": 3.0,
    "right_margin_cm": 2.5
  }
}
```

### promotions.json

```json
{
  "promotion_policy": {
    "thresholds": {
      "tone": 2,
      "style": 2,
      "structure": 3,
      "layout": 3,
      "boilerplate": 3
    },
    "promotion_requires": {
      "user_approved": true,
      "min_distinct_generation_ids": 2
    },
    "risk_levels": {
      "tone": "low",
      "style": "low",
      "layout": "medium",
      "structure": "high",
      "boilerplate": "high"
    },
    "auto_promote_risk_levels": ["low"],
    "notify_risk_levels": ["medium"],
    "require_approval_risk_levels": ["high"]
  },
  "promotions": [],
  "candidates": [],
  "rollbacks": []
}
```

승격 필수 조건 (AND):
1. `user_approved`: 사용자가 "회사 문서 스킬에 학습" 선택
2. `min_distinct_generation_ids >= 2`: 최소 2개 다른 문서에서 동일 패턴
3. `occurrence_count >= threshold`: 도메인별 임계값 충족

### originals/draft_{generation_id}.json

생성 직후 원본 초안 저장 (수정 학습 diff 추출의 기준):

```json
{
  "generation_id": "gen_20260311_001",
  "created_at": "2026-03-11T10:00:00Z",
  "rfp_title": "KOICA 봉사단 치유농업 연구",
  "doc_type": "execution_plan",
  "domain_type": "research",
  "pack_version": 3,
  "sections": [
    {"section_id": "s01", "markdown": "## 사업 이해\n\n..."},
    {"section_id": "s02", "markdown": "## 수행 전략\n\n..."}
  ],
  "composite_score": 0.78
}
```

### edit_history/edit_{generation_id}.json

사용자 수정본 업로드 후 diff 결과 저장:

```json
{
  "generation_id": "gen_20260311_001",
  "edited_at": "2026-03-11T15:00:00Z",
  "diffs": [
    {
      "diff_id": "diff_001",
      "section_id": "s01",
      "diff_type": "tone",
      "classification": "persistent_preference",
      "confidence": 0.92,
      "original_text": "~할 것임",
      "edited_text": "~하겠습니다",
      "user_decision": "learn",
      "candidate_id": "cand_abc123"
    }
  ],
  "edit_rate": 0.18
}
```

### pending_review/uncertain_{diff_id}.json

Diff Classifier 신뢰도 < 0.8인 항목. TTL 30일, 미응답 시 자동 폐기:

```json
{
  "diff_id": "diff_002",
  "created_at": "2026-03-11T15:00:00Z",
  "expires_at": "2026-04-10T15:00:00Z",
  "generation_id": "gen_20260311_001",
  "section_id": "s02",
  "original_text": "본 연구팀은",
  "edited_text": "본 사업단은",
  "confidence": 0.65,
  "suggested_classification": "persistent_preference",
  "status": "pending"
}
```

---

## 4. Extraction Pipeline

### Source Capability Matrix

```
┌──────────┬──────────┬────────┬─────────────┬──────────┐
│  Format  │Structure │ Style  │ Boilerplate │ Exemplar │
├──────────┼──────────┼────────┼─────────────┼──────────┤
│ DOCX     │  full    │ full   │ full        │ full     │
│ HWPX     │  full    │ full   │ full        │ full     │
│ HWP      │ sdk_only │sdk_only│ sdk_only    │ full     │
│ PDF      │  low     │  no    │ low         │ heuristic│
└──────────┴──────────┴────────┴─────────────┴──────────┘
```

- DOCX/HWPX: 구조+스타일+보일러플레이트+예시 전부 추출 가능
- HWP: Hancom SDK로 HWPX 변환 성공 시에만 HWPX급 처리. 실패 시 텍스트만.
- PDF: 콘텐츠(텍스트+제목+목록+표)만 휴리스틱 재구성(부록 B 참조). Exemplar로 사용 시 단락 경계·목록 구조는 confidence score 검증 필수. 스타일/레이아웃은 추출 불가.

### Extraction Flow

```
회사 문서 업로드
    │
    ▼
┌──────────────────┐
│ 1. Normalizer    │  포맷별 정규화
│                  │  DOCX → python-docx 직접 파싱
│                  │  HWPX → XML 파싱
│                  │  HWP  → Hancom SDK → HWPX (실패 시 텍스트만)
│                  │  PDF  → 텍스트 추출 (레이아웃 정보 제한적)
│                  │  → source_capability 태깅
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. Classifier    │  LLM: doc_type + domain_type 판별
│                  │  Structured Outputs 사용
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. Analyzers     │  source_capability에 따라 분석 범위 결정
│   (병렬 4개)      │
│                  │  3a. Section Extractor (capability: structure >= low)
│                  │      장/절/항 트리 + 순서 추출
│                  │      DOCX: Heading 스타일 파싱
│                  │      PDF: 폰트 크기 기반 추론 (low confidence)
│                  │
│                  │  3b. Style Extractor (capability: style == full)
│                  │      PDF는 스킵
│                  │      DOCX: styles.xml + 직접 run 속성 파싱
│                  │      → semantic_tokens.json + docx_mapping.json 생성
│                  │
│                  │  3c. Boilerplate Detector (capability: boilerplate >= low)
│                  │      LLM으로 각 문단 분류:
│                  │      company_boilerplate | domain_boilerplate | bid_specific | generic_filler
│                  │      company_boilerplate만 Pack에 저장
│                  │
│                  │  3d. Exemplar Harvester (capability: exemplar == full)
│                  │      우수 문단 추출 + LLM 품질 점수
│                  │      section_id + domain_type + intent 태깅
│                  │      의도/구조 유사도 기준 (문장 유사도 아님)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. Pack Builder  │  추출 결과 → Pack Candidate 조립
│                  │  confidence_scores 산출
│                  │  status: "draft"
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. Human Review  │  사용자에게 Pack 후보 제시
│    (UI)          │  섹션 구조 / 고정 문구 / 예시 확인·편집
│                  │  승인 → status: "shadow"
│                  │  (A/B 비교 후 만족 시 → "active")
└──────────────────┘
```

---

## 5. Generation Pipeline

### 전체 흐름

```
RFP 입력
    │
    ▼
┌──────────────────┐
│ 1. Domain        │  RFP → LLM → ProjectDomain 분류
│    Detector      │  (it_build | research | consulting | education_oda | general)
│                  │  + sub_domain + methodology_hint
│                  │  키워드 fallback 유지
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. Pack          │  경로 해소 순서:
│    Resolver      │  ① {company}/{doc_type}/{domain}
│                  │  ② {company}/{doc_type}/general
│                  │  ③ _default/{doc_type}/{domain}
│                  │  ④ _default/{doc_type}/general
│                  │  → 상속 병합 (회사 필드 우선)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. Section       │  sections.json의 conditions 평가
│    Resolver      │  → 이 RFP에 활성화할 섹션 목록
│                  │  → dynamic 섹션(s03_auto): RFP 과업에서 하위섹션 자동 생성
│                  │
│                  │  섹션 상태 규칙:
│                  │    omitted: conditions 미충족 → 출력 안 함
│                  │    active: conditions 충족 → Section Writer로 생성
│                  │    active_fallback: conditions 충족이지만 RFP에
│                  │      해당 정보 부족 → fallback_text_policy 적용
│                  │      - "generate_from_rfp": LLM이 최선 추론
│                  │      - "use_boilerplate": 고정 문구만
│                  │      - "skip_with_note": 빈 섹션 + 안내문
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. Planning      │  전체 문서 전략 수립 (LLM)
│    Agent         │  → 섹션별 emphasis, differentiators, risk_notes
│                  │  → domain_dict에서 역할/방법론/산출물 결정
│                  │  → schedule_planner 호출 → WBS 데이터 (s04/s05용)
│                  │  → 리스크 테이블 데이터 (s07용)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. Section       │  섹션별 병렬 생성 (ThreadPoolExecutor)
│    Writer        │  Pack 기반 프롬프트 조립:
│    (parallel)    │    ① 도메인 인식 시스템 프롬프트
│                  │    ② pack exemplars (의도/구조 유사도로 검색)
│                  │    ③ pack boilerplate (mode: replace|append|prepend|merge)
│                  │    ④ pack forbidden/preferred patterns
│                  │    ⑤ Layer 1 knowledge (domain 필터)
│                  │    ⑥ Layer 2 company context
│                  │    ⑦ RFP context
│                  │    ⑧ section instructions + block_types + constraints
│                  │    ⑨ 산문 품질 강제 규칙
│                  │  출력: section_id → markdown text
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 6. Quality       │  Pack-aware 품질 검증
│    Checker       │  Rule-based:
│                  │    - must_include_facts 충족
│                  │    - forbidden_patterns 위반
│                  │    - evidence_policy 준수
│                  │    - generation_target 범위
│                  │    - 블라인드 위반 (기존 quality_checker 재사용)
│                  │  LLM Grader:
│                  │    - content_depth, domain_relevance, narrative_quality
│                  │    - structure_coherence, actionability (각 1~5)
│                  │  위반 시 → Section Writer 1회 재작성
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 7. Content       │  markdown → Canonical IR 변환
│    Assembler     │  블록 타입별 변환:
│                  │    narrative_block: markdown → 구조화 텍스트
│                  │    table_block: WBS/인력/리스크 데이터 → 표 IR
│                  │    chart_block: WBS 데이터 → 간트차트 IR
│                  │    boilerplate_block: 고정 문구 → 텍스트 블록
│                  │  canonical_layout.json 기준으로 블록 배치
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 8. Template      │  Canonical IR + render_spec → 최종 파일
│    Renderer      │
│                  │  DOCX 경로:
│                  │    semantic_tokens → docx_mapping.json
│                  │    base.docx(docxtpl) + 변수 주입
│                  │    python-docx로 최종 조립
│                  │
│                  │  HWPX 경로:
│                  │    1순위: Hancom SDK/Automation
│                  │    2순위: Hancom Document API (향후)
│                  │    3순위: HWPX XML 직접 조립 (fallback)
│                  │    fallback: DOCX만 출력
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 9. Render        │  렌더링 후 검증 (post-render validation)
│    Validator     │  검사 항목:
│                  │    - 섹션별 render_validation.min_pages/max_pages
│                  │    - 표 넘침 (페이지 경계에서 잘림)
│                  │    - 머리글/바닥글 존재 확인
│                  │    - TOC 생성 여부 (render_spec.table_of_contents)
│                  │    - 페이지 번호 연속성
│                  │    - 간트차트/표 삽입 확인
│                  │  action_on_violation:
│                  │    "warn" → 사용자 알림 + 로그
│                  │    "retry" → Content Assembler로 돌아가 조정 (1회)
│                  │    "block" → 생성 실패 처리
└────────┬─────────┘
         │
         ▼
    DOCX / HWPX + 원본 초안 저장 (수정 학습용)
```

### schedule_planner (기존 wbs_planner 재설계)

기존 `wbs_planner.py`의 IT 고정 템플릿과 역할 스키마를 제거하고 domain_dict 기반으로 재구성:

- 템플릿 3개(WATERFALL/AGILE/HYBRID)를 제거
- domain_dict.phases에서 단계 로드
- domain_dict.roles에서 역할 로드
- domain_dict.methodologies에서 방법론 로드
- LLM 프롬프트에 도메인 컨텍스트 주입하여 RFP 맞춤 태스크 생성
- WbsTask 스키마의 responsible_role enum을 동적으로 교체
- 기존 인력배치 로직(_allocate_personnel)은 보존

### 기존 모듈 매핑

| 기존 | 신규 | 변경 |
|------|------|------|
| `section_writer.py` | Section Writer 핵심 유지, 프롬프트를 Pack 기반으로 교체 | 리팩토링 |
| `proposal_planner.py` | Section Resolver로 교체 (sections.json 기반) | 교체 |
| `wbs_planner.py` | `schedule_planner.py`로 재설계 (domain_dict 기반) | 교체 |
| `wbs_generator.py` | XLSX/간트 유지, DOCX는 Template Renderer로 이관 | 부분 교체 |
| `wbs_orchestrator.py` | `document_orchestrator.py`에 통합 | 교체 |
| `proposal_orchestrator.py` | `document_orchestrator.py`에 통합 | 교체 |
| `document_assembler.py` | Content Assembler + Template Renderer로 분리 | 교체 |
| `quality_checker.py` | Pack-aware 확장 + LLM Grader 추가 | 확장 |
| `knowledge_db.py` | domain_type 필터 추가 | 확장 |
| `company_context_builder.py` | 보존 | 보존 |
| — | `domain_detector.py` | 신규 |
| — | `pack_manager.py` | 신규 |
| — | `pack_extractor.py` | 신규 |
| — | `section_resolver.py` | 신규 |
| — | `content_assembler.py` | 신규 |
| — | `template_renderer.py` | 신규 |
| — | `document_orchestrator.py` | 신규 |
| — | `edit_learner.py` | 신규 |

---

## 6. Learning and Promotion Governance

### Edit Learning UX Flow

```
사용자가 수정한 문서 업로드
    │
    ▼
┌──────────────────┐
│ 1. Original      │  생성 시 저장한 원본 초안 로드
│    Matcher       │  generation_id로 매칭
│                  │  원본 없으면 → "원본을 찾을 수 없습니다" 안내
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. Diff          │  섹션 단위 diff 추출
│    Extractor     │  기존 diff_tracker.py 패턴 재사용
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. Diff          │  각 diff를 분류 (LLM Structured Outputs)
│    Classifier    │
│                  │  persistent_preference:
│                  │    - tone: 어투/표현 변경
│                  │    - structure: 섹션 추가/삭제/순서
│                  │    - style: 표현 패턴 선호/금지
│                  │    - layout: 표/차트/목록 선호
│                  │    - boilerplate: 고정 문구 변경
│                  │
│                  │  bid_specific_fact:
│                  │    - 사업명, 기관명, 예산, 일정
│                  │    - 특정 과업 내용, 인명, 지명
│                  │    - 이번 RFP에만 해당하는 요구사항
│                  │
│                  │  uncertain:
│                  │    - 분류 신뢰도 0.8 미만
│                  │    → 사용자 확인 대기열로
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. User Review   │  diff를 묶어서 사용자에게 제시
│    UI            │
│                  │  "수정 내용을 분석했습니다."
│                  │
│                  │  ┌─ 어투 변경 (2건) ─────────────────────┐
│                  │  │ "~할 것임" → "~하겠습니다" (3곳)       │
│                  │  │ [회사 스킬에 학습] [이번만 적용] [무시]  │
│                  │  └───────────────────────────────────────┘
│                  │
│                  │  ┌─ 섹션 구조 변경 (1건) ────────────────┐
│                  │  │ "리스크관리" 섹션에 "대응조직" 추가      │
│                  │  │ [회사 스킬에 학습] [이번만 적용] [무시]  │
│                  │  └───────────────────────────────────────┘
│                  │
│                  │  ┌─ 이번 사업 전용 (3건) ────────────────┐
│                  │  │ "KOICA" → "KOICA 글로벌연수사업"        │
│                  │  │ 예산 "5억 원" 추가                      │
│                  │  │ (자동 제외 — 학습 대상 아님)              │
│                  │  └───────────────────────────────────────┘
│                  │
│                  │  ┌─ 판단 불확실 (1건) ─────────────────────┐
│                  │  │ "본 연구팀은" → "본 사업단은"             │
│                  │  │ [회사 스킬에 학습] [이번만 적용] [무시]    │
│                  │  └───────────────────────────────────────┘
│                  │
│                  │  안내: "회사 스킬에 학습된 패턴은 다음 문서
│                  │         생성 시 자동 반영됩니다.
│                  │         같은 패턴이 다른 문서에서도 반복되면
│                  │         정식 규칙으로 승격됩니다."
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. Candidate     │  사용자가 "회사 스킬에 학습" 선택한 것만
│    Writer        │  → candidates/ 에 저장
│                  │  필드:
│                  │    candidate_id, diff_type, pattern,
│                  │    source_generation_id, occurrence_count: 1,
│                  │    distinct_generation_ids: [gen_id],
│                  │    user_approved: true,
│                  │    first_seen, last_seen, confidence
│                  │
│                  │  기존 candidate와 패턴 매칭:
│                  │    → 동일 패턴 + 다른 generation_id
│                  │    → occurrence_count += 1
│                  │    → distinct_generation_ids에 추가
│                  │    → 승격 조건 확인
└──────────────────┘
```

### Promotion Rules

```
승격 필수 조건 (AND):
  ① user_approved == true
  ② distinct_generation_ids.length >= 2  (다른 문서 2개 이상에서 반복)
  ③ occurrence_count >= threshold[diff_type]
     - tone: 2, style: 2, layout: 3, structure: 3, boilerplate: 3

승격 실행:
  LOW risk (tone, style):
    → 자동 승격 → promotions.json 기록 → pack 반영

  MEDIUM risk (layout):
    → 자동 승격 + 사용자 알림
    → "이 패턴이 회사 스킬에 반영되었습니다: ..."

  HIGH risk (structure, boilerplate):
    → 사용자 재승인 필요
    → "이 변경을 영구 규칙으로 확정할까요?"
    → [확정] [후보 유지] [삭제]
```

### Contamination Guard

Pack에 절대 들어가면 안 되는 것:

```python
CONTAMINATION_BLOCKLIST = {
    "patterns": [
        r"\d{4}년\s*\d{1,2}월",     # 구체적 날짜
        r"\d+억\s*원",               # 구체적 금액
        r"\d+,\d{3}",               # 숫자 금액
        r"제\d+차",                  # 차수
        r"20[2-3]\d년도",            # 연도
    ],
    "entity_types": [
        "organization_name",
        "project_name",
        "person_name",
        "location_specific",
        "budget_amount",
        "contract_number",
    ],
    "llm_verify": true
}
```

### Rollback

- 모든 promotion에 rollback 가능
- `promotions.json`에서 status: "active" → "rolled_back"
- pack에서 해당 규칙 제거
- rollback 사유 기록
- 특정 pack version으로 전체 rollback 가능 (최근 10 버전 보관)

---

## 7. Evaluation

### 생성 직후 자동 평가 (3종)

**Rule-based Checker** (기존 quality_checker 확장):
- must_include_facts 충족률
- forbidden_patterns 위반 수
- evidence_policy 준수율
- generation_target 범위 확인
- 블라인드 위반 (한글 조사 인식 정규식)
- → rule_score: 0.0~1.0

**LLM Grader** (신규):
- Absolute grader: content_depth, domain_relevance, narrative_quality, structure_coherence, actionability (각 1~5)
- Pairwise grader: 이전 버전 vs 현재 버전 비교 → which_is_better + reasoning
- → llm_score: 1.0~5.0

**Pack Conformance** (신규):
- section_match_rate: 섹션 구조 일치율
- style_match_rate: 스타일 토큰 준수율
- boilerplate_inclusion: 고정 문구 포함율
- exemplar_intent_similarity: 예시와의 의도/구조 유사도 (문장 유사도 아님)
- → conformance_score: 0.0~1.0

### 수정본 업로드 후 사후 평가 (2종)

**Edit Rate**:
- 원본 대비 수정 비율 (글자 수 기준)
- → edit_rate: 0.0~1.0 (낮을수록 좋음)

**Approval Metrics**:
- time_to_approval: 생성~최종 승인 소요시간
- rewrite_count: 재생성 횟수
- section_rejection_rate: 섹션별 거부율

### 종합 KPI

```
composite_score =
  rule_score × 0.2
+ (llm_score / 5) × 0.3
+ conformance_score × 0.2
+ (1 - edit_rate) × 0.3
```

**Pairwise Grader 처리**:
- Pairwise 결과는 `composite_score`에 포함하지 않고, 별도 `trend_score`로 관리 (버전별 개선 추이 측정)
- `trend_score`: pairwise에서 "현재 > 이전" 비율 (최근 10건 이동 평균)
- **첫 생성 시**: 이전 버전이 없으므로 pairwise grader 스킵. `trend_score = null`. Absolute grader만 실행.
- Phase 5 Acceptance Criteria의 "신규 > 이전 >= 70%"는 `trend_score >= 0.7`로 측정

### 저장

```
data/company_packs/{company_id}/evaluations/
├── eval_{generation_id}.json    ← 건별 평가
└── summary.json                 ← 이동 평균, 트렌드
```

---

## 8. Failure Modes

| 실패 상황 | 대응 |
|-----------|------|
| Domain Detector 분류 실패 | keyword fallback → general pack |
| Pack 파일 손상/누락 | base_pack_ref에서 기본 pack 상속 |
| Section Writer LLM 호출 실패 | call_with_retry 2회 → fallback_text_policy 적용 |
| HWPX SDK 미설치 | hwpx_fallback: "docx_only" → DOCX만 출력 |
| 수정본 원본 매칭 실패 | 학습 불가 안내, 문서는 정상 저장 |
| Diff Classifier 신뢰도 < 0.8 | uncertain → 사용자 확인 대기 |
| Contamination Guard 오탐 | 사용자가 수동으로 "학습" 재선택 가능 |
| Pack 추출 confidence < 0.5 | 사용자에게 경고 + 수동 편집 권장 |
| 렌더 후 page_validation 위반 | warn 로그 + 사용자 알림 (자동 수정 안 함) |
| Pack version 충돌 (동시 수정) | version 번호 기반 optimistic locking |
| `_default` fallback 전체 실패 | `PackNotFoundError` raise → 사용자에게 "지원되지 않는 문서 유형" 안내 |
| Pairwise grader 이전 버전 없음 | 첫 생성 시 pairwise 스킵, absolute grader만 실행, trend_score = null |
| uncertain diff 사용자 미응답 | TTL 30일 → 자동 폐기. `pending_review/` 디렉토리에 저장, 만료 시 삭제 |
| Candidate 패턴 동일성 판단 | 기존 `diff_tracker.py`의 `pattern_key` 해시 방식 재사용. 표현 다른 동일 의도는 별개 candidate로 누적 (Phase 4+ 에서 임베딩 기반 개선 검토) |

---

## 9. Migration from Current System

### 보존하는 것

- `knowledge_db.py` + Layer 1 495 유닛 — domain_type 필터만 추가
- `company_context_builder.py` — Layer 2 회사 컨텍스트 그대로 유지
- `company_db.py` — 실적/인력 ChromaDB 유지
- `diff_tracker.py` — diff 추출 로직 재사용
- `auto_learner.py` — 패턴 매칭/승격 로직 참고
- `quality_checker.py` — 블라인드/모호 검사 확장
- `wbs_generator.py` — XLSX/간트차트 생성 유지 (DOCX 부분만 제거)
- `llm_utils.py` — call_with_retry 그대로 사용
- 기존 API 엔드포인트 — `/api/generate-proposal-v2`, `/api/generate-wbs` 유지 (내부만 교체)

### 교체하는 것

- `wbs_planner.py` → `schedule_planner.py` (domain_dict 기반)
- `proposal_planner.py` → `section_resolver.py` (sections.json 기반)
- `wbs_orchestrator.py` + `proposal_orchestrator.py` → `document_orchestrator.py` (통합)
- `document_assembler.py` → `content_assembler.py` + `template_renderer.py` (분리)
- `section_writer.py` 프롬프트 → Pack 기반으로 교체 (함수 시그니처 유지)

### 호환성

기존 `/api/generate-proposal-v2`와 `/api/generate-wbs` 엔드포인트는 유지. 내부 구현만 `document_orchestrator.py`로 라우팅. 기존 클라이언트 코드 변경 없이 동작.

`/api/proposal/generate` (v1)은 절대 삭제 금지 (CLAUDE.md 규칙).

---

## 10. Rollout Plan

### Phase 1: 기본 Guide Pack + 수행계획서 품질 개선

- 기본 Guide Pack 4종 구축 (it_build, research, consulting, education_oda)
- `domain_detector.py` 구현
- `schedule_planner.py` 구현 (wbs_planner 대체)
- `section_resolver.py` 구현
- Section Writer 프롬프트 Pack 기반 교체
- `document_orchestrator.py` 구현 (수행계획서 경로)
- Quality Checker 확장 (must_include_facts, forbidden_patterns)
- **Acceptance Criteria**:
  - KOICA 수행계획서 재생성: llm_score >= 3.5/5.0 (narrative_quality + domain_relevance 평균)
  - 도메인별 섹션 구조 완전 포함 (section_match_rate >= 0.95, required 전수 포함)
  - 각 섹션 산문 generation_target.min_chars 충족
  - 도메인 감지 정확도: 4종 테스트 케이스 전부 정확 분류 (`rag_engine/tests/fixtures/domain_detection/` 에 it_build/research/consulting/education_oda RFP 텍스트 파일 사전 준비)
  - 기존 `/api/generate-wbs` 엔드포인트 호환 유지 (regression 없음)

### Phase 2: Template Renderer + DOCX 렌더링

- `content_assembler.py` 구현 (markdown → Canonical IR)
- `template_renderer.py` 구현 (IR → DOCX)
- `render_validator.py` 구현 (post-render 검증)
- semantic_tokens + docx_mapping 적용
- 기본 base.docx 템플릿 제작
- **Acceptance Criteria**:
  - 렌더링된 DOCX가 KRDS 디자인 기준 충족 (style_match_rate >= 0.85)
  - 표/간트차트/페이지번호/머리글/바닥글 모두 정상 렌더
  - render_validation 위반 0건 (warn 포함)
  - Canonical IR → DOCX round-trip에서 콘텐츠 손실 없음

### Phase 3: Pack Extractor + 회사 문서 학습

- `pack_extractor.py` 구현
- Source Capability Matrix 적용 (PDF 격하 포함)
- Pack 리뷰 UI (프론트엔드)
- draft → shadow → active 3단계 전환 플로우
- **Acceptance Criteria**:
  - DOCX 업로드 → pack 추출: structure confidence >= 0.8
  - shadow pack으로 생성한 문서의 conformance_score >= 0.7
  - shadow → active 전환: 3회 생성 + composite_score >= 기존 active 평균 + 사용자 승인
  - PDF 업로드 시 style/layout 추출 시도 없음 (capability matrix 준수)

### Phase 4: Edit Learning Loop

- `edit_learner.py` 구현 (Diff Classifier + Contamination Guard)
- 수정본 업로드 UI + diff 리뷰 UX
- Promotion/Rollback 거버넌스
- **Acceptance Criteria**:
  - Diff Classifier: persistent vs bid_specific 분류 정확도 >= 0.85 (`rag_engine/tests/fixtures/diff_classification/` 에 레이블 데이터셋 20건+ 사전 준비)
  - Contamination Guard: bid_specific 패턴이 pack에 승격되는 경우 0건
  - 승격 조건 준수: user_approved + distinct_generation_ids >= 2 + threshold 충족
  - LOW risk 자동 승격 후 다음 생성에서 해당 패턴 반영 확인
  - Rollback 후 pack 원복 확인

### Phase 5: 제안서 + PPT 통합

- proposal 경로를 document_orchestrator에 통합
- ppt 경로 통합
- Evaluation 체계 + LLM Grader + Pairwise Grader
- **Acceptance Criteria**:
  - 제안서/수행계획서/PPT 모두 동일 document_orchestrator로 생성
  - 기존 `/api/generate-proposal-v2`, `/api/generate-ppt` 호환 유지
  - LLM Grader llm_score >= 3.5 (모든 문서 타입)
  - Pairwise Grader: 신규 생성 > 이전 생성 비율 >= 70%

### Phase 6: HWPX + 고급 기능

- HWPX 렌더링 (Hancom SDK 우선, XML 직접 조립은 fallback만)
- Pack 버전 비교/롤백 UI
- DPO/SFT 검토 (편집 이력 충분 시)
- **Acceptance Criteria**:
  - HWPX 출력: Hancom Viewer에서 정상 열림 + 스타일 유지
  - SDK 미설치 환경: DOCX fallback 정상 동작
  - 롤백: 임의 버전으로 전체 rollback 후 정상 생성 확인

---

## 부록: 기본 Guide Pack 4종 섹션 구조 요약

### IT 구축형

사업이해 → 수행전략 → 기술적 접근방안 → 세부수행방안 → WBS/일정 → 투입인력 → 품질관리(감리대응) → 보안관리 → 리스크관리 → 기대효과

### 연구용역형

연구배경/목적 → 선행연구 검토 → 연구방법론 → 연구내용(과업별) → 추진일정 → 연구진 구성 → 품질관리 → 윤리/IRB → 연구결과 활용/확산

### 컨설팅/PMO형

사업이해 → 진단방법론 → 현황진단계획 → 개선방안 수립 → 실행지원 → 변화관리 → 추진일정 → 투입인력 → 품질관리 → 기대효과

### 교육/ODA형

사업이해 → 사전조사계획 → 교육과정 설계 → 콘텐츠 개발 → 시범/본운영 → 성과평가 → 현지이관/지속가능성 → 추진일정 → 투입인력 → 리스크관리

---

## 부록 B: PDF Paragraph Reconstruction Policy

> **통합 지점**: 이 파이프라인은 **Section 4 Extraction Pipeline의 Step 1 Normalizer** 내부에서 `source_format == "pdf"` 일 때 실행되는 PDF 전용 브랜치다. B.7 Step 7 완료 후 출력(`ReconstructedBlock[]`)은 Section 4의 Step 2 Classifier로 전달되며, 이후 Step 3 Analyzers는 `source_capability: {structure: "low", style: "no"}` 태깅에 따라 Section Extractor(low confidence)와 Exemplar Harvester만 실행한다. Style Extractor는 PDF에서 스킵된다. HWP 처리는 이 부록과 무관하며, Section 4 Normalizer의 SDK 변환 흐름(`HWP → Hancom SDK → HWPX`)을 따른다.

### B.1 문제 정의

PDF는 **페이지 렌더링 포맷**이지 문서 구조 포맷이 아니다. 텍스트는 절대 좌표의 글리프 스트림으로 저장되며, "단락", "제목", "목록"의 개념이 없다. 기존 PDF 파서(PyMuPDF, pdfplumber 등)는 단순 텍스트 추출 시 다음 문제를 발생시킨다:

| 증상 | 원인 |
|------|------|
| 한 단락이 여러 줄로 분리 | 줄바꿈(soft break)과 단락 끝(hard break) 구분 불가 |
| 두 단락이 하나로 합쳐짐 | 행간 거리 임계값 부재 |
| 표 내용이 본문에 혼입 | 표 영역 감지 없이 행 순서대로 추출 |
| 머리글/바닥글이 본문에 포함 | 반복 영역 감지 미비 |
| 2단 레이아웃 순서 뒤섞임 | 컬럼 감지 없이 y좌표 순 정렬 |
| 목록 항목이 연속 텍스트로 | bullet/번호 패턴 미인식 |

### B.2 Source Capability Matrix 재확인

PDF에서 추출 가능한 것과 불가능한 것을 명확히 구분:

| 능력 | PDF | DOCX | HWPX |
|------|-----|------|------|
| 텍스트 콘텐츠 | ✅ (재구성 필요) | ✅ 원본 | ✅ 원본 |
| 단락 경계 | ⚠️ 휴리스틱 | ✅ `<w:p>` | ✅ `<hp:p>` |
| 제목 수준 | ⚠️ 폰트 크기 추정 | ✅ Style ID | ✅ Style ID |
| 목록 구조 | ⚠️ 패턴 매칭 | ✅ `<w:numPr>` | ✅ 원본 |
| 표 구조 | ⚠️ 셀 경계 추정 | ✅ `<w:tbl>` | ✅ 원본 |
| 스타일/폰트 | ❌ 추출 불가 | ✅ Full | ✅ Full |
| 레이아웃/여백 | ❌ 추출 불가 | ✅ Full | ✅ Full |
| 이미지 위치 | ⚠️ 좌표만 | ✅ 앵커 | ✅ 앵커 |

**원칙**: PDF에서는 **콘텐츠 구조**(텍스트+제목+목록+표)만 추출한다. 스타일/레이아웃은 절대 추출 시도하지 않는다.

### B.3 7-Step Reconstruction Pipeline

```
┌──────────────────────────────────────────────────────────┐
│  Step 1: Type Detection                                  │
│  입력 PDF의 특성 분석 (단/다단, 표 밀도, 언어)          │
├──────────────────────────────────────────────────────────┤
│  Step 2: Pre-normalize                                   │
│  인코딩 정규화, 리거처 해제, 유니코드 NFC               │
├──────────────────────────────────────────────────────────┤
│  Step 3: Layout-aware Extraction                         │
│  pdfplumber로 글리프 좌표 추출 + 행/블록 클러스터링     │
├──────────────────────────────────────────────────────────┤
│  Step 4: Region Segmentation                             │
│  머리글/바닥글/본문/사이드바/표 영역 분류               │
├──────────────────────────────────────────────────────────┤
│  Step 5: Paragraph Reconstruction                        │
│  soft break vs hard break 판단 + 단락 병합              │
├──────────────────────────────────────────────────────────┤
│  Step 6: Semantic Classification                         │
│  제목/본문/목록/표캡션/인용 분류                        │
├──────────────────────────────────────────────────────────┤
│  Step 7: Confidence Scoring + Human Review Flag          │
│  블록별 신뢰도 산출 + 저신뢰 구간 마킹                 │
└──────────────────────────────────────────────────────────┘
```

### B.4 Step 1: Type Detection

PDF를 분석하기 전에 문서 유형을 파악하여 이후 단계의 파라미터를 조정:

```python
class PdfDocumentType:
    column_count: int          # 1 | 2 | 3 (첫 5페이지 샘플링)
    has_tables: bool           # 표 존재 여부
    table_density: float       # 0.0~1.0 (표가 차지하는 면적 비율)
    primary_language: str      # "ko" | "en" | "mixed"
    avg_font_size: float       # 본문 추정 폰트 크기
    has_header_footer: bool    # 반복 영역 존재
    page_orientation: str      # "portrait" | "landscape"
```

**감지 방법**:
- 컬럼: 페이지 중앙 40% 영역의 글리프 밀도로 판단 (밀도 < 0.1이면 2단 추정)
- 표: pdfplumber `find_tables()` 또는 선(line) 교차점 패턴
- 머리글/바닥글: 3+페이지에서 동일 y좌표 범위에 동일 텍스트 반복

### B.5 Step 2: Pre-normalize

```python
def pre_normalize(text: str) -> str:
    """PDF 추출 텍스트 정규화."""
    text = unicodedata.normalize("NFC", text)      # 유니코드 정규화
    text = re.sub(r"ﬁ", "fi", text)                # 리거처 해제
    text = re.sub(r"ﬂ", "fl", text)
    text = re.sub(r"ﬀ", "ff", text)
    text = re.sub(r"\u00AD", "", text)              # soft hyphen 제거
    text = re.sub(r"[ \t]+", " ", text)             # 연속 공백 정규화
    return text
```

한글 PDF 특수 처리:
- CID 폰트 매핑 실패 시 fallback 인코딩 시도 (CP949 → UTF-8)
- 한글 조사가 분리 추출되는 경우 재결합 (`"연구" + " " + "를"` → `"연구를"`)

### B.6 Step 3: Layout-aware Extraction

pdfplumber의 `extract_words()` 대신 `chars` 레벨 접근:

```python
def extract_text_blocks(page) -> list[TextBlock]:
    """글리프 좌표 기반 텍스트 블록 추출."""
    chars = page.chars  # [{text, x0, y0, x1, y1, size, fontname}, ...]

    # 1. 같은 행: y0 차이 < font_size * 0.3 → 같은 라인
    lines = cluster_by_y(chars, threshold_ratio=0.3)

    # 2. 다단 감지: x0 기준 클러스터링
    if doc_type.column_count > 1:
        columns = split_columns(lines, doc_type.column_count)
        lines = interleave_columns(columns)  # 컬럼 순서대로 재정렬

    # 3. 행 → 블록: 행간 거리로 그룹핑
    blocks = group_lines_to_blocks(lines, line_spacing_threshold)

    return blocks
```

**line_spacing_threshold 결정**:
- 평균 행간(leading)의 1.5배 초과 시 단락 분리
- 한글 문서: 기본 행간이 넓으므로 1.8배 적용
- 표 내부: 행간 무시, 셀 경계 기준

### B.7 Step 4: Region Segmentation

페이지를 의미 영역으로 분할:

```
┌─────────────────────────────┐
│       Header Zone           │  ← y < page_height * 0.08
├─────────────────────────────┤
│                             │
│       Body Zone             │  ← 본문 영역
│                             │
│    ┌───────────────┐        │
│    │  Table Zone   │        │  ← 선 교차점 감지
│    └───────────────┘        │
│                             │
├─────────────────────────────┤
│       Footer Zone           │  ← y > page_height * 0.92
└─────────────────────────────┘
```

**분류 규칙**:
- Header/Footer: 3+페이지 반복 텍스트 (Levenshtein 유사도 >= 0.85)
- Table: pdfplumber `find_tables()` 결과 + 선 교차 패턴
- Sidebar: 본문 영역 외곽 좁은 컬럼 (폰트 크기 < 본문 평균의 0.8)
- Body: 나머지 모든 영역

**제거 대상**: Header, Footer는 최종 출력에서 제외 (페이지 번호, 문서 제목 반복 등)

### B.8 Step 5: Paragraph Reconstruction

가장 핵심적인 단계. Soft break(줄바꿈)과 hard break(단락 끝)를 구분:

**판단 기준** (가중 점수 방식):

| 신호 | hard break 점수 | 설명 |
|------|-----------------|------|
| 행간 > threshold | +3 | 단락 간 여백 |
| 다음 행 들여쓰기 | +2 | 새 단락 시작 |
| 현재 행 길이 < 평균의 70% | +1 | 짧은 행으로 끝남 |
| 다음 행 대문자/번호 시작 | +1 | 새 항목 시작 |
| 현재 행 마침표/물음표로 끝남 | +1 | 문장 종료 |
| 폰트 크기 변화 | +3 | 제목→본문 전환 |
| 글머리 기호 패턴 | +2 | 목록 항목 |

**hard break 판정**: 총점 >= 3

**한글 특수 규칙**:
- `다.`, `함.`, `임.`, `됨.` 등 한글 종결어미 + 마침표 → hard break +2
- `- `, `• `, `① `, `가. `, `1) ` 등 한글 목록 패턴 → hard break
- 조사 분리 (`"을" "위해"`) → 앞 블록에 합치기 (soft break)

### B.9 Step 6: Semantic Classification

재구성된 단락에 의미 태그 부여:

```python
class SemanticType(Enum):
    HEADING_1 = "heading_1"    # 대제목
    HEADING_2 = "heading_2"    # 중제목
    HEADING_3 = "heading_3"    # 소제목
    BODY = "body"              # 본문
    LIST_ITEM = "list_item"    # 목록 항목
    TABLE_CAPTION = "table_caption"  # 표 제목
    FIGURE_CAPTION = "figure_caption"  # 그림 제목
    QUOTE = "quote"            # 인용
    PAGE_NUMBER = "page_number"  # 페이지 번호 (제거 대상)
```

**분류 규칙** (순서대로 적용):

1. **폰트 크기 기반**: 본문 평균 대비 1.3x+ → heading, 1.2x+ → heading_2, 1.1x+ → heading_3
2. **볼드 + 짧은 텍스트**: Bold + 길이 < 50자 → heading 후보
3. **번호 패턴**: `제N장`, `N.`, `N.N`, `가.`, `(N)` → heading 후보
4. **목록 패턴**: `- `, `• `, `① `, `◦ `, `※ ` → list_item
5. **표/그림 캡션**: `[표 N]`, `<표 N>`, `[그림 N]`, `Figure N` → caption
6. **나머지**: body

### B.10 Step 7: Confidence Scoring

각 블록에 신뢰도 점수를 부여하여 자동 처리 가능 여부를 판단:

```python
class ReconstructedBlock:
    text: str
    semantic_type: SemanticType
    confidence: float          # 0.0 ~ 1.0
    page_number: int
    needs_review: bool         # confidence < 0.6이면 True
    review_reason: str         # 왜 신뢰도가 낮은지
```

**신뢰도 감점 요인**:

| 요인 | 감점 | 설명 |
|------|------|------|
| 다단 레이아웃 교차점 | -0.2 | 컬럼 간 텍스트 혼입 가능 |
| 표 인접 텍스트 | -0.15 | 표 셀과 본문 혼동 |
| 이미지 위 텍스트 | -0.2 | OCR 필요 가능 |
| 폰트 정보 누락 | -0.3 | semantic 분류 불가 |
| 한글+영문 혼합 행 | -0.1 | 단어 경계 모호 |
| 행간 불균일 | -0.15 | hard/soft break 판단 불확실 |

**처리 정책**:
- `confidence >= 0.8`: 자동 처리, 리뷰 불필요
- `0.6 <= confidence < 0.8`: 자동 처리하되 리뷰 플래그 표시
- `confidence < 0.6`: 원본 텍스트 유지 + `needs_review = True` + 사용자에게 경고

### B.11 Pack Extractor 연동

PDF에서 추출한 결과를 Pack에 반영하는 범위:

```python
class PdfExtractionResult:
    """PDF에서 추출 가능한 Pack 요소."""

    # ✅ 추출 가능 (structure)
    sections: list[ExtractedSection]     # 섹션 이름 + 순서
    section_hierarchy: dict              # 제목 수준 관계

    # ✅ 추출 가능 (content)
    boilerplate_candidates: list[str]    # 반복 등장하는 문구
    exemplar_texts: list[str]            # 섹션별 본문 텍스트

    # ⚠️ 추정만 가능 (medium confidence)
    heading_style_hints: dict            # 폰트 크기/볼드 정보 (semantic token에 직접 매핑 안 함)

    # ❌ 추출 불가 (style/layout)
    # - 여백, 행간, 폰트 패밀리, 색상 등은 PDF에서 추출하지 않음
    # - 사용자에게 안내: "정확한 스타일 적용을 위해 DOCX 또는 HWPX 원본을 업로드해 주세요"
```

**PDF 업로드 시 사용자 안내 메시지**:
> "PDF에서 문서 구조(섹션, 목록, 표)를 추출했습니다. 다만 PDF 특성상 스타일(폰트, 여백, 색상)은 추출할 수 없습니다. 정확한 스타일 재현이 필요하시면 원본 DOCX 또는 HWP 파일을 업로드해 주세요."

**confidence 기반 Pack 반영**:
- `avg_confidence >= 0.8`: sections.json에 자동 반영 (draft 상태)
- `0.6 <= avg_confidence < 0.8`: 추출 결과를 사용자에게 보여주고 확인 후 반영
- `avg_confidence < 0.6`: 수동 입력 권장, 추출 결과는 참고용으로만 제공
