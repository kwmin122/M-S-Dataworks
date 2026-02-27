from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.web_app.alert_matcher import apply_metadata_filters  # noqa: E402

def test_keyword_match():
    """Keywords in title should match"""
    bid = {"title": "교통신호등 설치 공사", "category": "물품"}
    rule = {"keywords": ["교통신호등"], "excludeKeywords": []}

    assert apply_metadata_filters(bid, rule) is True

def test_exclude_keyword_blocks():
    """Exclude keywords should block"""
    bid = {"title": "교통신호등 유지보수"}
    rule = {"keywords": ["교통신호등"], "excludeKeywords": ["유지보수"]}

    assert apply_metadata_filters(bid, rule) is False

def test_exclude_region_blocks():
    """Exclude regions should block"""
    bid = {"title": "신호등 설치", "region": "안산"}
    rule = {"keywords": ["신호등"], "excludeRegions": ["안산", "부산"]}

    assert apply_metadata_filters(bid, rule) is False

def test_product_code_matching():
    """Product codes in attachmentText should match"""
    bid = {
        "title": "CCTV 구매",
        "attachmentText": "물품분류번호: 42101\n기타 내용..."
    }
    rule = {"keywords": ["CCTV"], "productCodes": ["42101"]}

    assert apply_metadata_filters(bid, rule) is True

def test_product_code_not_found_blocks():
    """Missing product code should block"""
    bid = {"title": "CCTV 구매", "attachmentText": "물품분류번호: 99999"}
    rule = {"keywords": ["CCTV"], "productCodes": ["42101"]}

    assert apply_metadata_filters(bid, rule) is False

def test_detailed_items_matching():
    """Detailed item names should match"""
    bid = {"title": "교통신호등 주 제조 구매"}
    rule = {"keywords": ["신호등"], "detailedItems": ["교통신호등 주"]}

    assert apply_metadata_filters(bid, rule) is True

def test_amount_range_filtering():
    """Amount range should filter correctly"""
    bid = {"title": "공사", "estimatedAmt": 100000000}

    # Within range
    rule1 = {"keywords": ["공사"], "minAmt": 50000000, "maxAmt": 200000000}
    assert apply_metadata_filters(bid, rule1) is True

    # Below minimum
    rule2 = {"keywords": ["공사"], "minAmt": 150000000}
    assert apply_metadata_filters(bid, rule2) is False

    # Above maximum
    rule3 = {"keywords": ["공사"], "maxAmt": 50000000}
    assert apply_metadata_filters(bid, rule3) is False

def test_all_filters_combined():
    """Complex rule with multiple filters"""
    bid = {
        "title": "교통신호등 주 설치",
        "category": "물품",
        "region": "서울",
        "estimatedAmt": 80000000,
        "attachmentText": "물품분류번호: 42101"
    }

    rule = {
        "keywords": ["교통신호등"],
        "excludeKeywords": ["유지보수"],
        "regions": ["서울", "경기"],
        "excludeRegions": ["안산"],
        "productCodes": ["42101"],
        "detailedItems": ["교통신호등 주"],
        "minAmt": 50000000,
        "maxAmt": 100000000,
    }

    assert apply_metadata_filters(bid, rule) is True
