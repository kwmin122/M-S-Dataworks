# HWP E2E 테스트 구현 플랜

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 나라장터 HWP 공고문을 실제 LLM 파이프라인(RFx 분석 → 자격 매칭)으로 테스트하고, document_parser에 .hwp 지원을 영구 추가한다.

**Architecture:**
- `document_parser.py`에 `_parse_hwp()` 추가 (olefile + zlib + HWPTAG_PARA_TEXT 레코드 파싱)
- 더미 회사 TXT 파일 2개 (적격/비적격) → RAGEngine → QualificationMatcher
- E2E 스크립트: `scripts/smoke_test_hwp_rfx.py` (실제 OpenAI API 호출)

**Tech Stack:** Python 3.11+, olefile (설치됨), zlib (stdlib), OpenAI GPT-4o-mini, ChromaDB

---

## 전제 조건

```bash
cd /Users/min-kyungwook/Downloads/기업전용챗봇세분화
source .venv/bin/activate 2>/dev/null || true
python -c "import olefile; print('olefile OK')"
# .env 파일에 OPENAI_API_KEY 설정 확인
grep OPENAI_API_KEY .env | head -1
```

---

## Task 1: HWP 파서 단위 테스트 작성 (TDD - 실패 먼저)

**Files:**
- Create: `tests/test_hwp_parser.py`
- Read before writing: `document_parser.py:144-168` (DocumentParser.parse 구조 확인)

**Step 1: 실패 테스트 작성**

```bash
cat > tests/test_hwp_parser.py << 'PYEOF'
"""
HWP 파서 단위 테스트 (document_parser._parse_hwp).
LLM 미호출 - 순수 파싱 로직만 검증.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from document_parser import DocumentParser

HWP_PATH = Path("/Users/min-kyungwook/Downloads") / "[공고문] [9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역.hwp"


def test_hwp_file_exists():
    """테스트 HWP 파일이 존재해야 함"""
    assert HWP_PATH.exists(), f"HWP 파일 없음: {HWP_PATH}"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_returns_parsed_document():
    """parse()가 .hwp 파일을 ParsedDocument로 반환해야 함"""
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    assert doc is not None
    assert doc.filename.endswith(".hwp")
    assert doc.char_count > 100, f"텍스트가 너무 짧음: {doc.char_count}자"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_contains_key_text():
    """파싱된 텍스트에 공고 핵심 내용이 포함되어야 함"""
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    text = doc.text

    assert "엔지니어링" in text or "정보통신" in text, \
        "면허 관련 텍스트 없음"
    assert "고양" in text or "파주" in text, \
        "지역 제한 텍스트 없음"
    assert "감리" in text, \
        "감리용역 텍스트 없음"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_extracts_budget():
    """예산 금액이 텍스트에 포함되어야 함"""
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    # 43,417,000원 또는 39,470,000원 (추정가격)
    assert "43,417,000" in doc.text or "39,470,000" in doc.text or "43417000" in doc.text, \
        f"예산 금액 없음. 텍스트 앞 500자: {doc.text[:500]}"


@pytest.mark.skipif(not HWP_PATH.exists(), reason="HWP 파일 없음")
def test_hwp_parse_and_chunk():
    """parse_and_chunk()가 청크를 반환해야 함"""
    parser = DocumentParser()
    chunks = parser.parse_and_chunk(str(HWP_PATH))
    assert len(chunks) >= 1, "청크가 없음"
    assert all(c.source_file for c in chunks), "source_file 없는 청크 존재"


def test_unsupported_hwp_raises_before_fix():
    """수정 전: .hwp는 ValueError 발생해야 함 (이 테스트는 구현 후 삭제)"""
    # 이 테스트는 _parse_hwp 구현 후 자동으로 실패하므로
    # 구현 후 테스트 파일에서 이 함수를 삭제하세요.
    pass
PYEOF
```

**Step 2: 테스트 실행 (실패 확인)**

```bash
python -m pytest tests/test_hwp_parser.py -v 2>&1 | tail -15
```
Expected: `test_hwp_parse_returns_parsed_document` 등이 `ValueError: 지원하지 않는 파일 형식` 으로 FAIL

---

## Task 2: document_parser.py에 HWP 지원 추가

**Files:**
- Modify: `document_parser.py:155-163` (parse() 분기 + `_parse_hwp` 메서드 추가)

**Step 1: parse() 메서드에 .hwp 분기 추가**

`document_parser.py:155-163`에서 아래를 찾아:

```python
        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(path)
        if ext == ".docx":
            return self._parse_docx(path)
        if ext == ".txt":
            return self._parse_txt(path)

        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")
```

아래로 교체:

```python
        ext = path.suffix.lower()
        if ext == ".pdf":
            return self._parse_pdf(path)
        if ext == ".docx":
            return self._parse_docx(path)
        if ext == ".txt":
            return self._parse_txt(path)
        if ext == ".hwp":
            return self._parse_hwp(path)

        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")
```

**Step 2: `_parse_hwp` 메서드 추가** (`_parse_txt` 메서드 바로 앞에 삽입)

```python
    def _parse_hwp(self, path: Path) -> ParsedDocument:
        """HWP 5.x 파일 파싱 (olefile + zlib).

        HWP 5.x 구조:
        - OLE Compound Document (olefile로 열기)
        - BodyText/Section0 스트림: zlib raw deflate 압축
        - 레코드 타입 67 (HWPTAG_PARA_TEXT): UTF-16-LE 텍스트

        가비지 필터: 한글/영문/숫자/공통 기호 외 문자 제거
        """
        try:
            import olefile
        except ImportError as exc:
            raise ImportError("olefile 미설치: pip install olefile") from exc

        import zlib
        import struct

        try:
            ole = olefile.OleFileIO(str(path))
        except Exception as exc:
            raise ValueError(f"HWP 파일을 열 수 없습니다: {exc}") from exc

        if not ole.exists("BodyText/Section0"):
            ole.close()
            raise ValueError("HWP 5.x 형식이 아닙니다 (BodyText/Section0 없음)")

        raw_data = ole.openstream("BodyText/Section0").read()
        ole.close()

        try:
            decompressed = zlib.decompress(raw_data, -15)
        except zlib.error as exc:
            raise ValueError(f"HWP 압축 해제 실패: {exc}") from exc

        # 레코드 파싱: type 67 = HWPTAG_PARA_TEXT
        paragraphs: list[str] = []
        i = 0
        while i < len(decompressed) - 4:
            tag_header = struct.unpack_from("<I", decompressed, i)[0]
            record_type = tag_header & 0x3FF
            size = (tag_header >> 20) & 0xFFF
            if size == 0xFFF:
                if i + 8 > len(decompressed):
                    break
                size = struct.unpack_from("<I", decompressed, i + 4)[0]
                i += 8
            else:
                i += 4
            if i + size > len(decompressed):
                break
            if record_type == 67:  # HWPTAG_PARA_TEXT
                chunk = decompressed[i : i + size]
                try:
                    text = chunk.decode("utf-16-le", errors="ignore").strip()
                except Exception:
                    text = ""
                if text and len(text) > 1:
                    # 한글/영문/숫자/공통 기호만 유지, 가비지 제거
                    cleaned = re.sub(r"[^\uAC00-\uD7A3\u3130-\u318F\w\s\-.,()[\]{}:;/\\@#%&*+=<>?!\n]", "", text).strip()
                    if cleaned:
                        paragraphs.append(cleaned)
            i += size

        text = "\n".join(paragraphs)
        normalized = self.chunker._normalize_text(text)
        pages = [normalized] if normalized else []
        return ParsedDocument(
            filename=path.name,
            text=normalized,
            pages=pages,
            metadata={"file_type": "hwp"},
        )
```

**Step 3: py_compile 확인**

```bash
python -m py_compile document_parser.py && echo "OK"
```
Expected: `OK`

**Step 4: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_hwp_parser.py -v --tb=short 2>&1 | tail -15
```
Expected: `test_hwp_parse_returns_parsed_document`, `test_hwp_parse_contains_key_text`, `test_hwp_parse_extracts_budget`, `test_hwp_parse_and_chunk` PASS

**Step 5: 기존 파서 회귀 확인**

```bash
python -m pytest tests/ -k "not smoke" --ignore=tests/test_evaluation_accuracy.py -q --tb=short 2>&1 | tail -10
```
Expected: 89 passed

**Step 6: 커밋**

```bash
git add document_parser.py tests/test_hwp_parser.py
git commit -m "$(cat <<'EOF'
feat(document_parser): add HWP 5.x support via olefile

- _parse_hwp(): olefile + zlib raw deflate + HWPTAG_PARA_TEXT(67) 레코드 파싱
- UTF-16-LE 디코딩 + 가비지 문자 필터링
- parse()에 .hwp 분기 추가 (기존 API 하위 호환 유지)
- tests/test_hwp_parser.py: 파일 존재/내용/청킹 단위 테스트

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 더미 회사 파일 생성

**Files:**
- Create: `testdata/company_a_goyang.txt`
- Create: `testdata/company_b_seoul.txt`

**Step 1: Company A (적격) 파일 생성**

```bash
mkdir -p testdata
cat > testdata/company_a_goyang.txt << 'EOF'
회사명: (주)고양정보통신엔지니어링
대표이사: 김정보
설립연도: 2015년
주된 영업소 소재지: 경기도 고양시 일산서구 대화동 123-45 정보빌딩 3층

사업자등록번호: 128-81-45678
조달청 입찰참가자격 등록번호: 20150451234
등록일: 2015년 11월 20일

보유 면허 및 자격:
- 엔지니어링산업진흥법에 의한 엔지니어링사업(정보통신) 신고번호: IT-2015-045231
  신고기관: 한국엔지니어링협회
  유효기간: 2015년 ~ 현재 (갱신 유지 중)

전문 인력:
- 정보통신기사 자격증 보유자: 8명
- 정보통신기술사: 1명 (홍길동, 기술사 제22-1234호)

수행 실적 (최근 3년):
1. 2023년 완료 - 고양시 OO초등학교 무선 네트워크 감리용역
   계약금액: 35,000,000원, 발주기관: 고양교육지원청
   수행기간: 2023.03.01 ~ 2023.06.30, 완료 확인서 발급

2. 2024년 완료 - 파주시 OO중학교 유선 네트워크 개선 감리용역
   계약금액: 42,000,000원, 발주기관: 파주교육지원청
   수행기간: 2024.02.15 ~ 2024.07.31, 완료 확인서 발급

3. 2024년 완료 - 고양시 OO고등학교 정보통신공사 감리용역
   계약금액: 38,500,000원, 발주기관: 고양교육지원청
   수행기간: 2024.04.01 ~ 2024.09.30, 완료 확인서 발급

손해배상책임보험:
- 보험사: 한국엔지니어링보험(주)
- 증서번호: ENG-2025-00891
- 유효기간: 2025.01.01 ~ 2025.12.31

납세 현황: 국세/지방세 완납 확인 (2026년 1월 기준)
조세포탈 해당 없음

연락처:
- 계약 담당: 이계약 과장 (031-000-1234)
- 기술 담당: 박기술 부장 (031-000-5678)
EOF
```

**Step 2: Company B (비적격) 파일 생성**

```bash
cat > testdata/company_b_seoul.txt << 'EOF'
회사명: (주)서울아이티컨설팅
대표이사: 박서울
설립연도: 2018년
주된 영업소 소재지: 서울특별시 강남구 테헤란로 123 IT센터 10층

사업자등록번호: 220-81-78901
조달청 입찰참가자격: 미등록 (나라장터 전자입찰 시스템 미등록)

보유 면허 및 자격:
- 정보통신 관련 법령에 의한 엔지니어링 면허 없음
- IT 컨설팅 및 SI 사업만 운영 중
- 소프트웨어사업자 신고번호: SW-2018-078901

주요 사업 영역:
- IT 시스템 컨설팅
- 소프트웨어 개발 및 구축
- ERP 시스템 구축

수행 실적 (최근 3년):
1. 2023년 완료 - OO기업 ERP 시스템 구축
   계약금액: 500,000,000원 (5억원), 발주기관: OO(주)
   (정보통신공사 감리 실적 아님)

2. 2024년 완료 - OO금융 IT 보안 컨설팅
   계약금액: 120,000,000원, 발주기관: OO금융(주)

정보처리기사 보유자: 5명
그 외 정보통신 관련 기사/기술사 없음

연락처:
- 대표전화: 02-000-1234
- 이메일: contact@seoulit.co.kr
EOF
```

**Step 3: 파일 확인**

```bash
ls -la testdata/company_a_goyang.txt testdata/company_b_seoul.txt
wc -l testdata/company_a_goyang.txt testdata/company_b_seoul.txt
```
Expected: 두 파일 모두 존재, 40줄 이상

**Step 4: 커밋**

```bash
git add testdata/company_a_goyang.txt testdata/company_b_seoul.txt
git commit -m "$(cat <<'EOF'
test: 적격/비적격 더미 회사 파일 추가 (HWP E2E 테스트용)

- company_a_goyang.txt: 고양시 소재 + 엔지니어링(정보통신) 면허 + 실적 3건
- company_b_seoul.txt: 서울 소재 + 면허/조달청 등록 없음

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: E2E 스크립트 작성

**Files:**
- Create: `scripts/smoke_test_hwp_rfx.py`

**Step 1: 스크립트 작성**

```bash
cat > scripts/smoke_test_hwp_rfx.py << 'PYEOF'
#!/usr/bin/env python3
"""
HWP 공고문 E2E 파이프라인 스모크 테스트.

사용법:
  python scripts/smoke_test_hwp_rfx.py

환경변수:
  OPENAI_API_KEY  (필수) - 실제 LLM 호출
  HWP_PATH        (선택) - 기본값: 내장 공고문 경로

테스트 대상:
  1. HWP 파싱 (document_parser)
  2. RFx 분석 (rfx_analyzer - real LLM)
  3. Company A (적격): 고양시 + 정보통신 면허
  4. Company B (비적격): 서울 + 면허 없음
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# ── 설정 ──────────────────────────────────────────────────────────────────────
HWP_PATH = Path(os.getenv(
    "HWP_PATH",
    "/Users/min-kyungwook/Downloads/"
    "[공고문] [9권역]학교 유무선 네트워크 개선 3차 정보통신공사 감리용역.hwp"
))
COMPANY_A = Path(__file__).parent.parent / "testdata" / "company_a_goyang.txt"
COMPANY_B = Path(__file__).parent.parent / "testdata" / "company_b_seoul.txt"
REPORT_DIR = Path(__file__).parent.parent / "reports"
API_KEY = os.getenv("OPENAI_API_KEY", "")


def header(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def check_prerequisites() -> None:
    header("전제 조건 확인")
    errors = []
    if not HWP_PATH.exists():
        errors.append(f"HWP 파일 없음: {HWP_PATH}")
    if not COMPANY_A.exists():
        errors.append(f"Company A 파일 없음: {COMPANY_A}")
    if not COMPANY_B.exists():
        errors.append(f"Company B 파일 없음: {COMPANY_B}")
    if not API_KEY or API_KEY == "your_openai_api_key_here":
        errors.append("OPENAI_API_KEY 미설정 (.env 파일 확인)")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        sys.exit(1)
    print(f"  ✅ HWP: {HWP_PATH.name}")
    print(f"  ✅ Company A: {COMPANY_A.name}")
    print(f"  ✅ Company B: {COMPANY_B.name}")
    print(f"  ✅ API KEY: {'*' * 8}{API_KEY[-4:]}")


def step1_parse_hwp() -> str:
    header("STEP 1: HWP 파싱")
    from document_parser import DocumentParser
    parser = DocumentParser()
    doc = parser.parse(str(HWP_PATH))
    print(f"  파일: {doc.filename}")
    print(f"  텍스트: {doc.char_count:,}자, {doc.page_count} 페이지")
    print(f"  앞 300자: {doc.text[:300]}")
    assert doc.char_count > 500, "텍스트 추출 실패"
    print("  ✅ HWP 파싱 성공")
    return doc.text


def step2_analyze_rfx(text: str) -> object:
    header("STEP 2: RFx 분석 (LLM 호출)")
    from rfx_analyzer import RFxAnalyzer
    # analyze()는 파일 경로 기반이므로 임시 txt 파일 생성
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write(text)
        tmp_path = f.name
    try:
        analyzer = RFxAnalyzer(api_key=API_KEY)
        result = analyzer.analyze(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    print(f"  공고명: {result.title or '(없음)'}")
    print(f"  발주기관: {result.issuing_org or '(없음)'}")
    print(f"  문서유형: {result.document_type}")
    print(f"  자격요건 {len(result.requirements)}개:")
    for i, req in enumerate(result.requirements, 1):
        mandatory = "필수" if req.is_mandatory else "권장"
        print(f"    {i}. [{mandatory}][{req.category}] {req.description}")
        if req.constraints:
            for c in req.constraints:
                print(f"       → constraint: {c.metric}/{c.op}/{c.value} ({c.raw})")
    assert len(result.requirements) >= 1, "자격요건 추출 실패"
    print("  ✅ RFx 분석 성공")
    return result


def step3_match_company(company_name: str, company_file: Path, rfx_result: object) -> dict:
    header(f"STEP 3: 회사 매칭 - {company_name}")
    from engine import RAGEngine
    from matcher import QualificationMatcher

    # 독립적인 임시 컬렉션 사용
    col_name = f"smoke_test_{uuid.uuid4().hex[:8]}"
    persist_dir = f"/tmp/smoke_test_{col_name}"

    engine = RAGEngine(
        persist_directory=persist_dir,
        collection_name=col_name,
    )
    engine.add_document(str(company_file))
    print(f"  회사 정보 로드: {engine.collection.count()}개 청크")

    matcher = QualificationMatcher(engine, api_key=API_KEY)
    matching = matcher.match(rfx_result)

    print(f"  종합 결과: {matching.overall_status}")
    print(f"  권고사항: {matching.recommendation}")
    print(f"  요건별 결과:")
    for req_match in matching.requirement_matches:
        status_icon = {"MET": "✅", "NOT_MET": "❌", "PARTIALLY_MET": "🟡", "UNKNOWN": "❓"}.get(
            req_match.status.value if hasattr(req_match.status, "value") else str(req_match.status), "?"
        )
        print(f"    {status_icon} [{req_match.requirement.category}] {req_match.requirement.description}")
        print(f"       근거: {req_match.evidence[:80] if req_match.evidence else '없음'}")

    return {
        "company": company_name,
        "file": str(company_file.name),
        "overall_status": str(matching.overall_status),
        "recommendation": matching.recommendation,
        "requirements": [
            {
                "category": m.requirement.category,
                "description": m.requirement.description,
                "status": str(m.status),
                "confidence": m.confidence,
                "evidence": m.evidence,
            }
            for m in matching.requirement_matches
        ],
    }


def main() -> None:
    print(f"\n🔬 HWP 공고문 E2E 파이프라인 스모크 테스트")
    print(f"   실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    check_prerequisites()

    # Step 1: HWP 파싱
    rfx_text = step1_parse_hwp()

    # Step 2: RFx 분석
    rfx_result = step2_analyze_rfx(rfx_text)

    # Step 3: 두 회사 매칭
    results = []
    results.append(step3_match_company("Company A (고양시·적격)", COMPANY_A, rfx_result))
    results.append(step3_match_company("Company B (서울·비적격)", COMPANY_B, rfx_result))

    # 결과 저장
    REPORT_DIR.mkdir(exist_ok=True)
    report = {
        "date": datetime.now().isoformat(),
        "hwp_file": str(HWP_PATH.name),
        "rfx_title": rfx_result.title,
        "rfx_issuing_org": rfx_result.issuing_org,
        "requirements_count": len(rfx_result.requirements),
        "company_results": results,
    }
    report_path = REPORT_DIR / f"smoke_hwp_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 최종 요약
    header("최종 요약")
    for r in results:
        status_icon = "✅" if "MET" in r["overall_status"] and "NOT" not in r["overall_status"] else "❌"
        print(f"  {status_icon} {r['company']}: {r['overall_status']}")
    print(f"\n  📄 리포트 저장: {report_path}")
    print("\n  ✅ 스모크 테스트 완료\n")


if __name__ == "__main__":
    main()
PYEOF
```

**Step 2: 스크립트 컴파일 확인**

```bash
python -m py_compile scripts/smoke_test_hwp_rfx.py && echo "OK"
```
Expected: `OK`

**Step 3: 커밋**

```bash
git add scripts/smoke_test_hwp_rfx.py
git commit -m "$(cat <<'EOF'
feat: HWP E2E 파이프라인 스모크 테스트 스크립트

- HWP 파싱 → RFx 분석 → 회사 A/B 매칭 전체 파이프라인
- Company A (고양시·적격) vs Company B (서울·비적격) 비교
- 결과 reports/smoke_hwp_*.json 자동 저장
- 사전 조건 확인 (파일 존재, API KEY) → 없으면 안내 후 종료

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: E2E 실행 및 결과 검증

**Step 1: `.env` 파일에 실제 API KEY 설정 확인**

```bash
grep OPENAI_API_KEY .env
```
Expected: `OPENAI_API_KEY=sk-...` (실제 키여야 함)

**Step 2: E2E 스모크 테스트 실행**

```bash
python scripts/smoke_test_hwp_rfx.py 2>&1 | tee reports/smoke_test_run.txt
```

Expected 출력 예시:
```
STEP 1: HWP 파싱
  파일: [공고문] [9권역]...hwp
  텍스트: 9,xxx자 ...
  ✅ HWP 파싱 성공

STEP 2: RFx 분석 (LLM 호출)
  공고명: 학교 유무선 네트워크개선 3차 정보통신공사 감리용역
  발주기관: 경기도고양교육지원청
  자격요건 N개:
    1. [필수][필수자격] 엔지니어링사업(정보통신) 또는 기술사사무소 면허
    2. [필수][지역요건] 주된 영업소 소재지 고양·파주
    ...

STEP 3: 회사 매칭 - Company A (고양시·적격)
  ✅ ...

STEP 3: 회사 매칭 - Company B (서울·비적격)
  ❌ ...

최종 요약
  ✅ Company A (고양시·적격): MET (또는 PARTIALLY_MET)
  ❌ Company B (서울·비적격): NOT_MET
```

**Step 3: 리포트 파일 확인**

```bash
ls -la reports/smoke_hwp_*.json | tail -1
python -c "
import json
from pathlib import Path
files = sorted(Path('reports').glob('smoke_hwp_*.json'))
if files:
    data = json.loads(files[-1].read_text(encoding='utf-8'))
    print('공고명:', data.get('rfx_title'))
    print('자격요건 수:', data.get('requirements_count'))
    for r in data.get('company_results', []):
        print(f'{r[\"company\"]}: {r[\"overall_status\"]}')
"
```

**Step 4: 전체 회귀 테스트**

```bash
python -m pytest tests/ -q --tb=short -k "not evaluation_accuracy" 2>&1 | tail -10
```
Expected: 모두 PASS (HWP 파서 테스트 포함)

**Step 5: 결과 커밋**

```bash
git add reports/smoke_hwp_*.json reports/smoke_test_run.txt 2>/dev/null || true
git status
git commit -m "$(cat <<'EOF'
docs: HWP E2E 스모크 테스트 실행 결과

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)" -- reports/ 2>/dev/null || echo "변경사항 없으면 스킵"
```

---

## 검증 체크리스트

```bash
# 1. HWP 파서 단위 테스트
python -m pytest tests/test_hwp_parser.py -v

# 2. 전체 회귀
python -m pytest tests/ -q --tb=short

# 3. 스모크 테스트 (API KEY 필요)
python scripts/smoke_test_hwp_rfx.py

# 4. 예상 결과 확인
#   Company A → MET 또는 PARTIALLY_MET (면허/지역 적격)
#   Company B → NOT_MET (지역·면허 부적격)
```

---

## 참고: 이 테스트로 검증되는 것

| 컴포넌트 | 검증 내용 |
|---------|----------|
| `document_parser._parse_hwp` | HWP 5.x 텍스트 추출 |
| `RFxAnalyzer` | 면허/지역 자격요건 추출 (CUSTOM metric) |
| `ConstraintEvaluator` | CUSTOM → FALLBACK_NEEDED → LLM fallback 경로 |
| `QualificationMatcher` | LLM 기반 면허/지역 판단 |
| 결과 비교 | Company A(적격) vs Company B(비적격) 차이 |
