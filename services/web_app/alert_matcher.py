from typing import Any

def apply_metadata_filters(bid: dict[str, Any], rule: dict[str, Any]) -> bool:
    """
    메타데이터 기반 1차 필터링.

    Returns:
        True if bid matches rule, False otherwise
    """

    # 1. 키워드 매칭
    text = f"{bid.get('title', '')} {bid.get('category', '')}".lower()

    # 포함 키워드 체크
    keywords = rule.get("keywords", [])
    if keywords:
        if not any(kw.lower() in text for kw in keywords):
            return False

    # 제외 키워드 체크 (우선순위 높음)
    exclude_keywords = rule.get("excludeKeywords", [])
    if exclude_keywords:
        if any(kw.lower() in text for kw in exclude_keywords):
            return False

    # 2. 지역 필터
    regions = rule.get("regions", [])
    if regions:
        if bid.get("region") not in regions:
            return False

    # 3. 제외 지역 (우선순위 높음)
    exclude_regions = rule.get("excludeRegions", [])
    if exclude_regions:
        if bid.get("region") in exclude_regions:
            return False

    # 4. 물품분류번호
    product_codes = rule.get("productCodes", [])
    if product_codes:
        attachment = bid.get("attachmentText", "").lower()
        if not any(code in attachment for code in product_codes):
            return False

    # 5. 세부품명
    detailed_items = rule.get("detailedItems", [])
    if detailed_items:
        if not any(item.lower() in text for item in detailed_items):
            return False

    # 6. 금액 범위
    min_amt = rule.get("minAmt")
    max_amt = rule.get("maxAmt")
    bid_amt = bid.get("estimatedAmt", 0)

    if min_amt is not None and bid_amt < min_amt:
        return False
    if max_amt is not None and bid_amt > max_amt:
        return False

    return True

def matches_any_rule(bid: dict[str, Any], rules: list[dict[str, Any]]) -> bool:
    """Check if bid matches ANY of the rules"""
    if not rules:
        return False

    for rule in rules:
        if not rule.get("enabled", True):
            continue

        if apply_metadata_filters(bid, rule):
            return True

    return False
