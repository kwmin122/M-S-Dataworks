# Kira Bot - 전체 특징 및 기능 목록

> AI 공공조달 입찰 자동화 플랫폼 | MS Solutions
> 최종 업데이트: 2026-03-20

---

## 1. 플랫폼 개요

**Kira Bot**은 공공조달 입찰의 전 과정을 AI로 자동화하는 B2B SaaS 플랫폼입니다.

- **비전**: 공고 발견 → RFP 분석 → GO/NO-GO 판단 → 입찰 문서 생성 → 검토 → 학습까지 입찰 라이프사이클 완전 자동화
- **핵심 차별화**: 3계층 AI 학습 모델 (전문 지식 + 회사 맞춤 + 승패 분석)
- **제품 구조**: Chat Hub (탐색) + Bid Studio (정식 생산) + Settings (회사 관리)

---

## 2. 3계층 AI 학습 모델

### Layer 1: 전문가 지식 (495+ 유닛)
- 공공조달 전문가 블로그 47건 크롤링 및 지식 추출
- 유튜브 강의 40건 분석 및 구조화
- 정부 공식 문서 18건 파싱 및 분류
- 7개 카테고리: 전략, 구조, 표현, 평가, 사례, 위험, 팁
- ChromaDB 벡터 DB 영구 저장 + 의미 기반 검색
- Knowledge Harvester: LLM Pass 1 지식 추출
- Knowledge Deduplicator: LLM Pass 2 충돌 해소 (AGREE/CONDITIONAL/CONFLICT)

### Layer 2: 회사 맞춤 학습
- CompanyDB: 회사별 실적/인력/자격/강점 구조화 저장
- Company Analyzer: 과거 제안서 문체, 구조, 표현 패턴 자동 분석
- Auto Learner: 편집 Diff 자동 추적 → 3회+ 반복 패턴 자동 학습
- Diff Tracker: 원본 vs 수정본 섹션별 차이 계산 + 편집률 산출
- 영속성: 서버 재시작 시 학습 상태 자동 복원 (lifespan load/save)
- 멀티테넌시: 조직별 회사 DB 완전 격리 (data/company_db/{company_id}/)

### Layer 3: 승패 분석 (예정)
- 낙찰/탈락 이력 DB 구축
- 평가 항목별 점수 상관관계 분석
- 승률 예측 모델

---

## 3. Chat Hub (대화형 탐색)

### 3.1 공고 검색
- 나라장터 공공데이터포털 API 실시간 연동
- 5개 카테고리 검색: 용역, 물품, 공사, 외자, 기타
- 필터: 키워드, 업무구분, 지역, 금액 범위, 기간
- 검색 결과 카드형 UI (제목, 기관, 마감일, 예산)
- 검색 결과 CSV 다운로드
- 공고 상세 정보 패널 (메타데이터, 평가항목, 자격요건)

### 3.2 RFP 분석
- 다중 포맷 지원: PDF, DOCX, HWP, HWPX, TXT, CSV, XLSX, PPT
- 멀티패스 자격요건 추출 (rfx_analyzer)
  - 필수/권장 자격 분류
  - 정량 제약 추출 (금액, 건수, 인원, 기간)
  - 17개 카테고리 동의어 사전 프롬프트 주입 (사업비↔예산↔추정가격 등)
- 평가기준 추출 (기술평가, 가격평가, 배점)
- 필수 서류 추출 (제출 문서 목록, 형식 힌트, 마감일)
- 특이사항 추출 (특수 조건, 주의사항)
- RFP 요약 리포트: 사업개요/핵심요건/평가기준 3섹션 GFM 마크다운
- 분석 결과 2탭 UI: "RFP 요약" + "GO/NO-GO 분석"

### 3.3 GO/NO-GO 판단
- ConstraintEvaluator: 결정론적 규칙 우선 비교 (수치, 기간, 건수)
- LLM 보완 판단: FALLBACK_NEEDED 항목만 AI가 판단
- 항목별 충족도 퍼센트 표시
- 근거 텍스트 인용 (회사 문서에서 추출)
- 요건 병렬 매칭 (ThreadPoolExecutor, max 6)

### 3.4 첨부파일 자동 처리
- 나라장터 e발주 첨부파일 자동 다운로드
- inqryDiv=2 (공고번호 기준) API 호출
- 자동 파싱 → GO/NO-GO 분석 연결
- 없는 경우 수동 업로드 폴백 UI

### 3.5 문서 기반 Q&A
- RAG 하이브리드 검색 (BM25 + ChromaDB 벡터, RRF 결합)
- BM25 rebuild threading.Lock 보호 (스레드 안전)
- 참조 페이지 번호 표시
- 인텐트 분류 (chat_router): 질문 유형 자동 판별 + 오프토픽 차단

### 3.6 일괄 공고 평가
- 최대 50개 공고 동시 GO/NO-GO 판정
- asyncio.Semaphore(3) + asyncio.gather() 병렬 처리
- 결과 요약 테이블 제공

### 3.7 Chat UI 구조
- ChatLayout: Sidebar + ChatArea + ContextPanel (3컬럼)
- Sidebar: 대화 목록, 새 대화, 이름 변경/삭제
- MessageList: 7종 메시지 타입 렌더링
  - text: 마크다운 (react-markdown + remark-gfm)
  - button_choice: 액션 버튼
  - bid_card_list: 공고 카드 목록
  - analysis_result: 구조화된 분석 결과
  - inline_form: 인라인 입력 폼
  - file_upload: 파일 업로드
  - status: 진행 상태 알림
- ContextPanel: 문서 뷰어 (PDF iframe + 비PDF 다운로드), 리사이즈 280~600px
- 대화 FSM: greeting → bid_search → analyzing → doc_chat

---

## 4. Bid Studio (입찰 문서 생성 워크스페이스)

### 4.1 Stage 1: RFP 분석
- 공고 문서 업로드 또는 텍스트 직접 입력
- Chat에서 분석 완료된 내용 → Studio 자동 전환 (handoff-from-chat)
- RFP 텍스트 AI 분석 (자격요건, 평가항목, 제출서류, 특이사항)

### 4.2 Stage 2: 패키지 분류
- AI 패키지 분류기 (package_classifier.py)
  - 키워드 스코어링 기반 도메인 분류 (IT, 건설, 용역 등)
  - 수의계약/견적 자동 감지 (11개 키워드 하드가드)
  - 발표평가 증거 게이트 (12개 키워드)
  - 신뢰도(confidence) 산출: < 65% 시 수동 검토 권장
  - 18건 회귀 테스트 코퍼스 품질 보장
- 필요 서류 4분류: 생성 문서 / 증빙 문서 / 행정 문서 / 가격 문서
- 서류별 상태 관리: 대기/진행중/완료/불필요
- 증빙자료 첨부 (14종 확장자 허용, 50MB 제한)
- 패키지 완성도 진행률 표시

### 4.3 Stage 3: 회사 정보 연결
- 회사 DB에서 관련 실적/인력 자동 매칭
- 프로젝트별 회사 자산 추가/제거
- Staging → Promote 2단계 (프로젝트 검증 → 공유 DB 승격)
- 프로젝트별 통합 회사 정보 조회 (company-merged)

### 4.4 Stage 4: 스타일 설정
- 스타일 기술서 생성 (회사 문체 + 구조 + 표현 패턴)
- Pin(고정): 선택한 스타일을 모든 생성에 적용
- Derive(파생): 기존 스타일에서 프로젝트 맞춤 변형
- Promote: 스타일을 공유 DB로 승격

### 4.5 Stage 5: 문서 생성
- 4종 문서 타입 선택: proposal / execution_plan / track_record / presentation
- 생성 전 계약(contract) 확인 UI
- 생성 진행 상태 실시간 표시
- 리비전 미리보기:
  - 제안서: 섹션 아코디언
  - 실적기술서: TrackRecordPreview (표 + 서술)
  - 발표자료: PresentationPreview (슬라이드 + QnA)

### 4.6 Stage 6: 검토/편집
- 섹션별 인라인 편집
- 원본 vs 수정본 Diff 시각적 비교
- 편집 후 DOCX 재조립

### 4.7 Stage 7: 학습 반영
- 편집 Diff → 스타일 파생(derive) → 재고정(repin) → 재생성
- Auto Learner: 반복 패턴 자동 학습
- 사용할수록 정확해지는 AI

---

## 5. 문서 자동 생성 (4종)

### 5.1 제안서 (Proposal DOCX)
- RFP 분석 → 섹션 아웃라인 자동 설계 (배점 비례 페이지 배분)
- Layer 1(전문 지식 495+유닛) + Layer 2(회사 맞춤) 결합 섹션 작성
- 품질 검사:
  - 블라인드 위반 감지 (한글 조사 인식 정규식)
  - 모호 표현 경고
  - 섹션 간 문체 일관성 검사
- 마크다운 → DOCX 자동 변환 (mistune 3.x AST 기반)
- Pydantic 입력 검증 (RfxResultInput: title 필수, total_pages 10~200)
- 섹션별 편집 → DOCX 재조립 → Diff 학습

### 5.2 수행계획서/WBS (XLSX + 간트차트 + DOCX)
- 방법론 자동 감지 (Waterfall, Agile, 하이브리드 등)
- LLM WBS 태스크 생성 + Layer 1 지식 주입
- 3시트 Excel 출력: 개요, WBS 테이블, 일정표 (openpyxl)
- 간트차트 PNG 시각화 (matplotlib)
- 수행계획서 DOCX 자동 생성

### 5.3 발표자료 (PPTX)
- KRDS 공공기관 PPT 디자인 가이드 자동 적용
- 6종 슬라이드 템플릿: 표지(A), 목차(B), 콘텐츠(C), 데이터(D), 마무리(E), 간지(F)
- 디자인 토큰: Blue 900 #003764 주색, Gray 700 #444444 본문
- Pretendard 폰트 (표지 40pt ExtraBold, 제목 26pt Bold, 본문 15pt Regular)
- 16:9 레이아웃 (1920x1080), 상단 제목바 48px + 중앙 콘텐츠 + 하단 푸터 28px
- 예상 질문 & 답변 10개 자동 생성 (ppt_slide_planner)
- 제안서 → 슬라이드 콘텐츠 자동 추출 (ppt_content_extractor)
- 다중 입력: RFP + 제안서 섹션 + 수행계획 태스크 + 회사 정보 + 스타일

### 5.4 실적/경력 기술서 (DOCX)
- RFP 요구사항 ↔ CompanyDB 과거 실적 자동 매칭
- 투입 인력 자동 배치 (경력, 자격증 기반)
- Layer 1 지식 주입으로 서술 품질 강화
- 실적 기술서 DOCX: 표 + 서술 형식 자동 조립

---

## 6. 회사 정보 관리

### 6.1 회사 프로필
- WYSIWYG 마크다운 편집기 (DocumentWorkspace)
- 버전 히스토리 + 이전 버전 롤백
- 자동 파싱: 업로드 문서에서 AI가 프로필 자동 추출

### 6.2 실적 DB
- CRUD: 프로젝트명, 발주처, 수행 기간, 금액, 기술 스택, 주요 성과
- AI 자동 매칭: 입찰 공고 요건과 관련 실적 자동 연결
- 다중 테넌트 격리

### 6.3 인력 DB
- CRUD: 이름, 직급, 경력(년), 자격증, 전문 분야
- 실적기술서 생성 시 최적 인력 자동 배치

### 6.4 문서 관리
- 일괄 업로드: PDF, DOCX, HWP 드래그앤드롭
- AI 자동 파싱 → CompanyDB 반영
- 정규화된 회사 ID (canonical-id): URL 인코딩 적용, 서버 단일 source of truth

### 6.5 온보딩 플로우
- 회사 정보 온보딩 모달 (CompanyOnboardingModal)
- 첫 로그인 시 자동 조직 프로비저닝
- 단계별 가이드: 회사명 → 실적 → 인력 → 문서 업로드

---

## 7. 알림 시스템

### 7.1 맞춤 공고 알림
- 키워드 기반 매칭 필터
- 업무구분, 지역, 발주품목 필터
- 금액 범위 필터
- 제외 키워드/지역 필터
- 물품분류번호, 세부품명 메타데이터 필터

### 7.2 알림 스케줄
- 실시간 알림
- 일일 요약 알림
- 정시 알림 (사용자 설정 시간)
- 조용한 시간 설정 (야간/주말 음소거)

### 7.3 알림 채널
- 이메일 (Brevo SMTP)
- 알림 미리보기: 설정 전 매칭 공고 사전 확인

---

## 8. 대시보드 & 분석

### 8.1 사용 현황
- 월별 분석 횟수 추적
- 월별 문서 생성 횟수
- 월별 다운로드 횟수

### 8.2 Smart Fit Score
- 회사-공고 적합도 점수 산출
- 부족한 자격요건 하이라이트

### 8.3 발주 예측
- 인기 기관 TOP 10
- 기관별 월별 발주량 추세 그래프
- 평균 규모, 주요 분야 분석

---

## 9. 랜딩 페이지 & UI

### 9.1 랜딩 페이지
- Hero 섹션: 3D 애니메이션 배경 (Spline) + 메인 CTA
- Product Hub: 4가지 주요 기능 카드
- How It Works: 3단계 플로우 (검색 → 분석 → 생성)
- Features: 3계층 학습 모델 설명
- Solutions: 산업별/규모별 솔루션
- Pricing: FREE / PRO / ENTERPRISE
- Legal: 개인정보처리방침, 이용약관

### 9.2 인증
- Google OAuth 로그인
- 카카오 로그인
- 안전한 세션 관리 (HttpOnly 쿠키)

### 9.3 Feature Flags
- `VITE_STUDIO_VISIBLE`: Studio UI 노출 제어
- `VITE_CHAT_GENERATION_CUTOVER`: Chat→Studio 전환 제어
- 빌드 타임 변수 (Dockerfile ARG)

---

## 10. 보안

### 10.1 인증 & 접근 제어
- Google/카카오 OAuth 소셜 로그인
- Supabase JWT → HttpOnly 쿠키 세션 (auth_gateway)
- 프로젝트별 5단계 ACL: viewer, reviewer, approver, editor, owner
- 조직 역할 bypass: org owner/admin은 전체 프로젝트 접근
- 자동 조직 프로비저닝: 첫 로그인 시 자동 생성

### 10.2 데이터 보호
- SSRF 방어: safeFetch (HTTPS only, DNS 사전 해석, 사설 IP 차단, redirect:manual, 10초 타임아웃)
- CSRF 방어: verifyCsrfOrigin (Origin allowlist, POST/PUT/PATCH/DELETE)
- HMAC 웹훅 서명: ${ts}.${nonce}.${rawBody} 서명, 리플레이 방지
- IDOR 방어: organizationId를 세션에서 주입 (getServerSession)
- 파일 업로드 보안: 확장자 화이트리스트(14종), 50MB 제한, 경로 순회 방어 (os.path.realpath)
- 파일명 sanitization: 화이트리스트 정규식 + 100자 제한

### 10.3 API 보안
- Rate Limiting: SlowAPIMiddleware (IP당 60요청/분)
- CORS: 정확한 도메인 정규식 pinning
- Nonce 중복 방지: UsedNonce create-only + P2002 catch
- 내부 API HMAC: verifyInternalAuth (ts/nonce/sig)

### 10.4 운영 보안
- 환경변수 zod 검증 (getEnv): 누락 시 부팅 차단
- 감사 로그: 모든 주요 액션 기록 (AuditLog 테이블)
- PGTZ=UTC 강제

---

## 11. 인프라 & 배포

### 11.1 기술 스택
- **프론트엔드**: React 19 + TypeScript + Vite + Tailwind CSS
- **백엔드 (Chat)**: Python FastAPI (비동기, uvicorn)
- **백엔드 (Studio)**: Python FastAPI + SQLAlchemy (async) + PostgreSQL
- **백엔드 (SaaS)**: Next.js 16 + Prisma 5 + TypeScript
- **AI 엔진**: OpenAI GPT-4 + ChromaDB 벡터 DB
- **RAG Engine**: FastAPI 0.115 (포트 8001)
- **데이터베이스**: PostgreSQL (Docker) + pgvector
- **ORM**: SQLAlchemy (async) + Prisma 5

### 11.2 배포
- Docker 멀티스테이지 빌드 (Node frontend → Python runtime)
- Railway 클라우드 자동 배포 (CI/CD)
- Feature Flags: 빌드 타임 Dockerfile ARG

### 11.3 테스트
- Python pytest: 500+ 테스트 (레거시 + rag_engine + Studio)
- Jest: 109+ 프론트엔드 테스트
- 패키지 분류기 회귀 코퍼스: 18건 parametrized
- E2E 검증 스크립트

### 11.4 성능
- 병렬 처리: ThreadPoolExecutor (청크 max 4, 요건 매칭 max 6)
- 비동기: asyncio.to_thread() 이벤트 루프 비차단
- LLM 안정성: call_with_retry() (60초 타임아웃 + 2회 재시도, 지수 백오프)
- 캐싱: 회사 DB 인스턴스 캐싱 (_company_db_cache)

---

## 12. 요금제

| 기능 | FREE | PRO (99,000원/월) | ENTERPRISE |
|------|------|-------------------|------------|
| 공고 검색 | O | O | O |
| RFP 분석 | 월 5건 | 무제한 | 무제한 |
| GO/NO-GO 판단 | - | O | O |
| 제안서 생성 | - | O | O |
| PPT 생성 | - | O | O |
| WBS 생성 | - | O | O |
| 실적기술서 생성 | - | O | O |
| 맞춤 알림 | - | O | O |
| 채팅 | 일 20회 | 무제한 | 무제한 |
| 전담 학습 모델 | - | - | O |
| 온프레미스 배포 | - | - | O |
| SLA + 전담 지원 | - | - | O |

---

## 13. 지원 포맷

### 입력 (Input)
| 포맷 | 용도 |
|------|------|
| PDF | RFP, 회사 문서, 첨부파일 |
| DOCX | RFP, 회사소개서, 과거 제안서 |
| HWP | 한컴오피스 문서 (magic bytes 감지) |
| HWPX | 한컴 XML 포맷 (ZIP+XML 네임스페이스 파싱) |
| TXT | 텍스트 RFP, 메모 |
| CSV | 데이터 파일 |
| XLSX | 엑셀 데이터 |
| PPT/PPTX | 프레젠테이션 파일 |

### 출력 (Output)
| 포맷 | 용도 |
|------|------|
| DOCX | 제안서, 수행계획서, 실적기술서 |
| PPTX | 발표자료 |
| XLSX | WBS 테이블 |
| PNG | 간트차트 |
| JSON | 체크리스트, 분석 결과 |
| CSV | 검색 결과 |

---

## 14. API 엔드포인트 전체 목록

### 인증 (6개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/auth/google/login | Google 로그인 URL |
| POST | /api/auth/google/callback | Google 콜백 |
| POST | /api/auth/kakao/login | 카카오 로그인 URL |
| POST | /api/auth/kakao/callback | 카카오 콜백 |
| GET | /api/auth/me | 현재 사용자 |
| POST | /api/auth/logout | 로그아웃 |

### 세션 (3개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/session | 세션 생성 |
| POST | /api/session/check | 세션 확인 |
| POST | /api/session/stats | 사용량 조회 |

### 공고 검색 & 분석 (8개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/bids/search | 공고 검색 |
| GET | /api/bid-attachments/{bid_ntce_no} | 첨부파일 목록 |
| GET | /api/file/{session_id}/{bucket}/{filename} | 파일 다운로드 |
| GET | /api/file-text/{session_id}/{bucket}/{filename} | 텍스트 미리보기 |
| POST | /api/analyze | RFP 문서 분석 |
| POST | /api/analyze-text | 텍스트 RFP 분석 |
| POST | /api/analyze/bid | 공고 직접 분석 |
| POST | /api/bids/evaluate-batch | 일괄 평가 |

### 회사 DB (12개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | /api/company-db/profile | 프로필 조회 |
| POST | /api/company-db/profile | 프로필 업데이트 |
| GET | /api/company-db/stats | 통계 조회 |
| GET | /api/company-db/canonical-id | 정규화 ID |
| POST | /api/company-db/track-record | 실적 추가 |
| GET | /api/company-db/track-records | 실적 목록 |
| POST | /api/company-db/personnel | 인력 추가 |
| GET | /api/company-db/personnel | 인력 목록 |
| DELETE | /api/company-db/item/{doc_id} | 항목 삭제 |
| POST | /api/company-db/profile/markdown | 프로필 마크다운 |
| PUT | /api/company-db/profile/section | 섹션 업데이트 |
| GET | /api/company-db/profile/history | 수정 히스토리 |

### 회사 문서 (6개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/company/documents/upload | 문서 업로드 |
| POST | /api/company/documents/text | 텍스트 입력 |
| GET | /api/company/documents | 문서 목록 |
| DELETE | /api/company/documents | 문서 삭제 |
| POST | /api/company/documents/clear | 전체 삭제 |
| POST | /api/company-db/profile/rollback | 버전 롤백 |

### 채팅 (3개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/chat | 문서 기반 채팅 |
| POST | /api/general-chat | 일반 채팅 |
| POST | /api/rematch-with-company | 재분석 |

### 문서 생성 Legacy (4개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/proposal/generate | 제안서 생성 |
| POST | /api/wbs/generate | WBS 생성 |
| POST | /api/ppt/generate | PPT 생성 |
| POST | /api/track-record/generate | 실적기술서 생성 |

### 제안서 편집 (4개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | /api/proposal/sections/{filename} | 섹션 조회 |
| PUT | /api/proposal/section/{filename} | 섹션 수정 |
| POST | /api/proposal/reassemble/{filename} | DOCX 재조립 |
| GET | /api/proposal/download/{filename} | 다운로드 |

### Studio (25+ 개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/studio/projects | 프로젝트 생성 |
| GET | /api/studio/projects | 프로젝트 목록 |
| GET | /api/studio/projects/{id} | 프로젝트 상세 |
| PATCH | /api/studio/projects/{id}/stage | 스테이지 변경 |
| POST | /api/studio/handoff-from-chat | Chat→Studio 전환 |
| POST | /api/studio/projects/{id}/analyze | RFP 분석 |
| POST | /api/studio/projects/{id}/classify | 패키지 분류 |
| GET | /api/studio/projects/{id}/package-items | 서류 목록 |
| PATCH | /api/studio/projects/{id}/package-items/{item}/status | 서류 상태 |
| POST | /api/studio/projects/{id}/package-items/{item}/evidence | 증빙 첨부 |
| GET | /api/studio/projects/{id}/package-completeness | 완성도 |
| GET | /api/studio/projects/{id}/package-items/{item}/evidence/download | 증빙 다운로드 |
| POST | /api/studio/projects/{id}/company-assets | 회사자산 추가 |
| GET | /api/studio/projects/{id}/company-assets | 회사자산 목록 |
| POST | /api/studio/projects/{id}/company-assets/{asset}/promote | 자산 승격 |
| GET | /api/studio/projects/{id}/company-merged | 통합 회사정보 |
| POST | /api/studio/projects/{id}/style-skills | 스타일 생성 |
| GET | /api/studio/projects/{id}/style-skills | 스타일 목록 |
| POST | /api/studio/projects/{id}/style-skills/{skill}/pin | 스타일 고정 |
| DELETE | /api/studio/projects/{id}/style-skills/pin | 고정 해제 |
| POST | /api/studio/projects/{id}/style-skills/{skill}/derive | 스타일 파생 |
| POST | /api/studio/projects/{id}/style-skills/{skill}/promote | 스타일 승격 |
| POST | /api/studio/projects/{id}/generate | 문서 생성 |
| GET | /api/studio/projects/{id}/documents/{type}/current | 현재 리비전 |
| POST | /api/studio/projects/{id}/documents/proposal/edited | 편집 저장 |
| GET | /api/studio/projects/{id}/documents/proposal/diff | Diff 조회 |
| GET | /api/studio/projects/{id}/documents/presentation/download | PPT 다운로드 |
| POST | /api/studio/projects/{id}/relearn | 학습 반영 |

### 알림 (5개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/alert/save | 알림 저장 |
| GET | /api/alert/config | 설정 조회 |
| DELETE | /api/alert/delete | 설정 삭제 |
| GET | /api/alert/preview | 미리보기 |
| POST | /api/admin/alert/send | 즉시 발송 |

### 대시보드 (4개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/dashboard/summary | 사용 현황 |
| POST | /api/dashboard/smart-fit-score | Smart Fit |
| GET | /api/forecast/popular-agencies | 인기 기관 |
| GET | /api/forecast/org/{org_name} | 발주 예측 |

### RAG Engine (8개)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | /api/analyze-bid | 입찰 분석 |
| POST | /api/generate-proposal | 제안서 v1 |
| POST | /api/generate-proposal-v2 | 제안서 v2 (A-lite) |
| POST | /api/generate-wbs | WBS 생성 |
| POST | /api/generate-ppt | PPT 생성 |
| POST | /api/generate-track-record | 실적기술서 |
| POST | /api/checklist | 체크리스트 |
| POST | /api/edit-feedback | 편집 피드백 |

**총 API 엔드포인트: 88개+**

---

## 15. 핵심 수치 요약

| 지표 | 값 |
|------|-----|
| AI 학습 지식 유닛 | 495+ |
| 자동화 워크플로우 단계 | 7단계 |
| 자동 생성 문서 종류 | 4종 (DOCX, PPTX, XLSX, PNG) |
| 지원 입력 포맷 | 8종 |
| 지원 출력 포맷 | 6종 |
| API 엔드포인트 | 88+ |
| 자동화 테스트 | 500+ |
| 분류기 회귀 테스트 | 18건 |
| 동의어 사전 카테고리 | 17개 |
| 보안 레이어 | 10+ (ACL, HMAC, CSRF, SSRF, Rate Limit 등) |
| ACL 레벨 | 5단계 |
| 슬라이드 템플릿 | 6종 |

---

*MS Solutions | Kira Bot | 2026*
