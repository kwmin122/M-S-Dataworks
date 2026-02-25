# 제조 AX 플랫폼 설계 (M&S Factory AI)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create implementation plan from this design.

**Goal:** M&S Solutions의 공공조달 AI(KiraBot)를 제조업 공급사/협력업체로 확장. 핵심 엔진(parser, RAG, analyzer, matcher)을 공용 core로 추출하고, 제조업 특화 서비스를 별도 프로젝트로 구축.

**Target:** 대기업 발주에 대응하는 중소 제조 공급사 (조달/영업/품질팀)

**Brand:** M&S Solutions (동일 브랜드, 별도 제품)

---

## 아키텍처

### 모노레포 내 새 프로젝트 + 공용 core 추출

```
MS_SOLUTIONS/
├── core/                          ← 공용 Python 패키지
│   ├── __init__.py
│   ├── document_parser.py         ← 기존 파일 이동 (format-agnostic)
│   ├── engine.py                  ← RAG 엔진 (ChromaDB + BM25 hybrid)
│   ├── spec_analyzer.py           ← rfx_analyzer.py에서 일반화
│   ├── capability_matcher.py      ← matcher.py에서 일반화
│   └── text_chunker.py
│
├── services/web_app/              ← KiraBot 백엔드 (import 경로 변경만)
├── frontend/kirabot/              ← KiraBot 프론트 (변경 없음)
│
├── services/factory_ai/           ← 제조 AX 백엔드 (FastAPI, 포트 8002)
│   ├── main.py
│   ├── email_collector.py         ← IMAP 수집 + 첨부파일 파싱
│   ├── mtc_verifier.py            ← 밀시트/성적서 검증 엔진
│   ├── quote_generator.py         ← 견적서 초안 생성
│   ├── cert_gap_analyzer.py       ← ISO/IATF 갭 분석
│   └── manufacturing_prompts.py   ← 제조업 특화 프롬프트
│
└── frontend/factory-ai/           ← 제조 AX 프론트 (React 19 + Vite)
    ├── App.tsx
    ├── components/chat/           ← kirabot 구조 재활용 + 도메인 수정
    └── components/landing/        ← 제조업 랜딩페이지
```

### 설계 원칙

- KiraBot 코드는 `import` 경로 변경 외 기능 변경 없음
- `core/`는 도메인 무관한 순수 라이브러리 (RFx/제조 양쪽에서 import)
- 각 서비스 독립 배포 가능
- 인증/결제 인프라는 나중에 공유 가능 (같은 브랜드)

---

## 기능 목록 (6개, 전체 구현)

### Feature 1: 수주 가능성 AI 판단 (GO/NO-GO for Manufacturing)

KiraBot의 핵심 기능을 제조업에 1:1 매핑.

**Flow:**
```
발주 사양서 업로드 (이메일/수동)
  → core/spec_analyzer: 요건 추출 (소재, 공차, 수량, 납기, 인증, 표면처리)
  → core/capability_matcher: 자사 역량 매칭 (설비, 인증, 과거 실적)
  → 결과: "수주 가능 / 조건부 / 불가" + 부족한 역량 가이드
```

**제조업 Constraint Types:**

| Metric | 예시 | 비고 |
|---|---|---|
| UNIT_PRICE | 단가 ≤ 5,000원 | KiraBot의 CONTRACT_AMOUNT 대응 |
| ORDER_QUANTITY | 수량 ≥ 10,000개 | — |
| PRODUCTION_CAPACITY | 월 생산능력 ≥ 50,000개 | KiraBot의 HEADCOUNT 대응 |
| CERTIFICATION | ISO 9001, IATF 16949 | KiraBot의 CERT_GRADE 대응 |
| LEAD_TIME | 납기 ≤ 30일 | KiraBot의 PERIOD_YEARS 대응 |
| MATERIAL_SPEC | SUS304, AL6061 | 신규 |
| TOLERANCE | ±0.05mm | 신규 |
| DEFECT_RATE | 불량률 ≤ 0.5% | 신규 |
| SURFACE_FINISH | Ra 1.6 이하 | 신규 |

**차별점:** 기존 CPQ 솔루션(Tacton, Logik.ai)은 구매자 관점(가격 최적화). 우리는 공급자 관점(수주 가능성 판단) — 경쟁 제품이 거의 없는 블루오션.

---

### Feature 2: 밀시트/성적서 자동 검증 (MTC Compliance Checker)

**Flow:**
```
자재 입고 시 밀시트 PDF 업로드
  → AI가 화학 성분, 기계적 성질, 열처리 조건 추출
  → 주문 사양서의 규격(KS, ASTM, EN) 요건과 자동 대조
  → PASS / FAIL + 부적합 항목 하이라이트
```

**추출 대상:**
- 화학 성분: C, Si, Mn, P, S, Cr, Ni, Mo (%)
- 기계적 성질: 인장강도(MPa), 항복강도(MPa), 연신율(%), 경도(HRC)
- 열처리: 온도, 시간, 냉각방법
- 치수: 외경, 두께, 길이

**규격 매칭:**
- KS D 3698 (냉간압연강판), ASTM A240 (스테인리스), EN 10204 Type 3.1/3.2
- 각 규격의 허용 범위를 constraint로 모델링

**기술:** `rfx_analyzer.py`의 constraint extraction + `matcher.py`의 numeric comparison 재활용.

---

### Feature 3: 문서 RAG Q&A + 유사 제품 검색 (Knowledge Base)

**Flow A — 문서 Q&A:**
```
내부 문서 업로드 (시험성적서, 밀시트, 공정도, 작업표준서)
  → core/engine.py: 벡터DB 인덱싱 (하이브리드 검색)
  → 자연어 질문 → AI 답변 + 출처 페이지 참조
  예: "SUS304 소재 인장강도 시험 결과 알려줘"
  예: "ISO 9001 부적합 시정조치 이력 조회"
```

**Flow B — 유사 제품 검색:**
```
신규 발주 사양 입력
  → 과거 납품 이력에서 가장 유사한 제품 검색 (RAG)
  → 당시 도면, 가공조건, 불량이력, 소요시간 정보 제공
  → "이 제품은 3년 전 현대모비스 납품한 XX와 92% 유사"
```

**기술:** `core/engine.py` 그대로. 메타데이터에 part_number, client, date 추가.

---

### Feature 4: 발주 이메일 자동 감지 (Smart RFQ Inbox)

**Flow:**
```
IMAP 연결 설정 (Gmail/Outlook/회사메일)
  → 5분 주기 폴링
  → AI가 발주/견적 요청 이메일 자동 감지 (키워드 + LLM 분류)
  → 첨부파일 자동 다운로드 + 파싱 (core/document_parser)
  → 핵심 요약: 발주처, 품목, 수량, 납기, 긴급도
  → 대시보드에 신규 RFQ 카드 + 푸시 알림
```

**기술 스택:**
- `imaplib` + `email` (Python stdlib, 외부 의존성 없음)
- 발주 감지 키워드: "견적", "사양서", "RFQ", "발주", "납품", "단가"
- LLM 분류: 일반 이메일 vs 발주 요청 구분 (GPT-4o-mini)
- 알림: Resend 이메일 (KiraBot 알림과 동일 인프라)

**IMAP 보안:** OAuth2 (Gmail) / App Password (Outlook) 지원. 자격증명은 서버사이드 암호화 저장.

---

### Feature 5: AI 견적서 초안 생성 (Quote Draft Generator)

**Flow:**
```
발주 사양서 분석 완료 후
  → 과거 유사 견적 RAG 검색 (가장 비슷한 견적 3건)
  → 원가 항목 초안 생성:
    - 소재비 (소재 단가 × 수량 × 스크랩율)
    - 가공비 (공정별 시간 × 시간당 단가)
    - 외주비 (표면처리, 열처리 등)
    - 관리비 + 이윤
  → 견적서 템플릿 (Excel/PDF) 출력
```

**원가 계산 접근:**
- Phase 1: 과거 유사 견적 참조 + AI가 항목별 초안 제시 (정확한 계산 아님, 참고용)
- Phase 2: 사용자가 원가 테이블 등록 → 규칙 기반 자동 계산 + AI 보정

**기술:** RAG 검색(과거 견적) + LLM 생성(견적 초안) + Excel 템플릿(openpyxl)

---

### Feature 6: ISO/IATF 인증 갭 분석 (Certification Gap Analyzer)

**Flow:**
```
인증 종류 선택 (ISO 9001 / IATF 16949 / AS9100 / ISO 14001)
  → 현재 보유 문서 일괄 업로드 (품질매뉴얼, 절차서, 기록)
  → AI가 해당 표준의 요구사항 체크리스트 생성
  → 보유 문서 vs 요구 문서 갭 매핑
  → 결과: 미비 문서 목록 + 작성 가이드 + 우선순위
```

**인증별 체크리스트:**
- ISO 9001: 10개 항목 (4. 조직의 상황 ~ 10. 개선)
- IATF 16949: ISO 9001 + 자동차 특화 추가 요구사항
- AS9100: ISO 9001 + 항공우주 특화

**기술:** 각 표준의 요구사항을 structured data로 모델링. 업로드된 문서에서 해당 요건을 충족하는 증거를 RAG 검색. `matcher.py`의 MET/NOT_MET/PARTIALLY_MET 체계 그대로 활용.

---

## 공급사 프로필 (Supplier Profile)

```typescript
interface SupplierProfile {
  companyName: string;
  businessType: string;           // 제조업종 (정밀가공, 사출, 프레스...)
  businessNumber: string;
  certifications: string[];       // ISO 9001, IATF 16949, AS9100...
  equipment: string[];            // CNC 5축, 사출기 350톤, SMT...
  productionCapacity: string;     // "월 10만개" / "CNC 8대 24시간 가동"
  materials: string[];            // SUS304, AL6061, PC, ABS...
  leadTimeRange: string;          // "2-4주"
  minOrderQuantity: string;       // "100개"
  keyClients: string[];           // 주요 납품처
  specializations: string[];      // 정밀가공, 판금, PCB, 도금...
  regions: string[];
  employeeCount: number | null;
  annualRevenue: string;
  documents: SupplierDocument[];  // 시험성적서, 밀시트, 인증서...
  aiExtraction: AiExtraction | null;
}
```

KiraBot의 `CompanyProfile`을 확장. 문서 업로드 시 AI 자동 추출은 동일 패턴.

---

## 기술 스택

| 레이어 | 기술 | 비고 |
|---|---|---|
| 공용 코어 | Python 3.12, ChromaDB, OpenAI | `core/` 패키지 |
| 백엔드 | FastAPI (포트 8002) | KiraBot과 동일 패턴 |
| LLM | GPT-4o-mini (기본) / GPT-4o (대용량) | 동일 |
| 이메일 수집 | imaplib + email (stdlib) | 외부 의존성 없음 |
| 프론트엔드 | React 19 + Vite + TypeScript + Tailwind | KiraBot 구조 재활용 |
| 인증 | Google OAuth (공유) | 동일 auth gateway |
| 저장 | JSON 파일 (MVP) → PostgreSQL | KiraBot과 동일 |
| 알림 | Resend (이메일) | KiraBot과 공유 |
| 견적 출력 | openpyxl (Excel) / WeasyPrint (PDF) | — |

---

## Phase 계획

### Phase 1 — Core 추출 + 기본 인프라
- `core/` 패키지 생성 (parser, engine, analyzer, matcher 추출)
- KiraBot import 경로 변경 + 검증
- `services/factory_ai/` FastAPI 스캐폴딩
- `frontend/factory-ai/` React 프로젝트 생성

### Phase 2 — Feature 1: 수주 가능성 판단
- spec_analyzer (제조업 constraint types)
- capability_matcher (공급사 역량 매칭)
- 공급사 프로필 등록 (문서 업로드 + AI 추출)
- 채팅 UI (사양서 업로드 → 분석 → GO/NO-GO)

### Phase 3 — Feature 2: 밀시트/성적서 검증
- MTC 파싱 엔진 (화학 성분, 기계적 성질 추출)
- 규격 데이터베이스 (KS, ASTM, EN 허용 범위)
- 자동 대조 + PASS/FAIL 리포트

### Phase 4 — Feature 3: 문서 RAG Q&A + 유사 제품 검색
- 내부 문서 업로드 + 벡터DB 인덱싱
- 자연어 Q&A 채팅
- 유사 제품 검색 (메타데이터 매칭)

### Phase 5 — Feature 4: 이메일 자동 수집
- IMAP 연결 설정 UI
- 이메일 폴링 + 발주 감지 (키워드 + LLM)
- 첨부파일 자동 파싱 + 알림

### Phase 6 — Feature 5: 견적서 초안 생성
- 과거 견적 RAG 검색
- 원가 항목 초안 LLM 생성
- Excel/PDF 템플릿 출력

### Phase 7 — Feature 6: ISO/IATF 갭 분석
- 인증 표준 체크리스트 데이터
- 문서 vs 요구사항 갭 매핑
- 미비 문서 목록 + 작성 가이드

---

## 경쟁 분석

| 경쟁사 | 관점 | 우리와의 차이 |
|---|---|---|
| Keelvar, LightSource | 구매자 (조달팀) | 우리는 공급자 관점 |
| Tacton CPQ | 구매자 (견적 요청) | 우리는 공급자의 견적 대응 |
| 위슬리 (스텝하우) | 범용 문서 AI | 우리는 제조업 특화 (밀시트, 사양서) |
| 올거나이즈 (Alli) | 범용 엔터프라이즈 AI | 우리는 중소 제조사 특화 |

**핵심 차별점:** "공급자 관점의 수주 AI" — 대기업 발주에 대응하는 중소 제조사를 위한 도구.

---

## 리서치 출처

- [AI-Powered RFQ Automation — SpiralScout](https://spiralscout.com/blog/ai-manufacturing-rfq-automation)
- [Respond to Manufacturing RFQs Faster — Tacton](https://www.tacton.com/cpq-blog/respond-to-rfq-faster/)
- [RFQ Automation Benefits — Iris AI](https://heyiris.ai/blog/rfq-automation-process-benefits-and-best-practices)
- [AI Procurement Platforms — Leverage AI](https://blog.tryleverage.ai/blog/pf/ai-procurement-automation-platforms-manufacturers)
- [Understanding RFQ Process — Inventive AI](https://www.inventive.ai/blog-posts/rfq-process-understanding)
- [ISO 9001 인증 가이드 — Quality Insights](https://www.quality-insights.co.kr/2025/06/quality-iso.html)
- [IATF 16949 체크리스트 — Quality Insights](https://www.quality-insights.co.kr/2025/06/iatf-certifi.html)
- [Mill Test Certificate — HQTS](https://www.hqts.com/material-test-certificate/)
- [위슬리 AI — 스텝하우](https://www.wissly.ai/ko)
- [AX 전환 가이드 — 스마트팩토리아](https://smartfactoria.com/content/ax-%EC%A0%84%ED%99%98-%EC%99%84%EB%B2%BD-%EA%B0%80%EC%9D%B4%EB%93%9C-5%EB%8B%A8%EA%B3%84)
- [AI CPQ Software 2026 — Alguna](https://blog.alguna.com/ai-cpq-software/)
- [정부 870억 제조 AI 투입 — EBN](https://www.ebn.co.kr/news/articleView.html?idxno=1700416)
