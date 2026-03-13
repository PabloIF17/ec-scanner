import pytest
from src.assessment.risk_scorer import RiskScorer


def test_critical_score():
    scorer = RiskScorer()
    checks = {
        "aura_endpoint": {"is_open": True},
        "object_access": [
            {"object": "User", "accessible": True, "priority": "critical", "sensitive_fields": [{"severity": "critical"}]},
            {"object": "Contact", "accessible": True, "priority": "critical", "sensitive_fields": []},
        ],
        "user_enumeration": {"vulnerable": True},
        "self_registration": {"enabled": True},
        "apex_exposure": {"potentially_unsafe": 1},
        "file_exposure": {"content_accessible": True},
    }
    result = scorer.score(checks)
    assert result.score >= 70
    assert result.severity in ("CRITICAL", "HIGH")
    assert len(result.remediation_summary) > 0


def test_minimal_score_when_aura_closed():
    scorer = RiskScorer()
    checks = {
        "aura_endpoint": {"is_open": False},
        "object_access": [],
        "user_enumeration": {"vulnerable": False},
        "self_registration": {"enabled": False},
        "apex_exposure": {"potentially_unsafe": 0},
        "file_exposure": {"content_accessible": False},
    }
    result = scorer.score(checks)
    assert result.score == 0
    assert result.severity == "MINIMAL"


def test_medium_score_with_selfreg_only():
    scorer = RiskScorer()
    checks = {
        "aura_endpoint": {"is_open": False},
        "object_access": [],
        "user_enumeration": {"vulnerable": False},
        "self_registration": {"enabled": True},
        "apex_exposure": {"potentially_unsafe": 0},
        "file_exposure": {"content_accessible": False},
    }
    result = scorer.score(checks)
    assert result.score == 5  # Only self-reg weight
