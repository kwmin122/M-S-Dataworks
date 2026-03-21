"""Performance budgets and timeout configuration."""

# Generation time targets (seconds)
GENERATION_TIME_TARGETS: dict[str, int] = {
    "proposal": 180,        # 3 minutes
    "execution_plan": 120,  # 2 minutes
    "track_record": 60,     # 1 minute
    "presentation": 120,    # 2 minutes
}

# Hard timeout (seconds) — abort if exceeded
GENERATION_HARD_TIMEOUT: int = 300  # 5 minutes

# Per-section timeout (seconds)
SECTION_TIMEOUT: int = 90

# Model cost tiers
MODEL_COST_TIERS: dict[str, dict] = {
    "gpt-4o": {
        "quality": "high",
        "cost_per_1k": 0.005,
        "recommended_for": ["proposal"],
    },
    "gpt-4o-mini": {
        "quality": "good",
        "cost_per_1k": 0.00015,
        "recommended_for": ["execution_plan", "track_record", "presentation"],
    },
}
