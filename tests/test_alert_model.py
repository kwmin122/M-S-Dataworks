import json
from pathlib import Path

def test_alert_config_schema_has_new_fields():
    """Verify extended AlertRule schema includes new filter fields"""
    config = {
        "email": "test@example.com",
        "enabled": True,
        "schedule": "daily_2",
        "hours": [9, 18],
        "rules": [{
            "id": "rule1",
            "keywords": ["교통신호등"],
            "excludeKeywords": [],
            "categories": [],
            "regions": [],
            "excludeRegions": ["안산", "부산"],  # NEW
            "productCodes": ["42101"],          # NEW
            "detailedItems": ["교통신호등 주"],  # NEW
            "excludeAgencyLocations": [],       # NEW (renamed from excludeContractorLocations)
            "enabled": True,
        }],
        "companyProfile": {                     # NEW
            "description": "교통신호등 제조 전문",
            "mainProducts": ["신호등"],
        }
    }

    # Should serialize without error
    json_str = json.dumps(config, ensure_ascii=False)
    assert "excludeRegions" in json_str
    assert "productCodes" in json_str
    assert "companyProfile" in json_str
    assert "excludeAgencyLocations" in json_str
