# 더미 데이터 생성 스크립트

**생성일:** 2026-03-08
**목적:** Kira Bot E2E 테스트용 현실적 더미 데이터 생성

---

## 구조

```
scripts/dummy_data/
├── company_profiles.json       # 회사 20개 기본 정보 (수동 큐레이션)
├── project_templates.json      # 프로젝트 카테고리/금액 템플릿
├── company_generator.py        # PDF 생성 (reportlab)
├── personnel_generator.py      # 인력 합성 (Faker)
├── company_data_builder.py     # CompanyDB 적재
└── test_*.py                   # 단위 테스트
```

---

## 사용 방법

**1. 의존성 설치:**
```bash
pip install -r requirements-dummy.txt
```

**2. 회사 프로필 큐레이션:**
```bash
vi scripts/dummy_data/company_profiles.json
# 20개 회사 정보 수동 입력 (1~2시간)
```

**3. 더미 데이터 생성:**
```bash
python scripts/generate_dummy_data.py
```

**4. 검증:**
```bash
ls data/company_docs/ | wc -l  # 20
cd rag_engine && python -c "from company_db import CompanyDB; db = CompanyDB(); print(len(db.get_all_track_records()))"  # 240
```

---

## 재생성

```bash
# 1. CompanyDB 초기화
cd rag_engine && python -c "from company_db import CompanyDB; db = CompanyDB(); db.clear_all()"

# 2. PDF 삭제
rm -rf data/company_docs/*.pdf

# 3. 재생성
python scripts/generate_dummy_data.py
```

---

## 테스트

```bash
cd scripts/dummy_data
pytest -v
```

---

## 출력

**회사소개서 PDF:**
- 위치: `data/company_docs/`
- 개수: 20개
- 구조: 10페이지 (표지~비전)

**CompanyDB:**
- Collection: `company_track_records`, `company_personnel`
- 실적: 240건 (회사당 12건)
- 인력: 160명 (회사당 8명)

**테스트 시나리오:**
- 위치: `docs/test/TEST_SCENARIOS.md`
- 개수: 10~15개
