"""
Risk Scoring Engine

Produces a composite risk score (0-100) based on all assessment check results.
Scoring weights map directly to the requirements specification.
"""

from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

# Scoring weights per check (total max = 100)
WEIGHTS = {
    "aura_open": 30,
    "critical_objects": 25,  # User, Contact, Account
    "high_objects": 15,  # Opportunity, Case, Lead
    "sensitive_fields": 10,
    "user_enumeration": 10,
    "self_registration": 5,
    "apex_exposure": 3,
    "file_exposure": 2,
}

SEVERITY_THRESHOLDS = [
    (90, "CRITICAL"),
    (70, "HIGH"),
    (50, "MEDIUM"),
    (30, "LOW"),
    (0, "MINIMAL"),
]


@dataclass
class RiskScore:
    score: int
    severity: str
    score_breakdown: dict[str, int]
    remediation_summary: list[str]


class RiskScorer:
    """
    Computes composite risk score from all assessment check results.
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)

    def score(self, checks: dict) -> RiskScore:
        """
        Compute risk score from the checks results dict.

        Expected checks structure:
        {
            "aura_endpoint": {"is_open": bool, ...},
            "object_access": [{"object": str, "accessible": bool, "priority": str, ...}],
            "user_enumeration": {"vulnerable": bool, ...},
            "self_registration": {"enabled": bool, ...},
            "apex_exposure": {"custom_actions_found": int, "potentially_unsafe": int, ...},
            "file_exposure": {"content_accessible": bool, ...},
        }
        """
        breakdown: dict[str, int] = {}
        remediation: list[str] = []

        # Check 1: Aura endpoint open (30 pts)
        aura = checks.get("aura_endpoint", {})
        aura_open = aura.get("is_open", False)
        if aura_open:
            breakdown["aura_open"] = WEIGHTS["aura_open"]
            remediation.append(
                "CRITICAL: Disable 'Allow guest users to access public APIs' and uncheck "
                "'API Enabled' in the guest user profile's System Permissions."
            )
        else:
            breakdown["aura_open"] = 0

        # Check 2: Object access — critical objects (25 pts)
        objects = checks.get("object_access", [])
        accessible_objects = [o for o in objects if o.get("accessible", False)]
        critical_objects = [o for o in accessible_objects if o.get("priority") == "critical"]
        high_objects = [o for o in accessible_objects if o.get("priority") == "high"]

        if critical_objects:
            breakdown["critical_objects"] = WEIGHTS["critical_objects"]
            obj_names = [o["object"] for o in critical_objects]
            remediation.append(
                f"CRITICAL: Remove Read access to {', '.join(obj_names)} objects "
                f"from the guest user profile."
            )
        else:
            breakdown["critical_objects"] = 0

        # Check 2: High-priority objects (15 pts)
        if high_objects:
            breakdown["high_objects"] = WEIGHTS["high_objects"]
            obj_names = [o["object"] for o in high_objects]
            remediation.append(
                f"HIGH: Review and remove access to {', '.join(obj_names)} objects "
                f"from the guest user profile."
            )
        else:
            breakdown["high_objects"] = 0

        # Check 3: Sensitive field exposure (10 pts)
        has_sensitive_fields = any(
            len(o.get("sensitive_fields", [])) > 0 for o in accessible_objects
        )
        if has_sensitive_fields:
            breakdown["sensitive_fields"] = WEIGHTS["sensitive_fields"]
            remediation.append(
                "HIGH: Review Field-Level Security (FLS) on the guest user profile. "
                "Remove access to sensitive fields (email, phone, address, financial)."
            )
        else:
            breakdown["sensitive_fields"] = 0

        # Check 4: User enumeration (10 pts)
        user_enum = checks.get("user_enumeration", {})
        if user_enum.get("vulnerable", False):
            breakdown["user_enumeration"] = WEIGHTS["user_enumeration"]
            remediation.append(
                "CRITICAL: In Sharing Settings, uncheck 'Portal User Visibility' and "
                "'Site User Visibility' to prevent guest users from enumerating internal users."
            )
        else:
            breakdown["user_enumeration"] = 0

        # Check 5: Self-registration (5 pts)
        self_reg = checks.get("self_registration", {})
        if self_reg.get("enabled", False):
            breakdown["self_registration"] = WEIGHTS["self_registration"]
            remediation.append(
                "MEDIUM: Disable self-registration if not required. Navigate to Setup > "
                "All Sites > [Your Site] > Workspaces > Administration > Login & Registration."
            )
        else:
            breakdown["self_registration"] = 0

        # Check 6: Apex exposure (3 pts)
        apex = checks.get("apex_exposure", {})
        if apex.get("potentially_unsafe", 0) > 0:
            breakdown["apex_exposure"] = WEIGHTS["apex_exposure"]
            remediation.append(
                "LOW: Review custom Apex controllers for 'with sharing' enforcement. "
                "Ensure all @AuraEnabled methods accessible to guest users use 'with sharing'."
            )
        else:
            breakdown["apex_exposure"] = 0

        # Check 7: File exposure (2 pts)
        file_exp = checks.get("file_exposure", {})
        if file_exp.get("content_accessible", False):
            breakdown["file_exposure"] = WEIGHTS["file_exposure"]
            remediation.append(
                "LOW: Set up a trigger to assign ownership to files uploaded by guest users. "
                "Review ContentVersion sharing settings."
            )
        else:
            breakdown["file_exposure"] = 0

        total_score = min(sum(breakdown.values()), 100)
        severity = self._get_severity(total_score)

        self.log.info(
            "risk_scorer.scored",
            score=total_score,
            severity=severity,
            aura_open=aura_open,
        )

        return RiskScore(
            score=total_score,
            severity=severity,
            score_breakdown=breakdown,
            remediation_summary=remediation,
        )

    def _get_severity(self, score: int) -> str:
        for threshold, severity in SEVERITY_THRESHOLDS:
            if score >= threshold:
                return severity
        return "MINIMAL"
