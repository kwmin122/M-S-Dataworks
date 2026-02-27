"""
RFx AI Assistant - RFx 문서 분석기

RFP/RFQ/RFI 문서에서 자격요건, 평가기준 등을 구조화하여 추출.
LLM을 활용하여 비정형 문서를 정형 데이터로 변환.

Example:
    >>> analyzer = RFxAnalyzer(api_key="...")
    >>> result = analyzer.analyze("rfp_document.pdf")
    >>> print(result.requirements)
"""

import os
import re
import json
import time
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum

from document_parser import DocumentParser, ParsedDocument
from rfp_synonyms import generate_prompt_injection

# 모듈 레벨 RFP 요약 캐시 (인스턴스 간 공유, Lock으로 스레드 안전 보장)
_rfp_summary_cache: dict[str, str] = {}
_rfp_summary_cache_lock = threading.Lock()


# ============================================================
# STEP 0: 선언적 제약 타입 (범용 수치 비교용)
# ============================================================

ConstraintOp = Literal[">=", ">", "<=", "<", "==", "!=", "in", "not_in"]
ConstraintValue = float | bool | str | list[str]


class ConstraintMetric(str, Enum):
    CONTRACT_AMOUNT      = "contract_amount"      # 건당 N억 이상
    PROJECT_COUNT        = "project_count"        # N건 이상
    HEADCOUNT            = "headcount"            # N명 이상
    PERIOD_YEARS         = "period_years"         # 최근 N년 이내 (명확한 경우만)
    COMPLETION_REQUIRED  = "completion_required"  # 완료된 실적만 (bool)
    CERT_GRADE           = "cert_grade"           # 기사 이상 (str)
    CUSTOM               = "CUSTOM"               # 파싱 불가 → LLM fallback


@dataclass
class RFxConstraint:
    """개별 정량 제약 조건. 특정 문서값 하드코딩 없이 metric+op+value로만 표현."""
    metric: str            # ConstraintMetric 값 또는 "CUSTOM"
    op: ConstraintOp
    value: ConstraintValue
    unit: str = ""         # KRW_100M | headcount | year | ""
    raw: str = ""          # 원문 구절 그대로 (추정/재서술 금지)


# ============================================================
# STEP 1: RFx 분석 결과 데이터 클래스
# ============================================================

@dataclass
class RFxRequirement:
    """개별 자격요건"""
    category: str          # 필수자격, 기술요건, 실적요건, 재무요건, 기타
    description: str       # 요건 설명
    is_mandatory: bool     # 필수 여부
    detail: str = ""       # 상세 내용 (기존 유지, fallback)
    constraints: list[RFxConstraint] = field(default_factory=list)  # 선언적 제약

    def __str__(self):
        mandatory = "🔴 필수" if self.is_mandatory else "🟡 권장"
        return f"[{mandatory}] [{self.category}] {self.description}"


@dataclass
class RFxEvaluationCriteria:
    """평가기준 항목"""
    category: str      # 기술평가, 가격평가, 기타
    item: str          # 평가 항목
    score: float       # 배점
    detail: str = ""   # 상세 내용


@dataclass
class RFxAnalysisResult:
    """RFx 문서 분석 종합 결과"""
    # 기본정보
    title: str = ""
    issuing_org: str = ""
    announcement_number: str = ""
    deadline: str = ""
    project_period: str = ""
    budget: str = ""
    
    # 자격요건
    requirements: list[RFxRequirement] = field(default_factory=list)
    
    # 평가기준
    evaluation_criteria: list[RFxEvaluationCriteria] = field(default_factory=list)
    
    # 제출서류
    required_documents: list[str] = field(default_factory=list)
    
    # 특이사항
    special_notes: list[str] = field(default_factory=list)
    
    # 원문 텍스트 (참조용)
    raw_text: str = ""

    # 문서 유형 게이트 정보
    document_type: str = "unknown"     # rfx|proposal|research_report|company_profile|manual|other
    is_rfx_like: bool = True           # RFx/유사 제안서 여부
    document_gate_reason: str = ""     # 분류 사유
    document_gate_confidence: float = 0.0
    extraction_model: str = ""         # 실제 추출에 사용된 모델
    
    @property
    def mandatory_requirements(self) -> list[RFxRequirement]:
        """필수 자격요건만 필터"""
        return [r for r in self.requirements if r.is_mandatory]
    
    @property
    def total_evaluation_score(self) -> float:
        """총 배점"""
        return sum(c.score for c in self.evaluation_criteria)
    
    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "기본정보": {
                "공고명": self.title,
                "발주기관": self.issuing_org,
                "공고번호": self.announcement_number,
                "제출마감일": self.deadline,
                "사업기간": self.project_period,
                "예산": self.budget
            },
            "문서유형": {
                "유형": self.document_type,
                "RFx유사여부": self.is_rfx_like,
                "분류신뢰도": self.document_gate_confidence,
                "근거": self.document_gate_reason,
                "추출모델": self.extraction_model,
            },
            "자격요건": [
                {
                    "분류": r.category,
                    "요건": r.description,
                    "필수여부": "필수" if r.is_mandatory else "권장",
                    "상세": r.detail,
                    "constraints": [
                        {
                            "metric": c.metric,
                            "op": c.op,
                            "value": c.value,
                            "unit": c.unit,
                            "raw": c.raw,
                        }
                        for c in r.constraints
                    ],
                }
                for r in self.requirements
            ],
            "평가기준": [
                {
                    "분류": c.category,
                    "항목": c.item,
                    "배점": c.score,
                    "상세": c.detail
                }
                for c in self.evaluation_criteria
            ],
            "제출서류": self.required_documents,
            "특이사항": self.special_notes
        }


class RFxParseError(Exception):
    """RFx LLM 응답 파싱/검증 실패"""


DOCUMENT_CLASSIFY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "document_type": {
            "type": "string",
            "enum": ["rfx", "proposal", "research_report", "company_profile", "manual", "other"],
        },
        "is_rfx_like": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["document_type", "is_rfx_like", "confidence", "reason"],
}


RFX_EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "기본정보": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "공고명": {"type": "string"},
                "발주기관": {"type": "string"},
                "공고번호": {"type": "string"},
                "제출마감일": {"type": "string"},
                "사업기간": {"type": "string"},
                "예산": {"type": "string"},
            },
            "required": ["공고명", "발주기관", "공고번호", "제출마감일", "사업기간", "예산"],
        },
        "자격요건": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "분류": {"type": "string"},
                    "요건": {"type": "string"},
                    "필수여부": {"type": "string", "enum": ["필수", "권장"]},
                    "상세": {"type": "string"},
                    "constraints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "metric": {"type": "string"},
                                "op": {
                                    "type": "string",
                                    "enum": [">=", ">", "<=", "<", "==", "!=", "in", "not_in"]
                                },
                                "value": {"type": "string"},
                                "unit": {"type": "string"},
                                "raw": {"type": "string"},
                            },
                            "required": ["metric", "op", "value", "unit", "raw"],
                        },
                    },
                },
                "required": ["분류", "요건", "필수여부", "상세", "constraints"],
            },
        },
        "평가기준": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "분류": {"type": "string"},
                    "항목": {"type": "string"},
                    "배점": {"type": "number"},
                    "상세": {"type": "string"},
                },
                "required": ["분류", "항목", "배점", "상세"],
            },
        },
        "제출서류": {
            "type": "array",
            "items": {"type": "string"},
        },
        "특이사항": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["기본정보", "자격요건", "평가기준", "제출서류", "특이사항"],
}


# ============================================================
# STEP 2: RFx 분석기 (LLM 기반)
# ============================================================

class RFxAnalyzer:
    """
    RFx 문서를 분석하여 구조화된 정보를 추출하는 분석기.
    
    LLM(GPT)을 사용하여 비정형 RFP 문서에서
    자격요건, 평가기준, 제출서류 등을 자동 추출.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Args:
            api_key (str): OpenAI API 키
            model (str): 사용할 모델명
        """
        self.api_key = api_key
        self.model = model
        self.small_model = os.getenv("OPENAI_MODEL_SMALL", model or "gpt-4o-mini")
        self.large_model = os.getenv("OPENAI_MODEL_LARGE", "gpt-4o")
        self.routing_enabled = os.getenv("OPENAI_ROUTING_ENABLED", "1").strip().lower() not in {"0", "false", "off"}
        self.strict_json_only = os.getenv("OPENAI_STRICT_JSON_ONLY", "1").strip().lower() not in {
            "0",
            "false",
            "off",
            "no",
        }
        self.large_doc_char_threshold = int(os.getenv("OPENAI_ROUTING_CHAR_THRESHOLD", "28000"))
        self.large_doc_page_threshold = int(os.getenv("OPENAI_ROUTING_PAGE_THRESHOLD", "35"))
        self.parser = DocumentParser()
        self._init_llm()
    
    def _init_llm(self) -> None:
        """LLM 클라이언트 초기화"""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            print(f"✅ LLM 초기화 완료: {self.model}")
        except ImportError:
            raise ImportError("openai 미설치. pip install openai")

    def _chat(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        model: Optional[str] = None
    ) -> str:
        """OpenAI Chat Completions 호출"""
        response = self.client.chat.completions.create(
            model=model or self.model,
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
        """OpenAI Structured Outputs(json_schema strict) 호출.

        finish_reason='length'(토큰 초과)이면 max_tokens를 늘려 1회 재시도.
        JSON 파싱 실패 시에도 1회 재시도한다.
        """
        last_error: Exception | None = None
        current_max_tokens = max_tokens
        for attempt in range(2):
            response = self.client.chat.completions.create(
                model=model or self.model,
                max_tokens=current_max_tokens,
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
            choice = response.choices[0]
            # 토큰 초과로 JSON이 잘린 경우 → max_tokens 증가 후 재시도
            if choice.finish_reason == "length":
                current_max_tokens = min(current_max_tokens * 2, 16384)
                last_error = RFxParseError(
                    f"Structured Output 토큰 초과 (finish_reason=length, "
                    f"max_tokens={current_max_tokens // 2})"
                )
                if attempt == 0:
                    print(f"   ⚠️ 토큰 초과, max_tokens={current_max_tokens}으로 재시도")
                    continue
                raise last_error
            content = (choice.message.content or "").strip()
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                last_error = RFxParseError(f"Structured Output JSON 파싱 실패: {exc}")
                if attempt == 0:
                    print(f"   ⚠️ JSON 파싱 실패, 재시도 중... ({exc})")
                    continue
                raise last_error from exc
            if not isinstance(parsed, dict):
                raise RFxParseError("Structured Output이 객체(dict) 형식이 아닙니다.")
            return parsed
        raise last_error or RFxParseError("Structured Output 호출 실패")
    
    # ============================================================
    # STEP 3: RFx 문서 분석 메인 함수
    # ============================================================
    
    def analyze(self, file_path: str) -> RFxAnalysisResult:
        """
        RFx 문서를 분석하여 구조화된 결과를 반환한다.
        
        Args:
            file_path (str): RFx 문서 파일 경로
            
        Returns:
            RFxAnalysisResult: 분석 결과
        """
        # STEP 3-1: 문서 파싱
        doc = self.parser.parse(file_path)
        print(f"📄 문서 파싱 완료: {doc.filename} ({doc.char_count}자, {doc.page_count}페이지)")

        # STEP 3-2: 문서 유형 게이트 분류 (RFx/비RFx/유사제안서)
        gate = self._classify_document_type(doc)
        extraction_model = self._select_extraction_model(
            char_count=doc.char_count,
            page_count=doc.page_count,
            is_rfx_like=gate.get("is_rfx_like", True),
        )

        # STEP 3-3: 유형에 맞는 다중 패스 구조화 추출
        analysis = self._extract_with_llm(
            doc.text,
            is_rfx_like=bool(gate.get("is_rfx_like", True)),
            model_name=extraction_model,
        )
        analysis.raw_text = doc.text
        analysis.document_type = str(gate.get("document_type", "unknown"))
        analysis.is_rfx_like = bool(gate.get("is_rfx_like", True))
        analysis.document_gate_reason = str(gate.get("reason", ""))
        analysis.document_gate_confidence = float(gate.get("confidence", 0.0) or 0.0)
        analysis.extraction_model = extraction_model
        
        return analysis
    
    def analyze_text(self, text: str) -> RFxAnalysisResult:
        """텍스트를 직접 분석 (파일 없이)"""
        pseudo_doc = ParsedDocument(filename="direct_input.txt", text=text, pages=[text] if text else [])
        gate = self._classify_document_type(pseudo_doc)
        model_name = self._select_extraction_model(
            char_count=len(text or ""),
            page_count=1,
            is_rfx_like=bool(gate.get("is_rfx_like", True)),
        )
        analysis = self._extract_with_llm(
            text,
            is_rfx_like=bool(gate.get("is_rfx_like", True)),
            model_name=model_name,
        )
        analysis.raw_text = text
        analysis.document_type = str(gate.get("document_type", "unknown"))
        analysis.is_rfx_like = bool(gate.get("is_rfx_like", True))
        analysis.document_gate_reason = str(gate.get("reason", ""))
        analysis.document_gate_confidence = float(gate.get("confidence", 0.0) or 0.0)
        analysis.extraction_model = model_name
        return analysis
    
    # ============================================================
    # STEP 3-B: RFP 3-Section 마크다운 요약 생성
    # ============================================================

    def _trim_for_token_limit(self, text: str, max_chars: int = 80000) -> str:
        """문서가 너무 길면 별지/부록/서식 제거 후 본문만 남긴다."""
        if len(text) <= max_chars:
            return text
        cut_pattern = re.compile(
            r'\n\s*(?:붙임|별지|별첨|첨부)\s*\d*\s*[\.:\-\)]',
            re.IGNORECASE,
        )
        match = cut_pattern.search(text)
        if match and match.start() > max_chars // 2:
            trimmed = text[:match.start()] + "\n\n[... 별지/부록 이후 생략 ...]"
        else:
            trimmed = text
        trimmed = re.sub(
            r'\n\s*(?:서식|양식)\s*\d+\s*[\.:\-\)].*?(?=\n\s*(?:서식|양식|제\d+[장조절])|$)',
            '\n[... 서식 생략 ...]\n',
            trimmed,
            flags=re.DOTALL,
        )
        if len(trimmed) > max_chars:
            trimmed = trimmed[:max_chars] + "\n\n[... 이하 생략 (토큰 한계) ...]"
        return trimmed

    def generate_rfp_summary(self, text: str, model_name: str | None = None) -> str:
        """RFP 문서에서 5-section 마크다운 요약을 생성한다.

        Sections:
        1. 사업유형 (발주처, 사업비, 기간, 계약방법, 공동계약, 하도급)
        2. 필요한 것 (사업 범위 - 납품/구축/수행 대상)
        3. 입찰참가 자격조건 (전체 목록)
        4. 평가방법 및 점수 (평가표 원문 보존)
        5. 추가 참고사항 (분리발주, 별도발주, 기존 시스템 연동 등)
        """
        cache_key = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        with _rfp_summary_cache_lock:
            if cache_key in _rfp_summary_cache:
                print("   ↳ RFP 요약: 캐시 히트")
                return _rfp_summary_cache[cache_key]

        synonym_guide = generate_prompt_injection()

        trimmed_text = self._trim_for_token_limit(text)
        model = model_name or self.model

        prompt = f"""당신은 한국 공공조달 입찰 전문 분석가입니다.
아래 제안요청서(RFP) 문서를 분석하여, 반드시 아래 5개 섹션 구조로 마크다운 형식 요약을 작성해주세요.
원문에 기재된 정보만 사용하고, 추측하지 마세요.

{synonym_guide}

## 출력 형식 (마크다운)

### 1. 사업유형
- **발주처**: [발주기관명]
- **사업비(예산)**: [금액 + VAT 포함/별도 여부. 사업비/총사업비/추정가격/예정가격/배정예산 등 어떤 표현이든 찾아서 기재]
- **사업기간**: [시작~종료 또는 기간. 사업기간/계약기간/용역기간/수행기간 등 동의어 포함 검색]
- **계약방법**: [입찰방식 + 낙찰자 결정방식. 예: 제한경쟁입찰 / 협상에 의한 계약]
- **공동계약(컨소시엄)**: [허용 여부, 방식(공동이행/분담이행/주계약자관리), 최소 지분율]
- **하도급**: [허용 여부, 제한사항]

### 2. 필요한 것 (사업 범위)
[이 사업에서 **실제로 납품/구축/수행해야 하는 것**을 구체적으로 나열.
 - 장비/시스템 종류, 수량, 규격 (예: 스마트폴 21개소, CCTV 69대, 서버 2식 등)
 - 소프트웨어 개발 범위 (예: VMS 연동, 관제시스템 구축 등)
 - 설치/시공 범위 (예: 광케이블 포설, 전원공사 등)
 - 문서에서 "사업범위", "과업내용", "납품물량", "수량산출" 등 섹션을 찾아 핵심만 요약]

### 3. 입찰참가 자격조건
[문서에 기재된 **모든** 자격요건을 번호 목록으로 빠짐없이 나열.
 - 업체가 **갖추어야 하는** 조건만 포함.
 - 부정당업자 제재 처분을 받지 않은 자 — 이 조건이 있으면 포함.
 - 하나의 항목에 여러 등록/자격이 나열되어 있으면 각각 별도 항목으로 분리.
 - 사업실적 요건은 구체적 금액·건수·기간까지 원문 그대로 기재.
 - 세부품명번호, 업종코드 등 구체적 번호가 있으면 반드시 포함.]

### 4. 평가방법 및 점수
[평가 구분(기술평가/가격평가), 배점, 세부 항목을 **표(table) 형태**로 원문에 최대한 가깝게 보존.
 정량적평가와 정성적평가를 구분하여 작성.
 배점이 있으면 반드시 포함.
 **중요**: 세부 항목 배점의 합이 부문 배점과 반드시 일치해야 합니다.
 정성적 평가표는 원문의 부문-세부부문-배점 계층 구조를 그대로 유지하세요.
 부문 안에 세부부문이 여러 개 있으면 각각의 배점을 별도 행으로 작성하세요.
 절대로 세부부문 배점을 합산하거나 재구성하지 마세요.
 배점이 명시되지 않은 항목은 배점 없이 항목명만 기재하세요.]

### 5. 추가 참고사항
[입찰 준비 시 실무적으로 중요한 사항을 나열. 아래 항목 중 문서에 있는 것만 포함:
 - **분리발주**: 분리발주 대상 품목 (SW, HW 등) 및 제외 사유
 - **별도발주(직접구매)**: 발주기관이 직접 구매하는 품목 (예: 특정 라이선스, 장비 등)
 - **기존 시스템 연동**: 기존에 사용 중인 시스템/제품명이 명시되어 있으면 기재 (예: 특정 VMS, NVR 등)
 - **현장설명회**: 일시, 장소, 필수 여부
 - **보증/유지보수**: 하자보수 기간, 유지보수 조건
 - **기타**: 위에 해당하지 않지만 입찰 참여에 중요한 조건
 해당 사항이 없으면 "해당 없음"으로 기재.]

---

## 분석할 문서:
{trimmed_text}
===== 문서 끝 ====="""

        t0 = time.perf_counter()
        try:
            raw = self._chat(
                prompt=prompt,
                max_tokens=4096,
                temperature=0.1,
                model=model,
            )
            result = self._postprocess_rfp_summary(raw)
            elapsed = time.perf_counter() - t0
            print(f"   ↳ RFP 요약 생성 완료 ({elapsed:.1f}s, {len(result)}자)")
            with _rfp_summary_cache_lock:
                _rfp_summary_cache[cache_key] = result
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"   ↳ RFP 요약 생성 실패 ({elapsed:.1f}s): {exc}")
            return ""

    @staticmethod
    def _postprocess_rfp_summary(summary: str) -> str:
        """결격사유/부정당업자 항목을 자격조건 목록에서 자동 제거."""
        _DISQUALIFY_RE = re.compile(
            r'부정당\s*업자|결격\s*사유|입찰\s*참가\s*자격\s*제한',
        )
        lines = summary.split('\n')
        filtered = [
            line for line in lines
            if not (_DISQUALIFY_RE.search(line) and re.match(r'\s*\d+[\.\)]\s', line))
        ]
        return '\n'.join(filtered)

    # ============================================================
    # STEP 4: LLM 기반 정보 추출
    # ============================================================

    def _extract_with_llm(
        self,
        text: str,
        is_rfx_like: bool = True,
        model_name: Optional[str] = None,
    ) -> RFxAnalysisResult:
        """
        LLM을 사용하여 RFx 문서에서 구조화된 정보를 추출한다.
        
        Args:
            text (str): 문서 원문 텍스트
            
        Returns:
            RFxAnalysisResult: 추출된 분석 결과
        """
        chunks = self._split_text_for_multipass(text)
        partial_results: list[RFxAnalysisResult] = []

        if len(chunks) == 1:
            # 단일 청크 — 스레드풀 오버헤드 없이 직접 실행
            prompt = (self._build_extraction_prompt(chunks[0]) if is_rfx_like
                      else self._build_general_extraction_prompt(chunks[0]))
            parsed = self._extract_single_pass(prompt=prompt, model_name=model_name)
            partial_results.append(parsed)
            print(f"   ↳ 추출 패스 1/1 완료 (요건 {len(parsed.requirements)}개)")
        else:
            # 다중 청크 — 병렬 추출 (최대 4 동시)
            def _extract_chunk(idx_text: tuple[int, str]) -> tuple[int, RFxAnalysisResult]:
                idx, chunk_text = idx_text
                prompt = (self._build_extraction_prompt(chunk_text) if is_rfx_like
                          else self._build_general_extraction_prompt(chunk_text))
                return idx, self._extract_single_pass(prompt=prompt, model_name=model_name)

            with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as pool:
                futures = {pool.submit(_extract_chunk, (i, ct)): i
                           for i, ct in enumerate(chunks, start=1)}
                indexed: list[tuple[int, RFxAnalysisResult]] = []
                for future in as_completed(futures):
                    idx, parsed = future.result()
                    indexed.append((idx, parsed))
                    print(f"   ↳ 추출 패스 {idx}/{len(chunks)} 완료 (요건 {len(parsed.requirements)}개)")
                # 원래 순서대로 정렬
                indexed.sort(key=lambda x: x[0])
                partial_results = [p for _, p in indexed]

        merged = self._merge_partial_results(partial_results)
        self._validate_parsed_result(merged, require_requirements=is_rfx_like)
        return merged

    def _extract_single_pass(self, prompt: str, model_name: Optional[str]) -> RFxAnalysisResult:
        """단일 패스 구조화 추출 (Structured Output 우선, JSON 파싱 폴백)"""
        try:
            structured_payload = self._chat_json(
                prompt=prompt,
                max_tokens=4096,
                temperature=0.1,
                schema_name="rfx_extraction",
                schema=RFX_EXTRACTION_JSON_SCHEMA,
                model=model_name,
            )
            return self._parse_llm_response(
                json.dumps(structured_payload, ensure_ascii=False)
            )
        except Exception as structured_error:
            if self.strict_json_only:
                raise RFxParseError(
                    f"Structured Output 추출 실패(strict 모드): {structured_error}"
                ) from structured_error
            response_text = self._chat(
                prompt=prompt,
                max_tokens=4096,
                temperature=0.1,
                model=model_name,
            )
            try:
                return self._parse_llm_response(response_text)
            except RFxParseError:
                repair_prompt = f"""아래 텍스트를 RFx 분석 JSON 스키마에 맞춰 재구성하세요.
반드시 JSON만 출력하고 코드블록/설명은 금지합니다.

[원본 응답]
{response_text}
"""
                repaired_text = self._chat(
                    prompt=repair_prompt,
                    max_tokens=4096,
                    temperature=0.0,
                    model=model_name,
                )
                return self._parse_llm_response(repaired_text)

    def _split_text_for_multipass(self, text: str) -> list[str]:
        """
        대용량 문서를 다중 패스로 분할.

        - 1패스 최대 길이: 40,000자
        - 오버랩: 3,500자
        """
        normalized = (text or "").strip()
        if not normalized:
            return [""]

        max_chars = 40_000
        overlap = 3_500
        if len(normalized) <= max_chars:
            return [normalized]

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(start + max_chars, len(normalized))
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(0, end - overlap)
        return chunks

    def _normalize_key(self, value: str) -> str:
        filtered = []
        for ch in (value or "").lower().strip():
            if ch.isalnum() or ch in ("가", "나", "다", "라", "마", "바", "사", "아", "자", "차", "카", "타", "파", "하"):
                filtered.append(ch)
            elif "\uac00" <= ch <= "\ud7a3":
                filtered.append(ch)
        return "".join(filtered)

    def _merge_partial_results(self, partial_results: list[RFxAnalysisResult]) -> RFxAnalysisResult:
        """다중 패스 결과를 merge + dedup"""
        merged = RFxAnalysisResult()
        if not partial_results:
            return merged

        # 기본정보: 앞 패스 우선, 비어있으면 뒤 패스 보완
        for part in partial_results:
            if not merged.title and part.title:
                merged.title = part.title
            if not merged.issuing_org and part.issuing_org:
                merged.issuing_org = part.issuing_org
            if not merged.announcement_number and part.announcement_number:
                merged.announcement_number = part.announcement_number
            if not merged.deadline and part.deadline:
                merged.deadline = part.deadline
            if not merged.project_period and part.project_period:
                merged.project_period = part.project_period
            if not merged.budget and part.budget:
                merged.budget = part.budget

        req_index: dict[str, RFxRequirement] = {}
        for part in partial_results:
            for req in part.requirements:
                key = self._normalize_key(req.description)
                if not key:
                    continue
                if key not in req_index:
                    req_index[key] = RFxRequirement(
                        category=req.category,
                        description=req.description,
                        is_mandatory=req.is_mandatory,
                        detail=req.detail,
                        constraints=list(req.constraints),  # 첫 패스 constraints 유지
                    )
                    continue
                # 중복 시 필수 플래그 보수적으로 OR
                existing = req_index[key]
                existing.is_mandatory = existing.is_mandatory or req.is_mandatory
                if req.detail and req.detail not in existing.detail:
                    existing.detail = f"{existing.detail} / {req.detail}".strip(" /")
        merged.requirements = list(req_index.values())

        crit_index: dict[str, RFxEvaluationCriteria] = {}
        for part in partial_results:
            for crit in part.evaluation_criteria:
                key = self._normalize_key(f"{crit.category}|{crit.item}")
                if not key:
                    continue
                if key not in crit_index:
                    crit_index[key] = RFxEvaluationCriteria(
                        category=crit.category,
                        item=crit.item,
                        score=float(crit.score or 0.0),
                        detail=crit.detail,
                    )
                    continue
                existing = crit_index[key]
                existing.score = max(existing.score, float(crit.score or 0.0))
                if crit.detail and crit.detail not in existing.detail:
                    existing.detail = f"{existing.detail} / {crit.detail}".strip(" /")
        merged.evaluation_criteria = list(crit_index.values())

        docs_seen: set[str] = set()
        notes_seen: set[str] = set()
        for part in partial_results:
            for doc in part.required_documents:
                key = doc.strip()
                if key and key not in docs_seen:
                    docs_seen.add(key)
                    merged.required_documents.append(key)
            for note in part.special_notes:
                key = note.strip()
                if key and key not in notes_seen:
                    notes_seen.add(key)
                    merged.special_notes.append(key)

        return merged
    
    def _build_extraction_prompt(self, text: str) -> str:
        """RFx 분석을 위한 프롬프트 구성"""
        return f"""당신은 입찰 전문 분석가입니다. 아래 RFx(RFP/RFQ/RFI) 문서를 분석하여 구조화된 JSON을 생성해주세요.

반드시 아래 JSON 형식으로만 응답해주세요. 다른 텍스트는 포함하지 마세요.

```json
{{
    "기본정보": {{
        "공고명": "문서에서 추출한 공고 제목",
        "발주기관": "발주 기관명",
        "공고번호": "공고번호 (없으면 빈 문자열)",
        "제출마감일": "마감일 (없으면 빈 문자열)",
        "사업기간": "사업기간 (없으면 빈 문자열)",
        "예산": "예산금액 (없으면 빈 문자열)"
    }},
    "자격요건": [
        {{
            "분류": "필수자격|기술요건|실적요건|재무요건|기타",
            "요건": "자격요건 설명",
            "필수여부": "필수|권장",
            "상세": "구체적인 조건 및 기준",
            "constraints": [
                {{"metric": "contract_amount", "op": ">=", "value": 20.0, "unit": "KRW_100M", "raw": "건당 20억원 이상"}},
                {{"metric": "project_count",   "op": ">=", "value": 2,    "unit": "",         "raw": "2건 이상"}},
                {{"metric": "completion_required", "op": "==", "value": true, "unit": "", "raw": "완료된 실적만"}}
            ]
        }}
    ],
    "평가기준": [
        {{
            "분류": "기술평가|가격평가|기타",
            "항목": "평가 항목명",
            "배점": 숫자,
            "상세": "평가 세부 기준"
        }}
    ],
    "제출서류": ["서류1", "서류2"],
    "특이사항": ["주의사항1", "컨소시엄 조건 등"]
}}
```

주의사항:
1. 자격요건은 빠짐없이 모두 추출해주세요.
2. 필수/권장을 정확히 구분해주세요.
3. 평가기준의 배점이 있으면 반드시 포함해주세요.
4. 문서에 명시되지 않은 항목은 빈 값으로 두세요.
5. 반드시 유효한 JSON만 출력하세요.
6. **"참가 제한" / "결격사유" / "부정당업자" 구분 규칙 (매우 중요)**:
   - 아래 키워드가 포함된 항목은 **결격사유/참가제한**이므로 자격요건에 넣지 마세요:
     "참가제한", "참가 제한", "참가자격 제한", "입찰참가 제한", "참가불가", "참가할 수 없",
     "결격사유", "결격 사유", "부정당업자", "부정당 업자", "부실이행", "부당이행",
     "담합", "뇌물", "입찰참가자격 제한처분", "제재처분", "영업정지",
     "파산", "회생절차", "금고 이상의 형"
   - 이런 결격사유는 자격요건으로 추출하지 마세요. 대신 "특이사항"에 "참가 제한 조건 N개 포함" 형태로 요약하세요.
   - 자격요건으로 추출해야 하는 것: 회사가 **적극적으로 갖추어야 하는** 조건 (사업 실적, 기술 인력, 자본금, 인증, 면허, 소재지 등).
   - 판별 기준: "해당 사항이 없으면 OK" → 결격사유(제외), "보유/달성해야 OK" → 자격요건(포함).
   - 예시 — 자격요건 O: "최근 5년간 유사 용역 실적 2건 이상", "정보보안 ISO 27001 인증 보유", "본사 소재지 서울"
   - 예시 — 결격사유 X: "부실·부당 이행자", "담합한 자", "뇌물을 준 자", "부정당업자로 입찰참가 제한을 받은 자", "국가유공자법에 의한 참가제한을 받은 자"
7. 자격요건의 constraints 배열 추출 규칙:
   - 금액 조건 → metric: "contract_amount", 억원 단위 숫자(KRW_100M), 예: "건당 20억원" → value: 20.0
   - 건수/명수 → metric: "project_count" / "headcount", 정수
   - 기간(최근 N년, 명확한 경우만) → metric: "period_years", 정수
   - 완료여부 → metric: "completion_required", boolean
   - 등급/자격 → metric: "cert_grade", 문자열
   - 파싱 불가 또는 애매한 표현 → metric: "CUSTOM", raw에 원문 그대로
   - raw 필드: 반드시 원문 구절 그대로 (추정/재서술 금지)
   - 조건 없으면 constraints: [] (빈 배열, 키 생략 금지)

===== RFx 문서 원문 =====
{text}
===== 문서 끝 ====="""

    def _build_general_extraction_prompt(self, text: str) -> str:
        """
        비RFx/유사 문서용 구조화 프롬프트.

        목표:
        - 어떤 문서가 들어와도 비교/분석/질문이 가능하도록
          "핵심 조건/비교 포인트"를 자격요건 형태로 변환한다.
        """
        return f"""당신은 문서 비교/분석 전문가입니다.
아래 문서가 RFx가 아닐 수 있음을 전제로, 비교 가능한 핵심 조건을 구조화 JSON으로 정리해주세요.

반드시 아래 JSON 형식으로만 응답하세요.

```json
{{
    "기본정보": {{
        "공고명": "문서 제목 또는 주제",
        "발주기관": "작성기관/발행기관 (없으면 빈 문자열)",
        "공고번호": "",
        "제출마감일": "",
        "사업기간": "",
        "예산": ""
    }},
    "자격요건": [
        {{
            "분류": "핵심조건|기술요건|품질요건|절차요건|기타",
            "요건": "비교 가능한 핵심 문장",
            "필수여부": "필수|권장",
            "상세": "근거 또는 수치",
            "constraints": []
        }}
    ],
    "평가기준": [
        {{
            "분류": "기술평가|가격평가|기타",
            "항목": "평가/비교 항목",
            "배점": 0,
            "상세": "가중치 또는 중요도 힌트"
        }}
    ],
    "제출서류": [],
    "특이사항": ["문서 성격 및 비교 시 주의사항"]
}}
```

규칙:
1) 문서가 RFx가 아니면 GO/NO-GO용 자격이 아니라 '비교 포인트' 중심으로 추출하세요.
2) 원문에 있는 문장만 근거로 사용하세요.
3) 자격요건은 최소 1개 이상 생성하세요.
4) JSON 외 텍스트 금지.

===== 입력 문서 원문 =====
{text}
===== 문서 끝 ====="""

    def _build_classification_prompt(self, text: str) -> str:
        return f"""아래 문서의 유형을 분류하세요.
반드시 JSON 객체만 반환하세요.

분류 기준:
- rfx: 입찰 공고, 제안요청서(RFP/RFQ), 참가자격/평가기준/제출서류가 핵심인 문서
- proposal: 제안서/사업제안 문서(요건 및 비교 가능)
- research_report: 연구보고서/정책연구/백서
- company_profile: 회사소개서/브로슈어
- manual: 운영 매뉴얼/가이드라인
- other: 그 외

JSON:
{{
  "document_type": "rfx|proposal|research_report|company_profile|manual|other",
  "is_rfx_like": true 또는 false,
  "confidence": 0~1 숫자,
  "reason": "판단 근거 한 줄"
}}

참고:
- is_rfx_like = true 조건: 입찰·평가·참가자격·제출요건 기반으로 회사 적격성 판단이 가능한 문서
- 연구보고서/회사소개서/일반 매뉴얼은 보통 false

[문서 일부]
{text}
"""

    def _classify_document_type(self, doc: ParsedDocument) -> dict[str, Any]:
        """문서 유형 게이트 분류"""
        preview = (doc.text or "")[:18_000]
        if not preview.strip():
            return {
                "document_type": "other",
                "is_rfx_like": False,
                "confidence": 0.0,
                "reason": "문서 텍스트가 비어있어 분류할 수 없습니다.",
            }

        prompt = self._build_classification_prompt(preview)
        try:
            payload = self._chat_json(
                prompt=prompt,
                max_tokens=500,
                temperature=0.0,
                schema_name="document_classification",
                schema=DOCUMENT_CLASSIFY_JSON_SCHEMA,
                model=self.small_model,
            )
            return payload
        except Exception:
            # 보수적 폴백: 제목/본문 키워드 기반
            text = f"{doc.filename}\n{preview}".lower()
            if any(token in text for token in ["제안요청서", "입찰", "rfp", "rfq", "참가자격", "평가기준"]):
                return {
                    "document_type": "rfx",
                    "is_rfx_like": True,
                    "confidence": 0.6,
                    "reason": "키워드 기반 폴백 분류: RFx/입찰 관련 용어 감지",
                }
            if any(token in text for token in ["연구보고", "정책연구", "백서"]):
                return {
                    "document_type": "research_report",
                    "is_rfx_like": False,
                    "confidence": 0.6,
                    "reason": "키워드 기반 폴백 분류: 연구/보고서 용어 감지",
                }
            return {
                "document_type": "other",
                "is_rfx_like": False,
                "confidence": 0.4,
                "reason": "분류 실패 폴백: 일반 문서로 처리",
            }

    def _select_extraction_model(self, char_count: int, page_count: int, is_rfx_like: bool) -> str:
        """문서 크기/성격 기반 모델 라우팅"""
        if not self.routing_enabled:
            return self.small_model

        if char_count >= self.large_doc_char_threshold:
            return self.large_model
        if page_count >= self.large_doc_page_threshold:
            return self.large_model
        # 유사 RFx인데 길이는 짧아도 표/요건 추출 품질을 위해 약간 공격적으로 상위 모델 사용 가능
        if is_rfx_like and char_count >= int(self.large_doc_char_threshold * 0.8):
            return self.large_model
        return self.small_model
    
    def _extract_json_payload(self, response_text: str) -> dict[str, Any]:
        """LLM 응답에서 JSON payload를 추출"""
        json_text = response_text.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in json_text:
            json_text = json_text.split("```", 1)[1].split("```", 1)[0]

        try:
            data = json.loads(json_text.strip())
        except json.JSONDecodeError as exc:
            raise RFxParseError(f"JSON 파싱 실패: {exc}") from exc

        if not isinstance(data, dict):
            raise RFxParseError("최상위 JSON이 객체(dict) 형식이 아닙니다.")

        return data

    @staticmethod
    def _parse_mandatory_flag(raw_value: Any) -> bool:
        """LLM 변형값을 안전하게 필수 여부(bool)로 변환"""
        if isinstance(raw_value, bool):
            return raw_value

        normalized = (
            str(raw_value or "")
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

        if not normalized:
            return False

        mandatory_tokens = {
            "필수",
            "필수요건",
            "mandatory",
            "must",
            "required",
            "true",
            "yes",
            "y",
            "1",
        }
        optional_tokens = {
            "권장",
            "선택",
            "optional",
            "recommended",
            "should",
            "false",
            "no",
            "n",
            "0",
        }

        if normalized in mandatory_tokens:
            return True
        if normalized in optional_tokens:
            return False

        if any(token in normalized for token in ["필수", "mandatory", "must", "required"]):
            return True
        if any(token in normalized for token in ["권장", "optional", "recommended"]):
            return False
        return False

    def _validate_parsed_result(self, result: RFxAnalysisResult, require_requirements: bool = True) -> None:
        """파싱 결과 최소 유효성 검증 — 요건 0개여도 경고만 남기고 계속 진행."""
        if require_requirements and not result.requirements:
            print("   ⚠ 자격요건이 0개 추출됨 (문서에 자격요건 정보가 부족할 수 있습니다)")

    def _parse_llm_response(self, response_text: str) -> RFxAnalysisResult:
        """LLM 응답을 파싱하여 RFxAnalysisResult로 변환"""
        result = RFxAnalysisResult()
        data = self._extract_json_payload(response_text)

        # 기본정보 파싱
        basic = data.get("기본정보", {})
        if not isinstance(basic, dict):
            raise RFxParseError("'기본정보'는 객체(dict)여야 합니다.")
        result.title = str(basic.get("공고명", "")).strip()
        result.issuing_org = str(basic.get("발주기관", "")).strip()
        result.announcement_number = str(basic.get("공고번호", "")).strip()
        result.deadline = str(basic.get("제출마감일", "")).strip()
        result.project_period = str(basic.get("사업기간", "")).strip()
        result.budget = str(basic.get("예산", "")).strip()

        # 자격요건 파싱
        requirements = data.get("자격요건", [])
        if not isinstance(requirements, list):
            raise RFxParseError("'자격요건'은 배열(list)이어야 합니다.")
        for req in requirements:
            if not isinstance(req, dict):
                continue
            description = str(req.get("요건", "")).strip()
            if not description:
                continue
            raw_constraints = req.get("constraints", [])
            parsed_constraints = []
            if isinstance(raw_constraints, list):
                for c in raw_constraints:
                    if not isinstance(c, dict):
                        continue
                    metric = str(c.get("metric", "CUSTOM")).strip() or "CUSTOM"
                    op = str(c.get("op", "")).strip()
                    if op not in (">=", ">", "<=", "<", "==", "!=", "in", "not_in"):
                        metric = "CUSTOM"  # 잘못된 op → SKIP 경로 (강제 치환 금지)
                    value = c.get("value")
                    # strict 모드: value는 항상 string으로 수신 → native 타입 복원
                    if isinstance(value, str):
                        try:
                            parsed = json.loads(value)
                            if not isinstance(parsed, dict):
                                value = parsed
                        except (json.JSONDecodeError, ValueError):
                            pass
                    if value is None or isinstance(value, (dict, list)):
                        metric = "CUSTOM"  # 누락/타입 불일치 → SKIP 경로 (기본값 0 금지)
                    parsed_constraints.append(RFxConstraint(
                        metric=metric,
                        op=op,
                        value=value,
                        unit=str(c.get("unit", "")).strip(),
                        raw=str(c.get("raw", "")).strip(),
                    ))
            result.requirements.append(RFxRequirement(
                category=str(req.get("분류", "기타")).strip() or "기타",
                description=description,
                is_mandatory=self._parse_mandatory_flag(req.get("필수여부", "필수")),
                detail=str(req.get("상세", "")).strip(),
                constraints=parsed_constraints,
            ))

        # 평가기준 파싱
        criteria = data.get("평가기준", [])
        if isinstance(criteria, list):
            for crit in criteria:
                if not isinstance(crit, dict):
                    continue
                try:
                    score = float(crit.get("배점", 0))
                except (TypeError, ValueError):
                    score = 0.0
                result.evaluation_criteria.append(RFxEvaluationCriteria(
                    category=str(crit.get("분류", "기타")).strip() or "기타",
                    item=str(crit.get("항목", "")).strip(),
                    score=score,
                    detail=str(crit.get("상세", "")).strip()
                ))

        # 제출서류, 특이사항
        required_documents = data.get("제출서류", [])
        special_notes = data.get("특이사항", [])
        result.required_documents = [str(x).strip() for x in required_documents] if isinstance(required_documents, list) else []
        result.special_notes = [str(x).strip() for x in special_notes] if isinstance(special_notes, list) else []

        self._validate_parsed_result(result, require_requirements=False)
        return result
