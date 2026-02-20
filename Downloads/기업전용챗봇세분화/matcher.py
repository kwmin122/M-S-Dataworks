"""
RFx AI Assistant - 자격 매칭 엔진 (핵심 모듈)

회사 정보(RAG)와 RFx 자격요건을 매칭하여
자격 충족 여부를 판단하는 핵심 엔진.

⭐ 이 모듈이 이 시스템의 핵심 차별화 포인트입니다.
   "우리 회사가 이 공고에 자격이 되는가?"를 자동 판단.

Example:
    >>> matcher = QualificationMatcher(rag_engine, api_key="...")
    >>> result = matcher.match(rfx_analysis)
    >>> print(result.overall_score)  # 78%
    >>> print(result.gaps)  # ISO 인증 미보유
"""

import json
import os
import re
from typing import Any, Literal, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from engine import RAGEngine, SearchResult
from rfx_analyzer import RFxAnalysisResult, RFxRequirement, RFxConstraint, ConstraintMetric


# ============================================================
# STEP 0: 선언적 제약 평가기 (결정론적 비교 레이어)
# ============================================================

@dataclass
class ConstraintEvalResult:
    """단일 constraint 평가 결과 (내부 신호 전용)"""
    outcome: Literal["PASS", "FAIL", "SKIP"]
    reason: str = ""
    observed_value: Any = None


AggregateOutcome = Literal["DETERMINED_MET", "DETERMINED_NOT_MET", "FALLBACK_NEEDED"]

_VALID_METRICS = {m.value for m in ConstraintMetric}


class CompanyFactNormalizer:
    """컨텍스트 텍스트에서 metric 별 수치를 추출 (regex 기반, LLM 미호출).

    키워드 앵커링으로 오인식 방지:
    - amount: "계약금액/금액/사업비" 앞 N억 패턴만 추출
    - 동일 metric에서 서로 다른 값이 2개 이상 → None (SKIP, 모호)
    """

    # 금액: 계약 관련 키워드 앞에 오는 N억 (앵커링)
    _AMOUNT_ANCHOR_RE = re.compile(
        r"(?:계약금액|계약액|사업비|총액|금액|규모)[^\d]{0,8}(\d+(?:\.\d+)?)\s*억"
    )
    # fallback: N,NNN,NNN원 형식 (5자리 이상 숫자)
    _AMOUNT_PLAIN_RE = re.compile(r"([\d,]{5,})\s*원")
    _COUNT_RE        = re.compile(r"(\d+)\s*건")
    _HEAD_RE         = re.compile(r"(\d+)\s*명")
    _PERIOD_RE       = re.compile(r"(\d+)\s*년")
    _COMP_POS        = {"완료", "납품완료", "종료", "준공"}
    _COMP_NEG        = {"진행 중", "수행 중", "예정", "미완료"}

    def extract(self, context: str, metric: str) -> "float | bool | None":
        """metric에 해당하는 값을 context에서 추출. 실패/모호 시 None."""
        if metric == ConstraintMetric.CONTRACT_AMOUNT:
            return self._extract_amount(context)
        if metric == ConstraintMetric.PROJECT_COUNT:
            return self._extract_count(context)
        if metric == ConstraintMetric.HEADCOUNT:
            return self._extract_headcount(context)
        if metric == ConstraintMetric.PERIOD_YEARS:
            return self._extract_period(context)
        if metric == ConstraintMetric.COMPLETION_REQUIRED:
            return self._extract_completion(context)
        return None  # cert_grade, CUSTOM 등 → SKIP

    @staticmethod
    def _unique_or_none(values: list) -> "float | None":
        """값이 1종류만 있으면 반환. 서로 다른 값 2개 이상 → None (모호, SKIP)."""
        unique = set(values)
        return values[0] if len(unique) == 1 else None

    def _extract_amount(self, text: str) -> "float | None":
        # 앵커 패턴 우선
        hits = [float(m.group(1)) for m in self._AMOUNT_ANCHOR_RE.finditer(text)]
        if hits:
            return self._unique_or_none(hits)
        # fallback: N,NNN,NNN원
        m = self._AMOUNT_PLAIN_RE.search(text)
        if m:
            try:
                return float(m.group(1).replace(",", "")) / 1e8
            except ValueError:
                pass
        return None

    def _extract_count(self, text: str) -> "float | None":
        hits = [float(m.group(1)) for m in self._COUNT_RE.finditer(text)]
        return self._unique_or_none(hits) if hits else None

    def _extract_headcount(self, text: str) -> "float | None":
        hits = [float(m.group(1)) for m in self._HEAD_RE.finditer(text)]
        return self._unique_or_none(hits) if hits else None

    def _extract_period(self, text: str) -> "float | None":
        hits = [float(m.group(1)) for m in self._PERIOD_RE.finditer(text)]
        return self._unique_or_none(hits) if hits else None

    def _extract_completion(self, text: str) -> "bool | None":
        has_pos = any(kw in text for kw in self._COMP_POS)
        has_neg = any(kw in text for kw in self._COMP_NEG)
        if has_pos and has_neg:
            return None  # 충돌 → SKIP
        if has_pos:
            return True
        if has_neg:
            return False
        return None  # 정보 없음 → SKIP


class DeterministicComparator:
    """수치 비교 연산자 적용. in/not_in은 현재 미지원(SKIP)."""

    _OPS: dict = {
        ">=": lambda a, b: a >= b,
        ">":  lambda a, b: a >  b,
        "<=": lambda a, b: a <= b,
        "<":  lambda a, b: a <  b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def compare(self, constraint: RFxConstraint, observed: Any) -> ConstraintEvalResult:
        op_fn = self._OPS.get(constraint.op)
        if op_fn is None:
            return ConstraintEvalResult("SKIP", f"op '{constraint.op}' 미지원", observed)
        try:
            passed = op_fn(float(observed), float(constraint.value))
            return ConstraintEvalResult(
                "PASS" if passed else "FAIL",
                observed_value=observed,
            )
        except (TypeError, ValueError) as exc:
            return ConstraintEvalResult("SKIP", f"수치 변환 실패: {exc}", observed)


class ConstraintEvaluator:
    """
    constraints 목록을 컨텍스트에 대해 평가하고 집계 결과를 반환.

    - CUSTOM metric → 항상 SKIP
    - 파싱 실패 → SKIP (강제 미충족 금지)
    - FAIL ≥ 1 → DETERMINED_NOT_MET
    - 전부 PASS → DETERMINED_MET
    - SKIP ≥ 1 + FAIL = 0 → FALLBACK_NEEDED
    """

    def __init__(self) -> None:
        self._normalizer = CompanyFactNormalizer()
        self._comparator = DeterministicComparator()

    def evaluate(
        self, constraints: list, context: str
    ) -> list:
        results: list[ConstraintEvalResult] = []
        for c in constraints:
            # CUSTOM 또는 미등록 metric → SKIP
            if c.metric == ConstraintMetric.CUSTOM or c.metric not in _VALID_METRICS:
                results.append(ConstraintEvalResult("SKIP", f"CUSTOM: {c.raw}"))
                continue
            # in/not_in 집합 연산 → SKIP (미구현)
            if c.op in ("in", "not_in"):
                results.append(ConstraintEvalResult("SKIP", f"집합 op '{c.op}' 미지원"))
                continue
            observed = self._normalizer.extract(context, c.metric)
            if observed is None:
                results.append(ConstraintEvalResult("SKIP", f"'{c.metric}' 파싱 실패"))
                continue
            result = self._comparator.compare(c, observed)
            results.append(result)
        return results

    @staticmethod
    def aggregate(results: list) -> str:
        if not results:
            return "FALLBACK_NEEDED"
        if any(r.outcome == "FAIL" for r in results):
            return "DETERMINED_NOT_MET"
        if any(r.outcome == "SKIP" for r in results):
            return "FALLBACK_NEEDED"
        return "DETERMINED_MET"


# ============================================================
# STEP 1: 매칭 상태 정의
# ============================================================

class MatchStatus(Enum):
    """자격요건 매칭 상태"""
    MET = "충족"              # ✅ 완전 충족
    PARTIALLY_MET = "부분충족"  # 🟡 일부 충족
    NOT_MET = "미충족"         # ❌ 미충족
    UNKNOWN = "판단불가"       # ❓ 정보 부족


MATCH_JUDGMENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["충족", "부분충족", "미충족", "판단불가"],
        },
        "evidence": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "preparation_guide": {"type": "string"},
    },
    "required": ["status", "evidence", "confidence", "preparation_guide"],
}

OPINION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "opinion": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 0,
            "maxItems": 4,
        },
        "risk_notes": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 0,
            "maxItems": 2,
        },
    },
    "required": ["opinion", "actions", "risk_notes"],
}

OPINION_MODE_GUIDANCE: dict[str, str] = {
    "conservative": (
        "리스크를 우선하여 보수적으로 조언하세요. 단정 표현을 피하고 '선확인 -> 보완 -> 검토' 순서로 안내하세요. "
        "확인되지 않은 사실은 반드시 조건부 표현으로 처리하세요."
    ),
    "balanced": (
        "기회와 리스크를 균형 있게 제시하세요. 결론-근거-실행 항목이 자연스럽게 이어지도록 작성하고 "
        "불확실성은 명확히 표시하세요."
    ),
    "aggressive": (
        "참여 가능성을 높이는 방향으로 제안하세요. 다만 근거 없는 단정은 금지하고, "
        "도전 시 필요한 최소 전제조건과 주의사항을 함께 제시하세요."
    ),
}

BALANCED_VARIANT_GUIDANCE: dict[str, str] = {
    "a": (
        "균형형 A안(결론 우선형): 첫 문장을 결론으로 시작하고, 그 뒤에 핵심 근거 2개와 "
        "즉시 실행 액션으로 연결하세요. 문장은 짧고 명료하게 유지하세요."
    ),
    "b": (
        "균형형 B안(리스크 관리형): 리스크/전제조건을 먼저 제시한 뒤, 대안 비교와 실행 순서를 "
        "안정적으로 안내하세요. 과도한 낙관 표현은 피하세요."
    ),
}


# ============================================================
# STEP 2: 매칭 결과 데이터 클래스
# ============================================================

@dataclass
class RequirementMatch:
    """개별 자격요건 매칭 결과"""
    requirement: RFxRequirement  # 원본 요건
    status: MatchStatus          # 매칭 상태
    evidence: str = ""           # 판단 근거 (회사 정보에서 찾은 증거)
    confidence: float = 0.0      # 신뢰도 (0.0 ~ 1.0)
    preparation_guide: str = ""  # 미충족 시 준비 가이드
    source_files: list[str] = field(default_factory=list)  # 증거 출처


@dataclass
class MatchingResult:
    """전체 매칭 분석 결과"""
    # RFx 기본 정보
    rfx_title: str = ""
    rfx_org: str = ""
    
    # 개별 요건 매칭 결과
    matches: list[RequirementMatch] = field(default_factory=list)
    
    # 종합 점수
    overall_score: float = 0.0  # 0 ~ 100%
    evaluation_expected_score: float = 0.0
    evaluation_total_score: float = 0.0
    technical_expected_score: float = 0.0
    price_expected_score: float = 0.0
    bonus_expected_score: float = 0.0
    evaluation_available: bool = False
    evaluation_notes: list[str] = field(default_factory=list)
    
    # 요약
    summary: str = ""
    recommendation: str = ""  # GO / NO-GO / CONDITIONAL
    assistant_opinions: dict[str, dict[str, Any]] = field(default_factory=dict)
    opinion_mode: str = "balanced"
    
    @property
    def met_count(self) -> int:
        return sum(1 for m in self.matches if m.status == MatchStatus.MET)
    
    @property
    def not_met_count(self) -> int:
        return sum(1 for m in self.matches if m.status == MatchStatus.NOT_MET)
    
    @property
    def partially_met_count(self) -> int:
        return sum(1 for m in self.matches if m.status == MatchStatus.PARTIALLY_MET)
    
    @property
    def unknown_count(self) -> int:
        return sum(1 for m in self.matches if m.status == MatchStatus.UNKNOWN)
    
    @property
    def gaps(self) -> list[RequirementMatch]:
        """미충족 요건 리스트"""
        return [m for m in self.matches if m.status in [MatchStatus.NOT_MET, MatchStatus.PARTIALLY_MET]]
    
    @property
    def mandatory_gaps(self) -> list[RequirementMatch]:
        """필수 미충족 요건"""
        return [m for m in self.gaps if m.requirement.is_mandatory]
    
    def to_report(self) -> str:
        """분석 결과 리포트 생성"""
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"📋 입찰 자격 분석 리포트")
        lines.append(f"{'='*60}")
        lines.append(f"공고명: {self.rfx_title}")
        lines.append(f"발주기관: {self.rfx_org}")
        lines.append(f"{'─'*60}")
        
        # 종합 점수
        score_emoji = "🟢" if self.overall_score >= 80 else "🟡" if self.overall_score >= 50 else "🔴"
        lines.append(f"\n{score_emoji} 종합 적합도: {self.overall_score:.0f}%")
        if self.evaluation_available and self.evaluation_total_score > 0:
            lines.append(
                f"📈 평가예상점수: {self.evaluation_expected_score:.1f} / {self.evaluation_total_score:.1f}"
            )
            lines.append(
                "   └ 기술/가격/가점: "
                f"{self.technical_expected_score:.1f} / {self.price_expected_score:.1f} / {self.bonus_expected_score:.1f}"
            )
        lines.append(f"추천: {self.recommendation}")
        lines.append(f"\n📊 요건 분석 현황:")
        lines.append(f"  ✅ 충족: {self.met_count}개")
        lines.append(f"  🟡 부분충족: {self.partially_met_count}개")
        lines.append(f"  ❌ 미충족: {self.not_met_count}개")
        lines.append(f"  ❓ 판단불가: {self.unknown_count}개")
        
        # 상세 매칭 결과
        lines.append(f"\n{'─'*60}")
        lines.append("📝 상세 분석 결과:\n")
        
        for i, match in enumerate(self.matches, 1):
            status_emoji = {
                MatchStatus.MET: "✅",
                MatchStatus.PARTIALLY_MET: "🟡",
                MatchStatus.NOT_MET: "❌",
                MatchStatus.UNKNOWN: "❓"
            }[match.status]
            
            mandatory = "🔴필수" if match.requirement.is_mandatory else "🟢권장"
            lines.append(f"{i}. {status_emoji} [{mandatory}] {match.requirement.description}")
            lines.append(f"   분류: {match.requirement.category}")
            lines.append(f"   상태: {match.status.value} (신뢰도: {match.confidence:.0%})")
            
            if match.evidence:
                lines.append(f"   근거: {match.evidence}")
            
            if match.preparation_guide:
                lines.append(f"   📌 준비사항: {match.preparation_guide}")
            
            lines.append("")
        
        # GAP 분석 요약
        if self.gaps:
            lines.append(f"{'─'*60}")
            lines.append("🔍 GAP 분석 (보완 필요 항목):\n")
            for gap in self.gaps:
                lines.append(f"  • {gap.requirement.description}")
                if gap.preparation_guide:
                    lines.append(f"    → {gap.preparation_guide}")
                lines.append("")
        
        # 요약
        lines.append(f"{'─'*60}")
        lines.append(f"\n💡 종합 의견:")
        lines.append(self.summary)

        selected_mode = self.opinion_mode if self.opinion_mode in self.assistant_opinions else "balanced"
        if selected_mode not in self.assistant_opinions and self.assistant_opinions:
            selected_mode = next(iter(self.assistant_opinions.keys()))
        opinion_payload = self.assistant_opinions.get(selected_mode, {})
        opinion_text = str(opinion_payload.get("opinion", "")).strip()
        opinion_actions = [
            str(item).strip()
            for item in opinion_payload.get("actions", [])
            if str(item).strip()
        ][:4]
        risk_notes = [
            str(item).strip()
            for item in opinion_payload.get("risk_notes", [])
            if str(item).strip()
        ][:2]

        if opinion_text or opinion_actions or risk_notes:
            mode_label = {
                "conservative": "보수적",
                "balanced": "균형",
                "aggressive": "공격적",
            }.get(selected_mode, selected_mode)
            lines.append(f"\n🤖 Kira 의견 ({mode_label})")
            if opinion_text:
                lines.append(opinion_text)
            if opinion_actions:
                lines.append("\n📋 다음 할 일:")
                for action in opinion_actions:
                    lines.append(f"  - [ ] {action}")
            if risk_notes:
                lines.append("\n⚠️ 주의할 점:")
                for note in risk_notes:
                    lines.append(f"  - {note}")
            lines.append("\n⚠️ Kira의 의견은 AI 참고용이며, 최종 판단은 담당자께서 해주세요.")
        lines.append(f"\n{'='*60}")
        
        return "\n".join(lines)


# ============================================================
# STEP 3: 자격 매칭 엔진
# ============================================================

class QualificationMatcher:
    """
    회사 정보(RAG)와 RFx 자격요건을 매칭하여
    자격 충족 여부를 판단하는 핵심 엔진.
    
    작동 흐름:
    1. RFx에서 추출된 각 자격요건에 대해
    2. RAG로 회사 정보 검색
    3. LLM으로 충족 여부 판단
    4. GAP 분석 및 준비 가이드 생성
    """
    
    def __init__(
        self,
        rag_engine: RAGEngine,
        api_key: str,
        model: str = "gpt-4o-mini"
    ):
        """
        Args:
            rag_engine (RAGEngine): 회사 정보가 저장된 RAG 엔진
            api_key (str): OpenAI API 키
            model (str): 사용할 LLM 모델
        """
        self.rag = rag_engine
        self.api_key = api_key
        self.model = model
        self.opinion_enabled = os.getenv("KIRA_OPINION_ENABLED", "1").strip() == "1"
        self.opinion_model = os.getenv("KIRA_OPINION_MODEL", self.model).strip() or self.model
        try:
            self.opinion_temperature = float(os.getenv("KIRA_OPINION_TEMPERATURE", "0.2"))
        except ValueError:
            self.opinion_temperature = 0.2
        self.opinion_temperature = max(0.0, min(1.0, self.opinion_temperature))
        self.opinion_ab_enabled = os.getenv("KIRA_OPINION_AB_ENABLED", "1").strip() == "1"
        self.strict_json_only = os.getenv("OPENAI_STRICT_JSON_ONLY", "1").strip().lower() not in {
            "0",
            "false",
            "off",
            "no",
        }
        self.balanced_variant_default = self._normalize_balanced_variant(
            os.getenv("KIRA_OPINION_BALANCED_VARIANT", "a")
        )
        self._init_llm()
    
    def _init_llm(self) -> None:
        """LLM 초기화"""
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)

    def _chat(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """OpenAI Chat Completions 호출"""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return (response.choices[0].message.content or "").strip()

    def _chat_json(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        schema_name: str,
        schema: dict[str, Any],
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """OpenAI Structured Outputs(json_schema strict) 호출"""
        response = self.client.chat.completions.create(
            model=model or self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            messages=[{"role": "user", "content": prompt}],
        )
        content = (response.choices[0].message.content or "").strip()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Structured Output이 객체(dict) 형식이 아닙니다.")
        return parsed

    @staticmethod
    def _extract_json_block(response_text: str) -> str:
        """LLM 응답에서 JSON 블록 추출"""
        text = response_text.strip()
        if "```json" in text:
            return text.split("```json", 1)[1].split("```", 1)[0].strip()
        if "```" in text:
            return text.split("```", 1)[1].split("```", 1)[0].strip()
        return text

    @staticmethod
    def _normalize_opinion_mode(mode: str) -> str:
        normalized = str(mode or "").strip().lower()
        alias = {
            "보수적": "conservative",
            "conservative": "conservative",
            "균형": "balanced",
            "balanced": "balanced",
            "공격적": "aggressive",
            "aggressive": "aggressive",
        }
        return alias.get(normalized, "balanced")

    @staticmethod
    def _normalize_balanced_variant(variant: str) -> str:
        normalized = str(variant or "").strip().lower()
        if normalized in {"a", "결론", "결론우선", "결론우선형"}:
            return "a"
        if normalized in {"b", "리스크", "리스크관리", "리스크관리형"}:
            return "b"
        return "a"

    def _resolve_balanced_variant(self, variant: Optional[str]) -> str:
        if variant is None or not str(variant).strip():
            return self.balanced_variant_default
        return self._normalize_balanced_variant(variant)

    def _opinion_cache_key(self, mode: str, balanced_variant: Optional[str] = None) -> str:
        normalized_mode = self._normalize_opinion_mode(mode)
        if normalized_mode != "balanced":
            return normalized_mode
        if balanced_variant is None:
            return "balanced"
        return f"balanced_{self._normalize_balanced_variant(balanced_variant)}"

    @staticmethod
    def _parse_match_status(raw_status: str) -> MatchStatus:
        """LLM 변형 응답을 안전하게 MatchStatus로 변환"""
        normalized = (
            str(raw_status or "")
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
            .replace("/", "")
        )
        if not normalized:
            return MatchStatus.UNKNOWN

        # 1) 완전 일치 우선
        exact_alias = {
            "충족": MatchStatus.MET,
            "충족됨": MatchStatus.MET,
            "완전충족": MatchStatus.MET,
            "met": MatchStatus.MET,
            "satisfied": MatchStatus.MET,
            "eligible": MatchStatus.MET,
            "부분충족": MatchStatus.PARTIALLY_MET,
            "부분충족됨": MatchStatus.PARTIALLY_MET,
            "partial": MatchStatus.PARTIALLY_MET,
            "partiallymet": MatchStatus.PARTIALLY_MET,
            "partiallysatisfied": MatchStatus.PARTIALLY_MET,
            "미충족": MatchStatus.NOT_MET,
            "불충족": MatchStatus.NOT_MET,
            "notmet": MatchStatus.NOT_MET,
            "ineligible": MatchStatus.NOT_MET,
            "판단불가": MatchStatus.UNKNOWN,
            "unknown": MatchStatus.UNKNOWN,
            "na": MatchStatus.UNKNOWN,
            "n/a": MatchStatus.UNKNOWN,
        }
        if normalized in exact_alias:
            return exact_alias[normalized]

        # 2) 포함 매칭은 부정 상태를 먼저 검사하여 오판정을 방지
        if any(token in normalized for token in ["notmet", "미충족", "불충족", "ineligible"]):
            return MatchStatus.NOT_MET
        if any(token in normalized for token in ["부분충족", "partial"]):
            return MatchStatus.PARTIALLY_MET
        if any(token in normalized for token in ["충족", "satisfied", "eligible", "met"]):
            return MatchStatus.MET
        if any(token in normalized for token in ["판단불가", "unknown", "na"]):
            return MatchStatus.UNKNOWN

        return MatchStatus.UNKNOWN

    @staticmethod
    def _safe_confidence(raw_confidence: object) -> float:
        """confidence 값을 0.0~1.0 범위로 정규화"""
        try:
            value = float(raw_confidence)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    @staticmethod
    def _contains_any(text: str, keywords: list[str]) -> bool:
        """텍스트에 키워드 목록 중 하나라도 포함되는지 확인"""
        lowered = str(text or "").lower()
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _is_consortium_share_requirement(req: RFxRequirement) -> bool:
        """
        컨소시엄 실적의 참여지분/분담금 인정 규칙인지 판별.

        이 요건은 회사의 '보유/미보유'보다,
        실적 계산 규칙 준수 여부 확인 성격이 강하므로 규칙형 판단을 우선 적용한다.
        """
        text = f"{req.category} {req.description} {req.detail}".lower()
        has_consortium = any(token in text for token in ["컨소시엄", "공동수급", "consortium", "joint venture", "joint-venture"])
        has_share = any(token in text for token in ["분담", "지분", "참여지분", "share", "contribution", "portion"])
        return has_consortium and has_share

    def _apply_rule_based_judgment(
        self,
        req: RFxRequirement,
        context: str,
    ) -> Optional[dict[str, Any]]:
        """
        반복적으로 오판정이 발생하는 요건을 규칙형으로 선판단.
        반환값이 None이면 기존 LLM 판단 흐름으로 진행.
        """
        if not self._is_consortium_share_requirement(req):
            return None

        consortium_keywords = ["컨소시엄", "공동수급", "consortium", "joint venture", "joint-venture"]
        share_keywords = ["분담금", "참여지분", "지분", "share", "contribution", "portion"]

        has_consortium = self._contains_any(context, consortium_keywords)
        has_share = self._contains_any(context, share_keywords)

        if has_consortium and has_share:
            return {
                "status": "충족",
                "evidence": "회사 정보에 컨소시엄 실적과 참여지분/분담금 기준이 함께 명시되어 있습니다.",
                "confidence": 0.95,
                "preparation_guide": "",
            }

        if has_consortium:
            return {
                "status": "부분충족",
                "evidence": "컨소시엄 실적 언급은 있으나 참여지분/분담금 정보가 불명확합니다.",
                "confidence": 0.75,
                "preparation_guide": "컨소시엄 실적별 참여지분(분담금) 증빙을 명시해 제출하세요.",
            }

        return {
            "status": "판단불가",
            "evidence": "검색된 회사 정보에서 컨소시엄 실적 관련 근거를 찾지 못했습니다.",
            "confidence": 0.4,
            "preparation_guide": "컨소시엄 수행실적 및 참여지분(분담금) 증빙을 추가하세요.",
        }
    
    # ============================================================
    # STEP 4: 메인 매칭 함수
    # ============================================================
    
    def match(self, rfx_analysis: RFxAnalysisResult) -> MatchingResult:
        """
        RFx 분석 결과와 회사 정보를 매칭하여 자격 판단을 수행한다.
        
        이것이 이 시스템의 핵심 기능입니다.
        
        Args:
            rfx_analysis (RFxAnalysisResult): RFx 문서 분석 결과
            
        Returns:
            MatchingResult: 매칭 분석 결과
        """
        result = MatchingResult(
            rfx_title=rfx_analysis.title,
            rfx_org=rfx_analysis.issuing_org
        )
        
        if not rfx_analysis.requirements:
            result.summary = "분석할 자격요건이 없습니다."
            result.recommendation = "UNKNOWN"
            return result
        
        # STEP 4-1: 각 자격요건별 매칭 수행
        for req in rfx_analysis.requirements:
            match = self._match_single_requirement(req)
            result.matches.append(match)
        
        # STEP 4-2: 종합 점수 산출
        result.overall_score = self._calculate_overall_score(result.matches)

        # STEP 4-3: 추천 판단 (GO / NO-GO / CONDITIONAL)
        result.recommendation = self._determine_recommendation(result)

        # STEP 4-4: 평가표 기반 예상 점수 산출
        self._calculate_expected_evaluation_score(result, rfx_analysis)

        # STEP 4-5: 종합 요약 생성
        result.summary = self._generate_summary(result, rfx_analysis)

        # STEP 4-6: Kira 의견(balanced) 선생성
        if self.opinion_enabled:
            self.generate_opinion_for_mode(
                result=result,
                rfx=rfx_analysis,
                mode="balanced",
            )
        
        return result
    
    # ============================================================
    # STEP 5: 개별 요건 매칭
    # ============================================================
    
    def _match_single_requirement(self, req: RFxRequirement) -> RequirementMatch:
        """
        개별 자격요건에 대해 회사 정보를 검색하고 충족 여부를 판단한다.
        
        Args:
            req (RFxRequirement): 자격요건
            
        Returns:
            RequirementMatch: 매칭 결과
        """
        # STEP 5-1: RAG 검색 - 회사 정보에서 관련 내용 찾기
        search_query = f"{req.category} {req.description} {req.detail}"
        search_results = self.rag.search(search_query, top_k=5)
        
        # STEP 5-2: 검색 결과가 없으면 판단불가
        if not search_results:
            return RequirementMatch(
                requirement=req,
                status=MatchStatus.UNKNOWN,
                evidence="회사 정보에서 관련 내용을 찾을 수 없습니다.",
                confidence=0.0,
                preparation_guide="해당 자격에 대한 회사 정보를 추가해주세요."
            )
        
        # STEP 5-3: LLM으로 충족 여부 판단
        context = "\n---\n".join([r.text for r in search_results])
        source_files = list(set(r.source_file for r in search_results))

        # STEP 5-3A-0: 선언적 제약 평가기 (constraints가 있으면 결정론 비교 우선)
        if req.constraints:
            evaluator = ConstraintEvaluator()
            eval_results = evaluator.evaluate(req.constraints, context)
            aggregate = ConstraintEvaluator.aggregate(eval_results)

            if aggregate == "DETERMINED_NOT_MET":
                evidence_parts = [
                    f"{c.raw}: 기준={c.value}{c.unit}, 실제={r.observed_value}"
                    for c, r in zip(req.constraints, eval_results)
                    if r.outcome == "FAIL"
                ]
                return RequirementMatch(
                    requirement=req,
                    status=MatchStatus.NOT_MET,
                    evidence="; ".join(evidence_parts) or "정량 기준 미달",
                    confidence=0.95,
                    preparation_guide="제시된 기준을 충족하는 실적/자격을 준비하세요.",
                    source_files=source_files,
                )
            elif aggregate == "DETERMINED_MET":
                return RequirementMatch(
                    requirement=req,
                    status=MatchStatus.MET,
                    evidence="정량 조건 모두 충족",
                    confidence=0.95,
                    preparation_guide="",
                    source_files=source_files,
                )
            # FALLBACK_NEEDED → 아래 기존 경로 계속

        # STEP 5-3A: 규칙형 판정이 가능한 요건은 LLM보다 먼저 처리
        judgment = self._apply_rule_based_judgment(req, context)
        if judgment is None:
            # STEP 5-3B: 일반 요건은 LLM으로 판단
            judgment = self._judge_with_llm(req, context)
        judgment["source_files"] = source_files
        
        return RequirementMatch(
            requirement=req,
            status=self._parse_match_status(judgment.get("status", "판단불가")),
            evidence=judgment.get("evidence", ""),
            confidence=self._safe_confidence(judgment.get("confidence", 0.0)),
            preparation_guide=judgment.get("preparation_guide", ""),
            source_files=source_files
        )
    
    def _judge_with_llm(self, req: RFxRequirement, context: str) -> dict:
        """
        LLM을 사용하여 자격요건 충족 여부를 판단한다.
        
        Args:
            req (RFxRequirement): 자격요건
            context (str): RAG에서 검색된 회사 정보
            
        Returns:
            dict: 판단 결과
        """
        prompt = f"""당신은 입찰 자격 판단 전문가입니다.

아래 [자격요건]에 대해 [회사 정보]를 바탕으로 충족 여부를 판단해주세요.

[자격요건]
- 분류: {req.category}
- 요건: {req.description}
- 상세: {req.detail}
- 필수 여부: {"필수" if req.is_mandatory else "권장"}

[회사 정보 (검색 결과)]
{context}

반드시 아래 JSON 형식으로만 응답해주세요:
```json
{{
    "status": "충족|부분충족|미충족|판단불가",
    "evidence": "판단 근거 (회사 정보에서 찾은 구체적 증거)",
    "confidence": 0.0에서 1.0 사이의 신뢰도 숫자,
    "preparation_guide": "미충족이거나 부분충족인 경우 구체적인 준비 방법. 충족이면 빈 문자열."
}}
```

판단 기준:
1. "충족": 회사 정보에서 해당 자격을 명확히 확인할 수 있음
2. "부분충족": 일부는 확인되나 완전하지 않음 (예: 유사 인증은 있으나 정확히 일치하지 않음)
3. "미충족": 회사 정보에서 해당 자격이 없거나 부재가 확인됨
        4. "판단불가": 회사 정보가 부족하여 판단할 수 없음

        보수적으로 판단하되, 확실한 증거가 있으면 "충족"으로 판단하세요."""

        try:
            return self._chat_json(
                prompt=prompt,
                max_tokens=1024,
                temperature=0.1,
                schema_name="qualification_judgment",
                schema=MATCH_JUDGMENT_JSON_SCHEMA,
            )
            
        except Exception as e:
            if self.strict_json_only:
                return {
                    "status": "판단불가",
                    "evidence": f"Structured Output 판단 실패(strict 모드): {str(e)}",
                    "confidence": 0.0,
                    "preparation_guide": "수동 확인이 필요합니다.",
                }
            # Structured Outputs가 불가한 조합에서는 기존 JSON 파싱 경로로 폴백
            try:
                response_text = self._chat(prompt=prompt, max_tokens=1024, temperature=0.1)
                json_text = self._extract_json_block(response_text)
                return json.loads(json_text.strip())
            except Exception as fallback_error:
                print(f"⚠️ LLM 판단 오류: {e} / fallback 오류: {fallback_error}")
                return {
                    "status": "판단불가",
                    "evidence": f"자동 판단 중 오류 발생: {str(fallback_error)}",
                    "confidence": 0.0,
                    "preparation_guide": "수동 확인이 필요합니다."
                }
    
    # ============================================================
    # STEP 6: 종합 점수 산출
    # ============================================================
    
    def _calculate_overall_score(self, matches: list[RequirementMatch]) -> float:
        """
        종합 적합도 점수를 산출한다.
        
        가중치:
        - 필수 요건: 가중치 2.0
        - 권장 요건: 가중치 1.0
        
        상태별 점수:
        - 충족: 100%
        - 부분충족: 50%
        - 미충족: 0%
        - 판단불가: 30% (보수적)
        """
        if not matches:
            return 0.0
        
        total_weight = 0.0
        total_score = 0.0
        
        status_scores = {
            MatchStatus.MET: 1.0,
            MatchStatus.PARTIALLY_MET: 0.5,
            MatchStatus.NOT_MET: 0.0,
            MatchStatus.UNKNOWN: 0.3
        }
        
        for match in matches:
            weight = 2.0 if match.requirement.is_mandatory else 1.0
            score = status_scores.get(match.status, 0.0)
            
            total_weight += weight
            total_score += weight * score
        
        return (total_score / total_weight * 100) if total_weight > 0 else 0.0
    
    # ============================================================
    # STEP 7: 평가표 기반 예상 점수
    # ============================================================

    def _calculate_expected_evaluation_score(
        self,
        result: MatchingResult,
        rfx: RFxAnalysisResult
    ) -> None:
        """평가기준(기술/가격/가점) 기반 예상 점수 계산"""
        criteria = rfx.evaluation_criteria or []
        if not criteria:
            result.evaluation_available = False
            return

        def normalize(value: str) -> str:
            return str(value or "").strip().lower()

        technical_total = 0.0
        price_total = 0.0
        bonus_total = 0.0
        other_total = 0.0

        for crit in criteria:
            score = max(0.0, float(crit.score or 0.0))
            category_text = normalize(crit.category)
            item_text = normalize(crit.item)
            detail_text = normalize(crit.detail)
            merged_text = f"{category_text} {item_text} {detail_text}"

            if "가격" in merged_text:
                price_total += score
            elif any(token in merged_text for token in ["가점", "우대", "bonus"]):
                bonus_total += score
            elif any(token in merged_text for token in ["기술", "정성", "정량", "수행"]):
                technical_total += score
            else:
                other_total += score

        total_score = technical_total + price_total + bonus_total + other_total
        if total_score <= 0:
            result.evaluation_available = False
            return

        status_weights = {
            MatchStatus.MET: 1.0,
            MatchStatus.PARTIALLY_MET: 0.5,
            MatchStatus.NOT_MET: 0.0,
            MatchStatus.UNKNOWN: 0.3,
        }
        if result.matches:
            fit_ratio = sum(status_weights.get(m.status, 0.0) for m in result.matches) / len(result.matches)
        else:
            fit_ratio = 0.0

        # 가격점수는 입찰가 정보가 없으므로 중립 가정치 사용
        price_assumption = 0.7

        technical_score = technical_total * fit_ratio
        bonus_score = bonus_total * fit_ratio
        other_score = other_total * fit_ratio
        price_score = price_total * price_assumption

        result.technical_expected_score = technical_score + other_score
        result.price_expected_score = price_score
        result.bonus_expected_score = bonus_score
        result.evaluation_expected_score = (
            result.technical_expected_score + result.price_expected_score + result.bonus_expected_score
        )
        result.evaluation_total_score = total_score
        result.evaluation_available = True
        result.evaluation_notes = [
            "가격점수는 입찰가 정보 미입력 상태에서 중립 가정치(70%)를 사용했습니다.",
            "기술/가점은 자격 매칭 결과 기반 추정치입니다.",
        ]

    # ============================================================
    # STEP 8: GO/NO-GO 추천
    # ============================================================
    
    def _determine_recommendation(self, result: MatchingResult) -> str:
        """입찰 참여 추천 판단"""
        
        # 필수 요건 미충족이 있으면 NO-GO
        mandatory_not_met = [
            m for m in result.matches
            if m.requirement.is_mandatory and m.status == MatchStatus.NOT_MET
        ]
        
        if mandatory_not_met:
            return f"🔴 NO-GO (필수 요건 {len(mandatory_not_met)}개 미충족)"

        # 필수 요건이 부분충족/판단불가면 선확인 필요
        mandatory_uncertain = [
            m for m in result.matches
            if m.requirement.is_mandatory and m.status in [MatchStatus.PARTIALLY_MET, MatchStatus.UNKNOWN]
        ]
        if mandatory_uncertain:
            return f"🟡 CONDITIONAL - 필수 요건 {len(mandatory_uncertain)}개 증빙 확인 필요"
        
        # 점수 기반 판단
        if result.overall_score >= 80:
            return "🟢 GO - 적극 참여 권장"
        elif result.overall_score >= 60:
            return "🟡 CONDITIONAL - 보완 후 참여 가능"
        elif result.overall_score >= 40:
            return "🟠 RISKY - 상당한 보완 필요"
        else:
            return "🔴 NO-GO - 참여 비권장"
    
    # ============================================================
    # STEP 9: 종합 요약 생성
    # ============================================================
    
    def _generate_summary(
        self,
        result: MatchingResult,
        rfx: RFxAnalysisResult
    ) -> str:
        """LLM으로 종합 분석 요약을 생성한다."""
        
        # 매칭 결과 요약 텍스트 구성
        matches_summary = []
        for m in result.matches:
            emoji = {"충족": "✅", "부분충족": "🟡", "미충족": "❌", "판단불가": "❓"}
            status = m.status.value
            matches_summary.append(
                f"- {emoji.get(status, '?')} {m.requirement.description}: {status}"
            )
        
        prompt = f"""아래 입찰 자격 분석 결과를 바탕으로 한국어로 간결하게 종합 의견을 작성해주세요.
3-5문장으로 핵심만 요약해주세요.

공고명: {rfx.title}
발주기관: {rfx.issuing_org}
종합 점수: {result.overall_score:.0f}%
추천: {result.recommendation}

매칭 결과:
{chr(10).join(matches_summary)}

GAP (보완 필요):
{chr(10).join(f'- {g.requirement.description}: {g.preparation_guide}' for g in result.gaps) or '없음'}
"""
        
        try:
            return self._chat(prompt=prompt, max_tokens=500, temperature=0.3)
        except Exception as e:
            return f"종합 분석 요약 생성 실패: {e}"

    def _generate_assistant_opinion(
        self,
        mode: str,
        result: MatchingResult,
        rfx: RFxAnalysisResult,
        balanced_variant: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Kira 의견(개인 비서형) 생성.
        Structured Outputs(json_schema strict)로 형식을 강제한다.
        """
        normalized_mode = self._normalize_opinion_mode(mode)
        mode_guidance = OPINION_MODE_GUIDANCE.get(normalized_mode, OPINION_MODE_GUIDANCE["balanced"])
        variant = self._resolve_balanced_variant(balanced_variant)
        variant_guidance = ""
        if normalized_mode == "balanced" and self.opinion_ab_enabled:
            variant_guidance = BALANCED_VARIANT_GUIDANCE.get(variant, BALANCED_VARIANT_GUIDANCE["a"])

        matches_summary: list[str] = []
        for match in result.matches[:8]:
            mandatory = "필수" if match.requirement.is_mandatory else "권장"
            matches_summary.append(
                f"- [{mandatory}] {match.requirement.description} => {match.status.value}"
            )

        gaps_summary = [
            f"- {gap.requirement.description}: {gap.preparation_guide or '보완 필요'}"
            for gap in result.gaps[:6]
        ]

        prompt = f"""당신은 입찰 실무 담당자를 돕는 개인 비서입니다.
반드시 JSON으로만 응답하세요.

작성 목표:
- 사실 요약이 아니라, 실무자가 바로 행동할 수 있는 의견을 제공합니다.
- 근거 없는 추정/단정은 금지합니다.
- {mode_guidance}
- {variant_guidance or "기본 균형형 문체를 사용하세요."}

출력 규칙:
1) opinion: 5~8문장 한국어 의견
2) actions: 즉시 실행 가능한 체크리스트 3~4개
3) risk_notes: 주의할 점 1~2개

[문서 정보]
- 공고명: {rfx.title}
- 발주기관: {rfx.issuing_org}

[분석 결과]
- 종합 적합도: {result.overall_score:.0f}%
- 추천: {result.recommendation}
- 충족/부분충족/미충족/판단불가: {result.met_count}/{result.partially_met_count}/{result.not_met_count}/{result.unknown_count}
- 평가예상점수: {result.evaluation_expected_score:.1f}/{result.evaluation_total_score:.1f}

[매칭 요약]
{chr(10).join(matches_summary) if matches_summary else "- 요건 정보 없음"}

[GAP 요약]
{chr(10).join(gaps_summary) if gaps_summary else "- 주요 GAP 없음"}
"""

        try:
            parsed = self._chat_json(
                prompt=prompt,
                max_tokens=900,
                temperature=self.opinion_temperature,
                schema_name=f"kira_opinion_{normalized_mode}",
                schema=OPINION_JSON_SCHEMA,
                model=self.opinion_model,
            )
            opinion = str(parsed.get("opinion", "")).strip()
            actions = [
                str(item).strip()
                for item in parsed.get("actions", [])
                if str(item).strip()
            ][:4]
            risk_notes = [
                str(item).strip()
                for item in parsed.get("risk_notes", [])
                if str(item).strip()
            ][:2]

            return {
                "opinion": opinion,
                "actions": actions,
                "risk_notes": risk_notes,
                "variant": variant if normalized_mode == "balanced" else "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            return {
                "opinion": "",
                "actions": [],
                "risk_notes": [],
                "variant": variant if normalized_mode == "balanced" else "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

    def generate_opinion_for_mode(
        self,
        result: MatchingResult,
        rfx: RFxAnalysisResult,
        mode: str,
        balanced_variant: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        모드별 Kira 의견을 생성하고 result.assistant_opinions 캐시에 저장한다.
        이미 캐시된 모드는 재호출하지 않는다.
        """
        normalized_mode = self._normalize_opinion_mode(mode)
        resolved_variant = self._resolve_balanced_variant(balanced_variant) if normalized_mode == "balanced" else None
        cache_key = self._opinion_cache_key(
            normalized_mode,
            None if balanced_variant is None else resolved_variant,
        )
        cached = result.assistant_opinions.get(cache_key)
        if isinstance(cached, dict) and (
            str(cached.get("opinion", "")).strip()
            or cached.get("actions")
            or cached.get("risk_notes")
        ):
            result.opinion_mode = normalized_mode
            return cached

        if not self.opinion_enabled:
            payload = {
                "opinion": "",
                "actions": [],
                "risk_notes": [],
                "variant": resolved_variant if normalized_mode == "balanced" else "",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            result.assistant_opinions[cache_key] = payload
            if normalized_mode == "balanced" and balanced_variant is None:
                result.assistant_opinions["balanced"] = payload
            result.opinion_mode = normalized_mode
            return payload

        payload = self._generate_assistant_opinion(
            mode=normalized_mode,
            result=result,
            rfx=rfx,
            balanced_variant=resolved_variant,
        )
        result.assistant_opinions[cache_key] = payload
        if normalized_mode == "balanced" and balanced_variant is None:
            result.assistant_opinions["balanced"] = payload
        result.opinion_mode = normalized_mode
        return payload
