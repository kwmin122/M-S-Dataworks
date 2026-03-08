# GDPR Record of Processing Activities (ROPA)

**조직**: Kira Bot / MS-Dataworks
**최종 업데이트**: 2026-03-08
**버전**: 1.0

---

## 1. 처리 목적 (Purpose of Processing)

**주요 목적**:
- 공공조달 입찰 공고 분석
- 자격요건 자동 추출 및 GO/NO-GO 판단
- 제안서 자동 생성 지원
- 입찰 이력 관리

---

## 2. 처리 데이터 범주 (Categories of Personal Data)

### 2.1. 사용자 계정 정보
- 이메일 주소 (Google/Kakao OAuth)
- 사용자 이름
- OAuth provider ID
- 세션 ID

### 2.2. 회사 정보
- 회사명
- 사업자등록번호
- 회사 주소
- 회사 연혁
- 임직원 정보 (이름, 직급)
- 사업 실적

### 2.3. 업로드 문서
- RFP 문서 (PDF/HWP/DOCX)
- 회사 소개서
- 사업 실적 자료
- 인력 현황

### 2.4. 분석 결과
- GO/NO-GO 판단 결과
- 자격요건 매칭 결과
- 생성된 제안서 초안

---

## 3. 데이터 주체 범주 (Categories of Data Subjects)

- 서비스 사용자 (입찰 담당자)
- 회사 대표자
- 회사 임직원 (실적/인력 정보에 포함된 경우)

---

## 4. 수신자 범주 (Categories of Recipients)

### 4.1. 내부 수신자
- 시스템 관리자 (로그 접근)
- 개발팀 (디버깅 목적)

### 4.2. 외부 수신자
- OpenAI (LLM API 호출 시 — 일시적 처리, 30일 후 자동 삭제)
- Google (OAuth 인증)
- Kakao (OAuth 인증)

### 4.3. 제3국 이전
- OpenAI: 미국 (EU-US Data Privacy Framework 준거)
- Google: 미국 (적정성 결정 또는 표준 계약 조항)
- Kakao: 한국 (GDPR 적용 대상 아님)

---

## 5. 처리 기간 (Retention Period)

| 데이터 유형 | 보존 기간 | 근거 |
|------------|----------|------|
| 세션 데이터 | 12시간 | 사용자 편의성 |
| 업로드 문서 | 사용자 삭제 시까지 | 서비스 제공 |
| 분석 결과 | 사용자 삭제 시까지 | 서비스 제공 |
| OAuth 토큰 | 세션 만료 시 즉시 삭제 | 보안 |
| 로그 (일반) | 90일 | 운영 모니터링 |
| 로그 (보안 이벤트) | 1년 | 감사 증적 |

**자동 삭제**:
- 90일간 미접속 사용자 → 전체 데이터 삭제 통보 후 30일 내 삭제

---

## 6. 법적 근거 (Legal Basis)

| 처리 활동 | 법적 근거 (GDPR 제6조) |
|----------|---------------------|
| 사용자 계정 관리 | (b) 계약 이행 |
| 분석 서비스 제공 | (b) 계약 이행 |
| 마케팅 (옵트인) | (a) 동의 |
| 보안 로그 | (f) 정당한 이익 |
| 법적 의무 준수 | (c) 법적 의무 |

---

## 7. 데이터 보안 조치 (Technical and Organizational Measures)

### 7.1. 기술적 조치
- ✅ HTTPS 전송 암호화 (TLS 1.3)
- ✅ 비밀번호 해싱 (bcrypt)
- ✅ 세션 HMAC 서명
- ✅ API Rate Limiting (DDoS 방어)
- ✅ Docker non-root 사용자
- ✅ 보안 헤더 (CSP, X-Frame-Options 등)
- ✅ 입력 검증 (Pydantic 스키마)
- ✅ SSRF 방어 (safeFetch)

### 7.2. 조직적 조치
- 최소 권한 원칙 (Least Privilege)
- 접근 로그 기록
- 정기 보안 감사 (분기별)
- 데이터 처리 약정 (DPA) 체결

### 7.3. 인시던트 대응
- 72시간 내 감독기관 통보
- 24시간 내 사용자 통보 (고위험 시)
- 인시던트 대응 플레이북 준비

---

## 8. 데이터 주체 권리 (Data Subject Rights)

### 8.1. 구현된 권리
- ✅ **열람권** (Right of Access): GET /api/user/profile
- ✅ **정정권** (Right to Rectification): PUT /api/user/profile
- ✅ **삭제권** (Right to Erasure): DELETE /api/user/account
- ✅ **처리 제한권** (Right to Restriction): 계정 비활성화 (향후 구현 예정)
- ✅ **이동권** (Right to Data Portability): GET /api/user/export (JSON)

### 8.2. 요청 처리 기한
- 1개월 이내 (복잡한 경우 2개월 연장 가능)

### 8.3. 연락처
- 이메일: privacy@ms-dataworks.com
- 웹: /privacy-policy

---

## 9. 데이터 보호 영향 평가 (DPIA)

**DPIA 필요 여부**: 🟡 검토 필요

**사유**:
- 대규모 자동화 의사결정 (GO/NO-GO 판단) → DPIA 권장
- LLM 사용 (제3국 이전) → DPIA 권장

**다음 단계**:
- DPIA 초안 작성 (Q2 2026)
- 외부 전문가 검토
- 감독기관 사전 협의 (필요 시)

---

## 10. 데이터 처리자 (Processors)

| 처리자 | 서비스 | 위치 | DPA 체결 |
|-------|-------|------|---------|
| OpenAI | LLM API | 미국 | ✅ 표준 DPA |
| Google Cloud | OAuth | 미국 | ✅ 표준 DPA |
| Kakao | OAuth | 한국 | ✅ 표준 DPA |
| Railway.app | 호스팅 | 미국 | ✅ 표준 DPA |

---

## 11. 국제 이전 (International Transfers)

| 수신국 | 메커니즘 | 상태 |
|-------|---------|------|
| 미국 (OpenAI) | EU-US Data Privacy Framework | ✅ 적정성 결정 |
| 미국 (Google) | Standard Contractual Clauses (SCC) | ✅ SCC 2021 |

---

## 12. 변경 이력 (Change Log)

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-03-08 | 1.0 | 초기 ROPA 작성 |

---

## 13. 승인

**작성자**: AI 엔지니어 Claude
**검토자**: (미지정)
**승인자**: (미지정)
**날짜**: 2026-03-08

---

**참고 문서**:
- GDPR (Regulation (EU) 2016/679)
- GDPR Article 30 (Records of Processing Activities)
- WP29 Guidelines on DPO
- EDPB Guidelines 07/2020 on targeting
