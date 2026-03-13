"""
Check 3: Sensitive Field Exposure

Maps to: Salesforce FLS Best Practices in the Spring '26 Guide

Analyzes field names returned from accessible objects and flags sensitive fields.
IMPORTANT: Only inspects field NAMES (metadata), never actual field values.
"""

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# Sensitive field patterns by category
SENSITIVE_PATTERNS: dict[str, list[str]] = {
    "email": [r"email", r".*email.*"],
    "phone": [r"phone", r"mobilephone", r"fax", r".*phone.*"],
    "address": [
        r"mailingaddress", r"billingaddress", r"shippingaddress",
        r".*street.*", r".*city.*", r".*state.*", r".*postalcode.*", r".*zip.*",
    ],
    "financial": [
        r"annualrevenue", r"amount", r".*revenue.*", r".*price.*", r".*cost.*",
        r".*salary.*", r".*budget.*",
    ],
    "identity": [
        r".*ssn.*", r".*taxid.*", r".*socialsecurity.*", r".*nationalid.*",
        r".*passport.*", r".*driverslicense.*", r".*ein.*",
    ],
    "internal": [
        r"description", r"internalcomments", r".*notes.*", r".*internal.*",
        r".*comment.*", r".*private.*",
    ],
}

SEVERITY_MAP = {
    "email": "critical",
    "phone": "high",
    "address": "high",
    "financial": "high",
    "identity": "critical",
    "internal": "medium",
}


@dataclass
class SensitiveField:
    field_name: str
    category: str
    severity: str


@dataclass
class FieldAnalysisResult:
    object_api_name: str
    all_fields: list[str]
    sensitive_fields: list[SensitiveField] = field(default_factory=list)

    @property
    def has_sensitive_fields(self) -> bool:
        return len(self.sensitive_fields) > 0

    @property
    def highest_severity(self) -> str:
        severities = [f.severity for f in self.sensitive_fields]
        if "critical" in severities:
            return "critical"
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"


class FieldAnalyzer:
    """
    Analyzes field names returned from accessible Salesforce objects
    to identify potentially sensitive data exposure.

    Only examines field names (schema metadata), never actual values.
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)
        self._compiled = self._compile_patterns()

    def _compile_patterns(self) -> dict[str, list[re.Pattern]]:
        return {
            category: [re.compile(p, re.IGNORECASE) for p in patterns]
            for category, patterns in SENSITIVE_PATTERNS.items()
        }

    def analyze(self, object_api_name: str, field_names: list[str]) -> FieldAnalysisResult:
        """Analyze field names for sensitive data patterns."""
        sensitive: list[SensitiveField] = []

        for field_name in field_names:
            field_lower = field_name.lower()

            for category, patterns in self._compiled.items():
                if any(p.fullmatch(field_lower) for p in patterns):
                    sensitive.append(
                        SensitiveField(
                            field_name=field_name,
                            category=category,
                            severity=SEVERITY_MAP[category],
                        )
                    )
                    break  # Only flag each field once (first matching category)

            # Also flag custom fields (*__c) containing sensitive name patterns
            if field_name.endswith("__c"):
                base_name = field_name[:-3].lower()
                for category, patterns in self._compiled.items():
                    if any(p.search(base_name) for p in patterns):
                        if not any(s.field_name == field_name for s in sensitive):
                            sensitive.append(
                                SensitiveField(
                                    field_name=field_name,
                                    category=f"custom_{category}",
                                    severity=SEVERITY_MAP[category],
                                )
                            )
                        break

        if sensitive:
            self.log.warning(
                "field_analysis.sensitive_found",
                object=object_api_name,
                count=len(sensitive),
            )

        return FieldAnalysisResult(
            object_api_name=object_api_name,
            all_fields=field_names,
            sensitive_fields=sensitive,
        )

    def analyze_all(
        self, objects: list[tuple[str, list[str]]]
    ) -> list[FieldAnalysisResult]:
        """Analyze field names for multiple objects."""
        return [self.analyze(obj_name, fields) for obj_name, fields in objects]
