# 테스트 더미 데이터 가이드

**생성일:** 2026-03-08

---

## 디렉토리 구조

```
docs/test/
├── README.md                      # 이 파일
├── TEST_SCENARIOS.md              # 테스트 시나리오 10개
├── 입찰공고문_*.pdf                # 공고 13개 (기존)
└── ...
```

---

## 더미 데이터 세트

**회사 데이터:**
- 위치: `data/company_docs/`
- 개수: 20개 (PDF 10페이지)
- CompanyDB: 실적 240건, 인력 160명

**공고 데이터:**
- 위치: `docs/test/`
- 개수: 13개 (PDF/HWP/HWPX)

---

## 사용 방법

**1. 더미 데이터 생성:**
```bash
python scripts/generate_dummy_data.py
```

**2. 테스트 시나리오 실행:**
```bash
# TS-001 실행 (대기업 IT × 공공 클라우드)
curl -F "file=@docs/test/입찰공고문_2026년 공공데이터 및 데이터기반행정 활성화 컨설팅.pdf" \
  http://localhost:8000/api/upload_target?session_id=ts001

curl -F "file=@data/company_docs/삼성SDS_회사소개서.pdf" \
  http://localhost:8000/api/upload_company?session_id=ts001

curl -X POST http://localhost:8000/api/analyze?session_id=ts001
```

**3. 결과 확인:**
- GO/NO-GO 점수
- 제안서 DOCX
- WBS XLSX/DOCX
- PPT PPTX
- 실적기술서 DOCX

---

## 테스트 시나리오

자세한 시나리오는 `TEST_SCENARIOS.md` 참조.

**요약:**
- TS-001: 대기업 IT × 공공 클라우드 (HIGH MATCH, GO 95점)
- TS-002: 중소 제조 × 공공 클라우드 (LOW MATCH, NO-GO 45점)
- TS-003: IT 중견 × 금융 ERP (GO 88점)
- TS-004: 중소 컨설팅 × 정보화전략 (GO 82점)
- TS-005: 중견 건설 × 공공 클라우드 (NO-GO 50점, 업종 불일치)
- TS-006: 보안전문 × 보안관제 (GO 92점, 완벽 매칭)
- TS-007: 시스템통합 × 네트워크 인프라 (GO 90점)
- TS-008: 연구기업 × AI 연구용역 (GO 85점)
- TS-009: 솔루션기업 × 빅데이터 플랫폼 (GO 87점)
- TS-010: IT서비스 × MSP 운영 (GO 89점)

---

## 재생성 방법

```bash
# 1. CompanyDB 초기화
cd rag_engine
python -c "from company_db import CompanyDB; db = CompanyDB(); db.clear_all()"

# 2. PDF 삭제
rm -rf data/company_docs/*.pdf

# 3. 재생성
python scripts/generate_dummy_data.py
```

---

## 검증 체크리스트

각 시나리오 실행 후 확인:

**기본 동작:**
- [ ] 공고 업로드 성공 (200 OK)
- [ ] 회사 문서 업로드 성공 (200 OK)
- [ ] RFP 분석 완료 (자격요건 추출)
- [ ] GO/NO-GO 점수 생성

**매칭 정확도:**
- [ ] HIGH MATCH 시나리오: 85점 이상
- [ ] LOW MATCH 시나리오: 50점 이하
- [ ] DOMAIN MISMATCH: 업종 불일치 감지

**문서 생성:**
- [ ] 제안서 DOCX 생성 (블라인드 체크 통과)
- [ ] WBS XLSX/DOCX 생성
- [ ] PPT PPTX 생성 (KRDS 디자인)
- [ ] 실적기술서 DOCX 생성

**학습 루프:**
- [ ] 수정 diff 추출
- [ ] Layer 2 자동 학습 트리거

---

## 자동화 스크립트

전체 시나리오 일괄 실행:
```bash
bash scripts/run_all_scenarios.sh
```

개별 시나리오 실행:
```bash
bash scripts/verify_ts001.sh  # TS-001만 실행
```

---

## 데이터셋 정보

**회사 20개 (A그룹 10개 + B그룹 10개):**

**A그룹 (대기업/중견):**
1. company_001: 삼성SDS (15조, 25,000명, 클라우드/AI/보안)
2. company_002: LG CNS (8조, 18,000명, 클라우드/DX)
3. company_003: 현대건설 (5조, 12,000명, 건설IT)
4. company_004: 대우건설 (4조, 10,000명, 건설IT)
5. company_005: 컨설팅기업 A (500억, 200명, 정보화전략)
6. company_006: 컨설팅기업 B (300억, 150명, DX컨설팅)
7. company_007: 제조기업 A (1,000억, 500명, 제조IT)
8. company_008: 제조기업 B (800억, 400명, 방산IT)
9. company_009: 연구기업 A (200억, 80명, AI/빅데이터)
10. company_010: 연구기업 B (150억, 60명, 보안R&D)

**B그룹 (중소/전문):**
11. company_011: 더존비즈온 (2,000억, 1,500명, ERP)
12. company_012: 한국전산원 협력사 (300억, 180명, 공공SI)
13. company_013: 가비아 (500억, 300명, 클라우드호스팅)
14. company_014: 솔루션기업 B (200억, 100명, 빅데이터)
15. company_015: 시스템통합기업 A (400억, 250명, 네트워크)
16. company_016: 시스템통합기업 B (350억, 200명, 인프라)
17. company_017: 보안기업 A (250억, 120명, 보안관제)
18. company_018: 보안기업 B (180억, 90명, 침해대응)
19. company_019: IT서비스기업 C (300억, 200명, MSP)
20. company_020: IT서비스기업 D (250억, 150명, 운영)

**공고 13개:**
- 기존 `docs/test/` 디렉토리의 PDF/HWP/HWPX 파일 활용
- 주요 카테고리: 공공SI, 클라우드, 금융IT, 보안, AI/빅데이터, 네트워크, MSP

---

## 예상 작업 시간

- 더미 데이터 생성: 5~10분
- 단일 시나리오 실행: 2~3분
- 전체 시나리오 실행: 30~40분

---

## 트러블슈팅

**Q: CompanyDB에 데이터가 없다고 나옵니다.**
```bash
# CompanyDB 재생성
python scripts/generate_dummy_data.py
```

**Q: PDF 생성 시 한글 폰트 오류가 납니다.**
```bash
# macOS: 시스템 폰트 경로 확인
ls /System/Library/Fonts/Supplemental/AppleGothic.ttf

# 없으면 company_generator.py의 폰트 경로 수정
```

**Q: curl 명령어가 실패합니다.**
```bash
# 백엔드 실행 확인
python services/web_app/main.py &
cd rag_engine && uvicorn main:app --reload --port 8001 &

# 포트 확인
lsof -i :8000
lsof -i :8001
```

**Q: 제안서 생성 시 Layer 1 지식이 안 들어갑니다.**
```bash
# KnowledgeDB 확인
cd rag_engine
python -c "from knowledge_db import KnowledgeDB; db = KnowledgeDB(); print(db.get_all_knowledge_count())"
# Expected: 495

# 495 미만이면 재생성 필요 (Phase 1 구현 시 생성됨)
```

---

## 다음 단계

1. 더미 데이터 생성 완료 후 `TEST_SCENARIOS.md` 시나리오 실행
2. 10개 시나리오 모두 예상 결과와 비교
3. 매칭 정확도 < 80% 시나리오 발견 시 matcher 튜닝
4. 문서 생성 품질 검증 (블라인드, 모호 표현)
5. 학습 루프 동작 확인

---

## 참고 문서

- 구현 계획: `docs/plans/2026-03-08-dummy-data-generation-impl-plan.md`
- 설계 문서: `docs/plans/2026-03-08-dummy-data-generation-design.md`
- Phase 1 핸드오프: `docs/plans/2026-02-27-phase1-implementation-handoff.md`
