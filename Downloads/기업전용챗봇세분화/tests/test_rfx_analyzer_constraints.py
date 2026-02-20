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


def test_invalid_op_becomes_custom_metric():
    """잘못된 op는 CUSTOM 메트릭으로 마킹되어 SKIP 경로로 가야 함 ('>=' 강제 치환 금지)"""
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
    assert c.metric == "CUSTOM", (
        f"잘못된 op는 metric=CUSTOM이 되어야 함 (SKIP 경로), 실제 metric={c.metric!r}, op={c.op!r}"
    )


def test_missing_value_becomes_custom_metric():
    """value 키 누락 시 metric=CUSTOM으로 마킹하여 SKIP 경로로 가야 함 (기본값 0 금지)"""
    bad_response = """{
        "기본정보": {"공고명": "T", "발주기관": "", "공고번호": "", "제출마감일": "", "사업기간": "", "예산": ""},
        "자격요건": [
            {
                "분류": "실적요건",
                "요건": "테스트",
                "필수여부": "필수",
                "상세": "테스트",
                "constraints": [
                    {"metric": "contract_amount", "op": ">=", "unit": "", "raw": "value 없음"}
                ]
            }
        ],
        "평가기준": [], "제출서류": [], "특이사항": []
    }"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(bad_response)

    c = result.requirements[0].constraints[0]
    assert c.metric == "CUSTOM", (
        f"value 누락 시 metric=CUSTOM이 되어야 함 (SKIP 경로), 실제 metric={c.metric!r}"
    )


def test_dict_value_becomes_custom_metric():
    """value가 dict/list 타입이면 metric=CUSTOM으로 마킹하여 SKIP 경로로 가야 함"""
    bad_response = """{
        "기본정보": {"공고명": "T", "발주기관": "", "공고번호": "", "제출마감일": "", "사업기간": "", "예산": ""},
        "자격요건": [
            {
                "분류": "실적요건",
                "요건": "테스트",
                "필수여부": "필수",
                "상세": "테스트",
                "constraints": [
                    {"metric": "contract_amount", "op": ">=", "value": {"min": 10}, "unit": "", "raw": "dict value"}
                ]
            }
        ],
        "평가기준": [], "제출서류": [], "특이사항": []
    }"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    result = analyzer._parse_llm_response(bad_response)

    c = result.requirements[0].constraints[0]
    assert c.metric == "CUSTOM", (
        f"dict value는 metric=CUSTOM이 되어야 함 (SKIP 경로), 실제 metric={c.metric!r}"
    )


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


# ────────────────────────────────────────────────────────────
# Task 14: to_dict() constraints 직렬화 + general prompt 검증
# ────────────────────────────────────────────────────────────

def test_to_dict_includes_constraints():
    """to_dict()의 자격요건 항목에 constraints 필드가 포함되어야 함"""
    from rfx_analyzer import RFxAnalysisResult, RFxRequirement, RFxConstraint

    req = RFxRequirement(
        category="실적요건",
        description="공공기관 SI 2건 이상",
        is_mandatory=True,
        detail="건당 20억원 이상",
        constraints=[
            RFxConstraint(metric="contract_amount", op=">=", value=20.0, unit="KRW_100M", raw="건당 20억원 이상"),
        ]
    )
    analysis = RFxAnalysisResult.__new__(RFxAnalysisResult)
    analysis.title = "테스트"
    analysis.issuing_org = ""
    analysis.announcement_number = ""
    analysis.deadline = ""
    analysis.project_period = ""
    analysis.budget = ""
    analysis.document_type = "rfx"
    analysis.is_rfx_like = True
    analysis.document_gate_confidence = 0.9
    analysis.document_gate_reason = ""
    analysis.extraction_model = "gpt-4o-mini"
    analysis.requirements = [req]
    analysis.evaluation_criteria = []
    analysis.required_documents = []
    analysis.special_notes = []

    d = analysis.to_dict()
    req_dict = d["자격요건"][0]
    assert "constraints" in req_dict, "to_dict() 자격요건에 constraints 필드 없음"
    assert len(req_dict["constraints"]) == 1
    c = req_dict["constraints"][0]
    assert c["metric"] == "contract_amount"
    assert c["op"] == ">="
    assert c["value"] == 20.0
    assert c["unit"] == "KRW_100M"
    assert c["raw"] == "건당 20억원 이상"


def test_to_dict_empty_constraints_serialized():
    """constraints=[] 이어도 to_dict()에서 빈 배열로 포함되어야 함"""
    from rfx_analyzer import RFxAnalysisResult, RFxRequirement

    req = RFxRequirement(
        category="기술요건",
        description="ISO 인증",
        is_mandatory=False,
        detail="",
        constraints=[]
    )
    analysis = RFxAnalysisResult.__new__(RFxAnalysisResult)
    analysis.title = ""
    analysis.issuing_org = ""
    analysis.announcement_number = ""
    analysis.deadline = ""
    analysis.project_period = ""
    analysis.budget = ""
    analysis.document_type = "rfx"
    analysis.is_rfx_like = True
    analysis.document_gate_confidence = 0.9
    analysis.document_gate_reason = ""
    analysis.extraction_model = "gpt-4o-mini"
    analysis.requirements = [req]
    analysis.evaluation_criteria = []
    analysis.required_documents = []
    analysis.special_notes = []

    d = analysis.to_dict()
    req_dict = d["자격요건"][0]
    assert "constraints" in req_dict, "빈 constraints도 to_dict()에 포함되어야 함"
    assert req_dict["constraints"] == []


def test_general_prompt_includes_constraints_example():
    """_build_general_extraction_prompt()가 constraints 예시를 포함해야 함"""
    analyzer = RFxAnalyzer.__new__(RFxAnalyzer)
    prompt = analyzer._build_general_extraction_prompt("임의의 텍스트")
    assert "constraints" in prompt, (
        "_build_general_extraction_prompt에 constraints 예시 없음 "
        "(LLM이 constraints를 출력하지 않을 수 있음)"
    )
