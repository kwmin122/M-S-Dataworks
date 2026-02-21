from pydantic import BaseModel
from typing import Any


class AnalyzeBidRequest(BaseModel):
    organization_id: str
    bid_notice_id: str
    company_facts: dict[str, Any]
    attachment_text: str


class EvaluationDetails(BaseModel):
    missingLicenses: list[str] = []
    insufficientCapital: bool = False
    regionMismatch: bool = False
    confidenceScore: float = 1.0


class AnalyzeBidResponse(BaseModel):
    is_eligible: bool
    details: dict[str, Any]
    action_plan: str
