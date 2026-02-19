"""
rfx_analyzer의 constraints 추출 검증.
LLM mock으로 파서 로직만 테스트 (실제 API 호출 없음).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rfx_analyzer import RFxAnalyzer, RFxRequirement, RFxConstraint


MOCK_CONSTRAINTS_RESPONSE = """{
    "기본정보": {"공고명": "테스트", "발주기관": "", "공고번호": "", "제출마감일": "", "사업기간": "", "예산": ""},
    "자격요건": [
        {
            "분류": "실적요건",
            "요건": "공공기관 SI 수행실적 2건 이상",
            "필수여부": "필수",
            "상세": "최근 3년간, 건당 20억원 이상, 완료된 실적만",
            "constraints": [
                {"metric": "project_count",       "op": ">=", "value": 2,    "unit": "",         "raw": "2건 이상"},
                {"metric": "contract_amount",     "op": ">=", "value": 20.0, "unit": "KRW_100M", "raw": "건당 20억원 이상"},
                {"metric": "completion_required", "op": "==", "value": true, "unit": "",         "raw": "완료된 실적만"}
            ]
        },
        {
            "분류": "기술요건",
            "요건": "정보처리기사 보유",
            "필수여부": "필수",
            "상세": "정보처리기사 자격증 보유자",
            "constraints": []
        }
    ],
    "평가기준": [],
    "제출서류": [],
    "특이사항": []
}"""

# JSON에서 true/false/null은 Python 리터럴과 다르므로 json.loads를 거쳐야 함
# MOCK_CONSTRAINTS_RESPONSE는 실제 JSON 문자열임
# true/false를 JSON에서 허용 (JSON spec: lowercase)


def test_constraints_always_present():
    """constraints 키는 빈 배열이라도 항상 파싱 결과에 있어야 함"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(MOCK_CONSTRAINTS_RESPONSE)

    for req in result.requirements:
        assert hasattr(req, 'constraints'), f"constraints 필드 없음: {req.description}"
        assert isinstance(req.constraints, list), "constraints는 list여야 함"


def test_constraints_parsed_correctly():
    """constraints가 RFxConstraint 객체로 올바르게 파싱돼야 함"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(MOCK_CONSTRAINTS_RESPONSE)

    req = result.requirements[0]  # 실적요건
    assert len(req.constraints) == 3

    c0 = req.constraints[0]
    assert c0.metric == "project_count"
    assert c0.op == ">="
    assert c0.value == 2
    assert c0.raw == "2건 이상"

    c1 = req.constraints[1]
    assert c1.metric == "contract_amount"
    assert c1.value == 20.0
    assert c1.unit == "KRW_100M"


def test_empty_constraints_for_no_conditions():
    """조건 없는 요건은 constraints=[]이어야 함"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(MOCK_CONSTRAINTS_RESPONSE)

    req = result.requirements[1]  # 정보처리기사
    assert req.constraints == []


def test_invalid_op_is_replaced():
    """잘못된 op 문자열은 '>='로 치환되어야 함"""
    bad_response = """{
        "기본정보": {"공고명": "T", "발주기관": "", "공고번호": "", "제출마감일": "", "사업기간": "", "예산": ""},
        "자격요건": [
            {
                "분류": "실적요건",
                "요건": "테스트",
                "필수여부": "필수",
                "상세": "테스트",
                "constraints": [
                    {"metric": "contract_amount", "op": "INVALID_OP", "value": 10.0, "unit": "", "raw": "10억"}
                ]
            }
        ],
        "평가기준": [], "제출서류": [], "특이사항": []
    }"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(bad_response)

    c = result.requirements[0].constraints[0]
    assert c.op == ">=", f"잘못된 op가 '>='로 치환되어야 함, 실제: {c.op}"


def test_missing_constraints_key_defaults_to_empty():
    """constraints 키 자체가 없으면 빈 배열로 처리"""
    no_constraints_response = """{
        "기본정보": {"공고명": "T", "발주기관": "", "공고번호": "", "제출마감일": "", "사업기간": "", "예산": ""},
        "자격요건": [
            {
                "분류": "기타",
                "요건": "constraints 키 없음",
                "필수여부": "권장",
                "상세": ""
            }
        ],
        "평가기준": [], "제출서류": [], "특이사항": []
    }"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(no_constraints_response)

    req = result.requirements[0]
    assert req.constraints == [], f"constraints 없으면 빈 배열이어야 함, 실제: {req.constraints}"
