"""RFP 동의어 사전 — LLM 프롬프트 주입 + RAG 쿼리 확장.

Source: docs/plans/RFP_동의어_사전.md
"""

RFP_SYNONYM_DICT: dict[str, dict] = {
    # ── 금액/가격 ──
    "사업비": {
        "synonyms": ["사업비", "총사업비", "사업금액", "사업 비", "총 사업비"],
        "category": "금액",
        "note": "사업 전체에 투입되는 총 금액",
    },
    "추정가격": {
        "synonyms": ["추정가격", "추산가격", "추정 가격"],
        "category": "금액",
        "note": "예정가격 결정 전 산정 (부가세·관급자재 미포함)",
    },
    "추정금액": {
        "synonyms": ["추정금액", "추정 금액"],
        "category": "금액",
        "note": "추정가격 + 부가세 + 관급자재비",
    },
    "예정가격": {
        "synonyms": ["예정가격", "예정 가격"],
        "category": "금액",
        "note": "낙찰·계약금액 결정 기준 (부가세 포함)",
    },
    "기초금액": {
        "synonyms": ["기초금액", "기초 금액"],
        "category": "금액",
        "note": "복수예비가격 산출 기준",
    },
    "계약금액": {
        "synonyms": ["계약금액", "계약 금액", "도급금액", "도급액", "낙찰금액"],
        "category": "금액",
        "note": "실제 계약 체결 금액",
    },
    "배정예산": {
        "synonyms": ["배정예산", "예산액", "예산금액", "총예산", "사업예산", "투입예산", "예산"],
        "category": "금액",
        "note": "해당 사업에 배정된 예산",
    },
    "설계금액": {
        "synonyms": ["설계금액", "설계가격", "설계 금액"],
        "category": "금액",
        "note": "설계서 기반 산출 금액",
    },
    # ── 발주/기관 ──
    "발주기관": {
        "synonyms": ["발주기관", "발주처", "발주관서", "발주자", "주관기관", "주관부서", "주관처"],
        "category": "기관",
    },
    "수요기관": {
        "synonyms": ["수요기관", "수요처", "수요부서", "사업기관", "사용기관"],
        "category": "기관",
    },
    "감독관": {
        "synonyms": ["감독관", "감독공무원", "감독원", "감독자", "담당공무원", "사업담당자"],
        "category": "기관",
    },
    "계약자": {
        "synonyms": ["계약자", "계약상대자", "사업수행자", "수급자", "시공자", "용역업체", "수행업체", "도급자", "수급인"],
        "category": "기관",
    },
    "제안사": {
        "synonyms": ["제안사", "제안업체", "제안자", "입찰자", "입찰참가자", "응찰자", "응찰업체", "참여업체"],
        "category": "기관",
    },
    # ── 기간 ──
    "사업기간": {
        "synonyms": ["사업기간", "계약기간", "용역기간", "수행기간", "공사기간", "시행기간", "이행기간", "과업기간"],
        "category": "기간",
    },
    "납품기한": {
        "synonyms": ["납품기한", "납품기일", "납기", "납품일", "완료일", "완료기한", "준공기한", "준공일"],
        "category": "기간",
    },
    "착수일": {
        "synonyms": ["착수일", "착수일자", "계약일", "개시일", "시작일", "착공일"],
        "category": "기간",
    },
    "제출기한": {
        "synonyms": ["제출기한", "제출마감", "제출마감일", "접수마감", "접수기한", "마감일시", "제출일시"],
        "category": "기간",
    },
    "공고기간": {
        "synonyms": ["공고기간", "공고일", "입찰공고일", "게시일", "게시기간"],
        "category": "기간",
    },
    # ── 계약방법 ──
    "일반경쟁입찰": {
        "synonyms": ["일반경쟁", "일반경쟁입찰", "공개경쟁", "공개경쟁입찰"],
        "category": "계약방법",
    },
    "제한경쟁입찰": {
        "synonyms": ["제한경쟁", "제한경쟁입찰", "제한입찰"],
        "category": "계약방법",
    },
    "협상에의한계약": {
        "synonyms": ["협상에 의한 계약", "협상계약", "기술협상", "협상에의한계약"],
        "category": "계약방법",
    },
    "적격심사": {
        "synonyms": ["적격심사", "적격심사제", "적격심사낙찰제", "적격심사 낙찰제"],
        "category": "계약방법",
    },
    "종합평가낙찰제": {
        "synonyms": ["종합평가낙찰제", "종합평가", "종합낙찰제", "종합심사"],
        "category": "계약방법",
    },
    "최저가낙찰제": {
        "synonyms": ["최저가", "최저가낙찰", "최저가낙찰제", "최저가격 낙찰"],
        "category": "계약방법",
    },
    # ── 공동계약 ──
    "공동수급체": {
        "synonyms": ["공동수급체", "공동도급체", "공동수급", "공동도급", "컨소시엄", "JV", "조인트벤처"],
        "category": "공동계약",
    },
    "공동이행방식": {
        "synonyms": ["공동이행", "공동이행방식", "공동이행 방식"],
        "category": "공동계약",
        "note": "출자비율에 따라 연대 이행",
    },
    "분담이행방식": {
        "synonyms": ["분담이행", "분담이행방식", "분담이행 방식"],
        "category": "공동계약",
        "note": "공종별 분담 이행",
    },
    "주계약자관리방식": {
        "synonyms": ["주계약자관리방식", "주계약자 관리방식", "주계약자방식"],
        "category": "공동계약",
    },
    "출자비율": {
        "synonyms": ["출자비율", "지분율", "지분률", "참여비율", "계약참여비율"],
        "category": "공동계약",
    },
    "최소지분율": {
        "synonyms": ["최소지분율", "최소지분률", "최소 지분율", "계약참여 최소지분율"],
        "category": "공동계약",
    },
    # ── 입찰자격 ──
    "입찰참가자격": {
        "synonyms": ["입찰참가자격", "입찰참가 자격", "응찰자격", "참가자격", "입찰자격", "참여자격", "입찰참가자격조건"],
        "category": "자격",
    },
    "나라장터등록": {
        "synonyms": ["나라장터", "G2B", "국가종합전자조달", "전자조달시스템", "입찰참가자격등록"],
        "category": "자격",
    },
    "직접생산확인": {
        "synonyms": ["직접생산확인증명서", "직접생산증명서", "직접생산 확인증명서", "직접생산확인", "직접생산증명"],
        "category": "자격",
    },
    "중소기업확인": {
        "synonyms": ["중소기업확인서", "중기업확인서", "소기업확인서", "소상공인확인서", "중소기업 확인서", "중소기업 범위 확인"],
        "category": "자격",
    },
    "부정당업자": {
        "synonyms": ["부정당업자", "부정당 업자", "입찰참가자격 제한", "입찰참가자격제한", "제재업체"],
        "category": "자격",
    },
    # ── 평가 ──
    "기술능력평가": {
        "synonyms": ["기술능력평가", "기술평가", "기술능력 평가", "제안서평가", "제안서 평가", "기술부문평가"],
        "category": "평가",
    },
    "정성적평가": {
        "synonyms": ["정성적 평가", "정성적평가", "정성평가", "기술제안 평가", "제안내용 평가"],
        "category": "평가",
    },
    "정량적평가": {
        "synonyms": ["정량적 평가", "정량적평가", "정량평가", "정량적 지표 평가", "계량평가"],
        "category": "평가",
    },
    "가격평가": {
        "synonyms": ["가격평가", "입찰가격평가", "가격 평가", "입찰가격 평가", "가격점수"],
        "category": "평가",
    },
    "경영상태": {
        "synonyms": ["경영상태", "경영상태평가", "신용평가등급", "신용평가", "신용등급", "기업신용", "재무상태", "재무건전성"],
        "category": "평가",
    },
    "사업이행실적": {
        "synonyms": ["사업이행실적", "수행실적", "사업실적", "수행경험", "유사사업실적", "시공실적", "이행실적", "동종실적", "유사실적"],
        "category": "평가",
    },
    "기술능력": {
        "synonyms": ["기술능력", "기술인력", "기술인력보유", "기술자보유", "기술상태", "참여인력"],
        "category": "평가",
    },
    "신인도": {
        "synonyms": ["신인도", "기업신인도", "계약질서준수", "계약질서 준수", "신뢰도"],
        "category": "평가",
    },
    # ── 분리발주 ──
    "분리발주": {
        "synonyms": ["분리발주", "분리 발주", "분할발주", "별도입찰"],
        "category": "발주",
    },
    "관급자재": {
        "synonyms": ["관급자재", "관급", "관급 자재", "관급품"],
        "category": "발주",
    },
    # ── 하도급 ──
    "하도급": {
        "synonyms": ["하도급", "하도급계약", "하청", "하청계약"],
        "category": "하도급",
    },
    "하도급비율": {
        "synonyms": ["하도급비율", "하도급 비율", "하도급률", "하도급한도"],
        "category": "하도급",
    },
    # ── 하자보수 ──
    "하자보수기간": {
        "synonyms": [
            "하자보수기간", "하자보증기간", "하자담보기간",
            "무상보증기간", "무상보수기간", "무상 A/S기간",
            "A/S기간", "보증기간", "품질보증기간",
        ],
        "category": "보증",
    },
}


def get_all_synonyms(canonical_key: str) -> list[str]:
    """특정 키의 모든 동의어 반환."""
    entry = RFP_SYNONYM_DICT.get(canonical_key)
    return entry["synonyms"] if entry else []


def find_canonical_key(term: str) -> str | None:
    """입력 용어의 표준 키 찾기."""
    for key, entry in RFP_SYNONYM_DICT.items():
        if term in entry["synonyms"]:
            return key
    return None


def expand_query(query: str) -> list[str]:
    """RAG 검색 쿼리 확장 — 동의어를 모두 포함하여 검색."""
    expanded = [query]
    for _key, entry in RFP_SYNONYM_DICT.items():
        for syn in entry["synonyms"]:
            if syn in query:
                for alt in entry["synonyms"]:
                    if alt != syn:
                        expanded.append(query.replace(syn, alt))
                break
    return list(set(expanded))


def get_category_keywords(category: str) -> list[str]:
    """특정 카테고리의 모든 키워드 반환."""
    keywords = []
    for entry in RFP_SYNONYM_DICT.values():
        if entry["category"] == category:
            keywords.extend(entry["synonyms"])
    return list(set(keywords))


_CACHED_PROMPT_INJECTION: str | None = None


def generate_prompt_injection() -> str:
    """LLM 프롬프트에 주입할 동의어 가이드 텍스트 생성 (모듈 레벨 캐시)."""
    global _CACHED_PROMPT_INJECTION
    if _CACHED_PROMPT_INJECTION is not None:
        return _CACHED_PROMPT_INJECTION
    lines = ["## 동의어 매핑 가이드 (정보 추출 시 참조)", ""]
    for key, entry in RFP_SYNONYM_DICT.items():
        syns = ", ".join(f'"{s}"' for s in entry["synonyms"])
        note = f' — {entry.get("note", "")}' if entry.get("note") else ""
        lines.append(f"- **{key}**: {syns}{note}")
    lines.append("")
    lines.append("※ 위 목록에 없더라도 문맥상 동일한 의미의 표현이 있으면 함께 인식하세요.")
    _CACHED_PROMPT_INJECTION = "\n".join(lines)
    return _CACHED_PROMPT_INJECTION
