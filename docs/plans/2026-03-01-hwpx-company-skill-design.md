# HWPX 템플릿 + 회사별 Skill File 시스템 설계

> 작성일: 2026-03-01
> 상태: 설계 완료, 구현 계획 수립 대기

---

## 1. 핵심 컨셉

**"회사의 제안서 DNA를 학습하고, 그 회사만의 양식으로 생성한다"**

각 회사가 가진 고유한 제안서 작성 패턴(폰트, 레이아웃, 문체, 강점 표현, 평가항목별 전략)을 `profile.md` 파일로 추출/학습하고, HWPX 템플릿에 AI 생성 콘텐츠를 주입하여 **회사 양식이 100% 보존된** 제안서를 출력한다.

### 왜 profile.md인가?

- **LLM 최적**: 마크다운은 LLM이 읽고 쓰기에 최적화된 포맷
- **사람 편집 가능**: 개발자가 아닌 영업 담당자도 직접 수정 가능
- **버전 관리**: Git diff로 변경 이력 추적, 롤백 용이
- **diff 학습 자연스러움**: auto_learner가 패턴 추출 → md 섹션 업데이트로 직결
- **Layer 2의 구체적 구현체**: 추상적 "회사 맞춤"이 하나의 파일로 수렴

### 왜 HWPX인가?

- 공공조달 제안서의 사실상 표준 포맷 (한글 기반)
- XML 기반 개방형 포맷 (ZIP + XML) → 프로그래밍 가능
- 회사 고유 양식 보존이 평가에 직접 영향 (표지, 머리글/꼬리글, 표 스타일 등)
- `python-hwpx` 라이브러리로 서버사이드 처리 가능 (순수 Python, 크로스 플랫폼)

---

## 2. 디렉토리 구조

```
data/company_skills/
  _default/                       ← Kira 기본 템플릿 (회사 템플릿 없을 때 사용)
    profile.md                    ← 범용 프로필 (Layer 1 지식 기반)
    templates/
      proposal_default.hwpx       ← Kira 기본 제안서 템플릿
      wbs_default.hwpx
      ppt_default.hwpx

  {company_id}/
    profile.md                    ← 회사별 "스킬 파일" (핵심)
    profile_history/              ← 버전 관리 (Phase C)
      profile_v001.md
      profile_v002.md
      changelog.json              ← 버전별 변경 사유 + 수정률 KPI
    templates/
      proposal_template.hwpx      ← 회사 고유 제안서 템플릿
      wbs_template.hwpx
    past_proposals/               ← 분석 완료된 과거 제안서 원본 (HWPX)
    style_assets/                 ← 로고, 워터마크 등
```

### 템플릿 없는 회사 처리

회사가 "우리는 양식이 없어요"인 경우:
1. `_default/` 디렉토리의 Kira 기본 템플릿 사용
2. 기본 템플릿은 Layer 1 지식(495 유닛)으로 학습된 공공조달 최적 양식
3. 사용하면서 점진적으로 회사 고유 패턴 축적 → 자체 템플릿으로 진화

---

## 3. profile.md 구조

```markdown
# {회사명} 제안서 프로필

## 문서 스타일
- 본문 폰트: 함초롬바탕 11pt
- 제목 폰트: 함초롬돋움 16pt Bold
- 줄간격: 160%
- 여백: 상3.0/하2.5/좌3.0/우2.5cm
- 페이지 번호: 하단 중앙, "- {n} -" 형식

## 문체
- 어미: ~합니다 (경어체)
- 문장 길이: 평균 40자 이하 (간결체)
- 강조 표현: "검증된", "축적된 노하우", "실질적 성과"
- 금지 표현: "최선을 다하겠습니다", "노력하겠습니다" (모호)
- 수치 표현: 가능한 정량적 ("3건" > "다수")

## 강점 표현 패턴
- 유사 실적: "{건수}건의 유사사업 수행으로 검증된 수행능력"
- 기술력: "자사 보유 {기술명} 기반 최적 솔루션"
- 인력: "{등급} {인원}명의 전문인력 투입"
- 사후관리: "무상 {기간}년 하자보수 + 24시간 긴급대응 체계"

## 평가항목별 전략
- 기술이해도: 발주처 pain point 재정의 → "왜 이 사업이 필요한지" 먼저 서술
- 수행방법론: 3단계 접근법 선호 (As-Is 분석 → Gap 도출 → To-Be 설계)
- 프로젝트 관리: WBS 주 단위, 마일스톤 5개+, 위험관리 매트릭스 포함
- 투입인력: 유사 프로젝트 경력 강조, PM 이력 상세 기술
- 기대효과: 정량적 KPI (현재 vs 목표 비교표)

## 승패 패턴 (Layer 3 연동 예정)
- 잘 되는 분야: IT 용역, 정보시스템 구축, 데이터 분석
- 약한 분야: 하드웨어 납품, 건설 감리
- 자주 받는 감점: 표 제목 누락, 페이지 초과, 요구사항 매핑 누락

## HWPX 생성 규칙
- 표지: 회사 로고(style_assets/logo.png) 우상단 배치
- 목차: 자동 생성, 점선 리더
- 표 스타일: 헤더 #003764 배경 + 흰색 글자, 본문 격행 #F5F7FA
- 그림/도표: 중앙 정렬, 캡션 "그림 {n}. {제목}" 형식
- 각주: 출처 표기 시 사용

## 학습 이력
- 2026-03-01: 초기 프로필 생성 (과거 제안서 3건 분석)
- 2026-03-05: "제안 배경" 섹션 톤 수정 반영 (diff_tracker)
```

### profile.md가 커버하는 범위

| 영역 | 설명 | 소스 |
|---|---|---|
| 문서 스타일 | 폰트, 여백, 줄간격, 표 스타일 | HWPX 템플릿 자동 분석 + 과거 제안서 |
| 문체 | 어미, 강조/금지 표현, 문장 길이 | company_analyzer + diff 학습 |
| 강점 패턴 | 실적/기술/인력 표현 공식 | 과거 제안서 분석 + diff 학습 |
| 평가항목 전략 | 항목별 서술 전략, 접근법 | 과거 낙찰 제안서 분석 |
| 승패 패턴 | 강/약 분야, 빈출 감점 | Layer 3 승패 분석 (로드맵) |
| HWPX 규칙 | 레이아웃, 캡션, 각주 규칙 | HWPX 템플릿 자동 추출 |

---

## 4. 아키텍처

### 4.1 온보딩 흐름

```
[과거 제안서 업로드 (HWPX)]
  → hwpx_parser.py: 구조 분석 (섹션/스타일/폰트 추출)
  → company_analyzer.analyze_company_style(): 문체/강점/톤 분석
  → company_profile_builder.py: 분석 결과 → profile.md 자동 생성
  → 사용자 확인: "이 스타일로 이해했습니다. 맞나요?"
  → profile.md 저장 + past_proposals/에 원본 보관

[HWPX 템플릿 업로드 (선택)]
  → hwpx_parser.py: 양식 구조 분석 (표지/목차/머리글/꼬리글/표 스타일)
  → profile.md의 "문서 스타일" + "HWPX 생성 규칙" 섹션 자동 보강
  → templates/에 저장
```

**핵심**: 과거 제안서가 HWPX이므로, 한 번의 업로드로 **콘텐츠 분석(문체/강점) + 양식 분석(스타일/레이아웃)** 동시 수행 가능. 별도 템플릿 업로드 없이도 과거 제안서에서 양식을 추출할 수 있다.

### 4.2 생성 흐름

```
RFP 분석 결과
  + profile.md (회사 DNA — 문체, 전략, 스타일)
  + Layer 1 지식 (범용 노하우 495유닛)
  + Layer 2 회사 데이터 (CompanyDB 실적/인력)
  ↓
section_writer (5계층 프롬프트)
  [Layer 1] 범용 지식
  [Layer 2] CompanyDB 실적/인력
  [Profile] profile.md 문체+전략+강점패턴  ← 신규 계층
  [RFP] 해당 사업 요구사항
  [생성 지시] 섹션별 작성 지시
  ↓
마크다운 섹션 콘텐츠 생성
  ↓
[HWPX 템플릿 있음?]
  Yes → hwpx_injector: 템플릿 section*.xml에 콘텐츠 주입
        → HWPX 출력 (회사 양식 100% 보존)
  No  → document_assembler: DOCX 생성 (profile.md 스타일 규칙 적용)
        또는 _default/ 기본 HWPX 템플릿 사용
```

### 4.3 학습 루프

```
생성된 제안서
  → 사용자 검토/수정 (HWPX 에디터에서)
  → 수정된 HWPX 재업로드
  → diff_tracker: AI 원본 vs 수정본 비교
  → auto_learner: 패턴 추출 (3회 이상 반복 시 자동 반영)
  → company_profile_updater: profile.md 해당 섹션 업데이트
  → profile_history/에 이전 버전 보관 + changelog.json 기록
```

### 4.4 버전 관리 + 롤백 (Phase C)

```json
// changelog.json
{
  "versions": [
    {
      "version": 1,
      "date": "2026-03-01",
      "reason": "초기 프로필 생성 (과거 제안서 3건 분석)",
      "proposals_after": 0,
      "edit_rate_after": null
    },
    {
      "version": 2,
      "date": "2026-03-05",
      "reason": "기술이해도 섹션 톤 수정 반영 (diff 3회 누적)",
      "proposals_after": 5,
      "edit_rate_after": 0.18
    },
    {
      "version": 3,
      "date": "2026-03-10",
      "reason": "수행방법론 접근법 변경 반영",
      "proposals_after": 3,
      "edit_rate_after": 0.30
    }
  ]
}
```

수정률이 이전 버전보다 유의미하게 높아지면(예: 10%p+) → 자동 롤백 제안.

---

## 5. 신규 모듈

| 모듈 | 역할 | Phase |
|---|---|---|
| `hwpx_parser.py` | python-hwpx로 HWPX 읽기 + 구조 분석 (섹션/스타일/폰트/표/머리글 추출) | B |
| `hwpx_injector.py` | HWPX 템플릿의 section*.xml에 생성된 콘텐츠 주입 (XML lxml 조작) | B |
| `company_profile_builder.py` | 과거 제안서(HWPX) 분석 → profile.md 자동 생성 | A |
| `company_profile_updater.py` | diff 학습 결과 → profile.md 자동 업데이트 + 버전 관리 | C |

### HWPX 구조 참고 (python-hwpx)

```
proposal.hwpx (ZIP)
├── META-INF/manifest.xml
├── Contents/
│   ├── content.hpf          ← 문서 메타데이터
│   ├── header.xml           ← 머리글
│   ├── section0.xml         ← 본문 (핵심)
│   └── ...
├── settings.xml              ← 문서 설정 (여백, 줄간격 등)
└── Preview/
    └── PrvImage.png          ← 미리보기
```

section*.xml 구조:
```xml
<hp:p>                        ← 문단
  <hp:run>                    ← 텍스트 런
    <hp:rPr>                  ← 런 속성 (폰트, 크기, 굵기)
      <hp:fontRef hangul="함초롬바탕" latin="Times New Roman"/>
    </hp:rPr>
    <hp:t>본문 텍스트</hp:t>
  </hp:run>
</hp:p>
```

---

## 6. 기존 모듈 연동

| 기존 모듈 | 변경 내용 | Phase |
|---|---|---|
| `company_analyzer.py` | `analyze_company_style()` → `profile.md` 포맷 변환 메서드 추가 | A |
| `section_writer.py` | 5계층 프롬프트: Profile 계층 추가 (profile.md system prompt 주입) | A |
| `auto_learner.py` | `doc_type="hwpx"` 추가 + profile.md 업데이트 트리거 | C |
| `proposal_orchestrator.py` | HWPX 출력 경로 분기 (DOCX or HWPX) | B |
| `main.py` | 프로필 CRUD API + HWPX 템플릿 업로드 API + HWPX 생성 API | A,B |

---

## 7. 기술 스택

| 항목 | 선택 | 이유 |
|---|---|---|
| HWPX 라이브러리 | `python-hwpx` (airmang) | 순수 Python, lxml 의존만, MIT, SaaS 서버 배포 가능 |
| 프로필 포맷 | Markdown (.md) | LLM 최적, 사람 편집 가능, 버전 관리 용이 |
| XML 조작 | lxml (python-hwpx 의존성) | XPath 지원, 네임스페이스 처리 |
| 스타일 추출 | company_analyzer (기존) + hwpx_parser (신규) | 콘텐츠는 기존, 양식은 신규 |
| 학습 루프 | auto_learner + diff_tracker (기존) | profile.md 업데이트 트리거만 추가 |

### python-hwpx vs pyhwpx 비교

| | python-hwpx | pyhwpx |
|---|---|---|
| 플랫폼 | **크로스 플랫폼** | Windows only |
| 의존성 | lxml만 | 한컴오피스 설치 필수 |
| 방식 | ZIP+XML 직접 조작 | 한컴 COM 자동화 |
| SaaS 배포 | **가능** (Docker/Linux) | 불가능 |
| 라이선스 | MIT | MIT |

→ SaaS 서버 배포를 위해 **python-hwpx** 확정.

---

## 8. 출력 전략 (하이브리드)

### 케이스별 동작

| 상황 | 동작 | 출력 |
|---|---|---|
| 회사 HWPX 템플릿 있음 | 템플릿에 콘텐츠 주입 | HWPX (회사 양식 100%) |
| 회사 HWPX 템플릿 없음 + 과거 제안서 있음 | 과거 제안서에서 양식 추출 → 기본 템플릿에 적용 | HWPX (추출 양식) |
| 아무것도 없음 (신규 가입) | `_default/` Kira 기본 템플릿 사용 | HWPX (Kira 표준) |
| DOCX 선호 명시 | 기존 document_assembler 경로 | DOCX |

### API 파라미터

```python
# POST /api/generate-proposal-v2
{
    "rfx_result": { ... },
    "output_format": "hwpx",      # "hwpx" | "docx" (기본: "hwpx")
    "company_id": "comp_abc123",   # 프로필 조회용
    "template_id": null            # null이면 자동 선택
}
```

---

## 9. 구현 로드맵

### Phase A: 프로필 시스템 (profile.md 생성/관리)

```
A-1: company_profile_builder.py
     - company_analyzer 결과 → profile.md 마크다운 변환
     - 과거 제안서(HWPX) 텍스트 추출 → 문체/강점/전략 분석
     - 평가항목별 전략 섹션 자동 생성

A-2: profile.md CRUD API (main.py)
     - GET /api/company/{id}/profile — 프로필 조회
     - POST /api/company/{id}/profile — 프로필 생성 (과거 제안서 업로드)
     - PUT /api/company/{id}/profile — 프로필 수정
     - DELETE /api/company/{id}/profile — 프로필 삭제

A-3: section_writer.py 5계층 프롬프트 확장
     - profile.md 내용을 system prompt에 주입
     - 평가항목별 전략을 섹션 생성 시 참조
```

### Phase A 완료 데모 시나리오

```
1. 과거 제안서 3건 업로드 (HWPX)
2. → hwpx_parser 텍스트 추출 → company_analyzer 분석 → profile.md 자동 생성 (30초)
3. → "이 스타일로 이해했습니다" 확인 화면 (profile.md 요약 표시)
4. 새 RFP 업로드 → 분석 → GO 판정
5. → "제안서 초안 생성" 클릭
6. → profile.md 반영된 DOCX 출력 (문체/강점/전략이 회사 맞춤)
     ※ Phase A에서는 아직 HWPX 주입 없이 DOCX 출력. HWPX는 Phase B에서.
7. 사용자: "기술이해도 섹션 톤이 좀 딱딱해" → 수정 후 피드백
8. → 수정 기록 저장 (Phase C에서 profile.md 자동 업데이트로 연결)

검증 포인트:
- profile.md에 회사 문체/강점/전략이 정확히 추출되는가?
- section_writer가 profile.md 내용을 실제 반영하여 생성하는가?
- 동일 RFP에 대해 profile 있는 회사 vs 없는 회사의 출력이 다른가?
```

### Phase B: HWPX 엔진 (읽기/쓰기)

```
B-1: hwpx_parser.py
     - HWPX ZIP 해제 → section*.xml 파싱
     - 스타일 추출 (폰트, 여백, 줄간격, 표 스타일)
     - 구조 분석 (섹션 목록, 머리글/꼬리글, 표지)
     - 텍스트 추출 (기존 hwp_parser.py 확장)

B-2: hwpx_injector.py
     - HWPX 템플릿의 {{placeholder}} 또는 섹션 마커 인식
     - 마크다운 → HWPX XML 변환 (hp:p + hp:run 생성)
     - 변환 매핑 규칙은 구현 계획서 참조:
       docs/plans/2026-03-01-hwpx-company-skill-impl-plan.md (Task B-2)
     - 표, 불렛, 볼드/이탤릭 등 서식 보존
     - 이미지 삽입 (간트차트 등)

B-3: HWPX 템플릿 자동 분석 → profile.md 보강
     - 업로드된 HWPX에서 스타일 정보 자동 추출
     - profile.md "문서 스타일" + "HWPX 생성 규칙" 섹션 자동 채움
     - "이 스타일로 이해했습니다" 확인 UX

B-4: proposal_orchestrator.py HWPX 출력 경로 추가
     - output_format 분기 (hwpx/docx)
     - _default/ 템플릿 폴백 로직
```

### Phase C: 학습 루프 + 버전 관리

```
C-1: company_profile_updater.py
     - diff_tracker 결과 → profile.md 섹션별 업데이트
     - 3회 이상 반복 패턴만 반영 (auto_learner 임계값)

C-2: profile_history/ 버전 관리
     - 업데이트 시 이전 버전 자동 보관
     - changelog.json: 변경 사유 + 이후 수정률 KPI 기록
     - 수정률 악화 시 롤백 제안

C-3: auto_learner 확장
     - doc_type="hwpx" 지원
     - profile.md 업데이트 트리거 연결
```

### 로드맵 (향후)

```
Phase 2: 제안서 셀프 평가 시뮬레이터
     - profile.md + Layer 1 "평가위원 심리" 지식 결합
     - 평가위원 시뮬레이션 → 항목별 점수 + 감점 리스크 + 수정 제안
     - 제출 전 품질 보증

Phase 3+: 템플릿 마켓플레이스
     - 회사 양식 익명화 → 업종별 공유
     - "IT 용역 기술제안서 (평균 낙찰률 38%)" 형태로 추천
     - 신규 가입 회사 onboarding 가속
```

---

## 10. 비즈니스 가치

| 가치 | 설명 |
|---|---|
| **양식 보존** | 공공조달에서 회사 고유 양식이 평가에 직접 영향 → 경쟁력 |
| **전략 축적** | "이기는 패턴"이 profile.md에 쌓임 → 시간이 갈수록 품질 향상 |
| **학습 lock-in** | 사용할수록 회사 맞춤도 향상 → 이탈 비용 증가 |
| **진입 장벽 제거** | 템플릿 없어도 Kira 기본 템플릿으로 즉시 시작 |
| **차별화** | 타 AI 제안서 도구는 범용 출력 → Kira는 회사 DNA 반영 |
| **셀프 평가** | 제출 전 품질 보증 → 낙찰률 직접 향상 (Phase 2) |

---

## 11. 수정 파일 예상

| 파일 | Phase | 변경 |
|---|---|---|
| `company_profile_builder.py` (신규) | A | profile.md 자동 생성 |
| `section_writer.py` | A | 5계층 프롬프트 (Profile 계층 추가) |
| `main.py` | A,B | 프로필 CRUD + HWPX API |
| `hwpx_parser.py` (신규) | B | HWPX 읽기 + 구조/스타일 분석 |
| `hwpx_injector.py` (신규) | B | HWPX 콘텐츠 주입 |
| `proposal_orchestrator.py` | B | HWPX 출력 경로 분기 |
| `company_profile_updater.py` (신규) | C | diff → profile.md 업데이트 |
| `auto_learner.py` | C | doc_type="hwpx" + 트리거 |
| 테스트 ~10개 파일 | A-C | 각 Phase별 테스트 |
