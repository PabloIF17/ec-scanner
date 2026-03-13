"""
Assessment Pipeline Orchestrator

Runs all 7 security checks against a confirmed Experience Cloud site
and produces a structured risk-scored assessment report.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Assessment, Site
from src.assessment.aura_probe import AuraProbe
from src.assessment.object_enumerator import ObjectEnumerator
from src.assessment.field_analyzer import FieldAnalyzer
from src.assessment.user_enumerator import UserEnumerator
from src.assessment.selfreg_checker import SelfRegChecker
from src.assessment.apex_detector import ApexDetector
from src.assessment.file_checker import FileChecker
from src.assessment.risk_scorer import RiskScorer

logger = structlog.get_logger(__name__)


class AssessmentPipeline:
    """
    Orchestrates all security checks for a single Experience Cloud site.

    Check execution order:
    1. Aura Endpoint (gateway check — all subsequent checks depend on this)
    2. Object Access Enumeration (requires Aura open)
    3. Sensitive Field Analysis (requires Check 2)
    4. User Enumeration (requires Aura open)
    5. Self-Registration Check (independent)
    6. Apex/VF Exposure (requires Aura open)
    7. File Exposure (requires Aura open)
    8. Risk Scoring (aggregates all checks)
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)
        self.risk_scorer = RiskScorer()
        self.field_analyzer = FieldAnalyzer()

    async def run(self, site: Site, db: AsyncSession) -> Assessment:
        """Run the complete assessment pipeline for a site."""
        start = datetime.now(timezone.utc)
        domain = site.domain
        log = self.log.bind(domain=domain, site_id=str(site.id))
        log.info("assessment.started")

        checks: dict[str, Any] = {}
        error_message: str | None = None

        try:
            # Check 1: Aura endpoint
            aura_probe = AuraProbe()
            aura_result = await aura_probe.probe(domain)
            checks["aura_endpoint"] = {
                "is_open": aura_result.is_open,
                "endpoint_url": aura_result.endpoint_url,
                "response_code": aura_result.response_code,
                "response_type": aura_result.response_type,
                "severity": aura_result.severity,
            }
            log.info("assessment.check1_complete", aura_open=aura_result.is_open)

            # Checks 2, 4, 6, 7 require Aura endpoint to be open
            if aura_result.is_open and aura_result.endpoint_url:
                endpoint = aura_result.endpoint_url

                # Check 2: Object enumeration
                obj_enumerator = ObjectEnumerator(endpoint, fwuid=aura_result.fwuid)
                obj_result = await obj_enumerator.enumerate()

                # Check 3: Field analysis (runs on results from Check 2)
                field_results = []
                for obj in obj_result.accessible_objects:
                    if obj.fields_returned:
                        analysis = self.field_analyzer.analyze(
                            obj.object_api_name, obj.fields_returned
                        )
                        field_results.append({
                            "object": obj.object_api_name,
                            "sensitive_fields": [
                                {
                                    "field": f.field_name,
                                    "category": f.category,
                                    "severity": f.severity,
                                }
                                for f in analysis.sensitive_fields
                            ],
                        })

                checks["object_access"] = [
                    {
                        "object": obj.object_api_name,
                        "priority": obj.priority,
                        "accessible": obj.accessible,
                        "record_count_approx": obj.record_count_approx,
                        "fields_returned": obj.fields_returned,
                        "sensitive_fields": next(
                            (
                                fr["sensitive_fields"]
                                for fr in field_results
                                if fr["object"] == obj.object_api_name
                            ),
                            [],
                        ),
                        "severity": obj.severity,
                    }
                    for obj in obj_result.objects
                ]
                log.info(
                    "assessment.check2_complete",
                    accessible=len(obj_result.accessible_objects),
                )

                # Check 4: User enumeration
                user_enumerator = UserEnumerator(endpoint)
                user_result = await user_enumerator.check()
                checks["user_enumeration"] = {
                    "vulnerable": user_result.vulnerable,
                    "users_visible": user_result.users_visible,
                    "fields_exposed": user_result.fields_exposed,
                    "severity": user_result.severity,
                }

                # Check 6: Apex/VF exposure
                apex_detector = ApexDetector(endpoint)
                apex_result = await apex_detector.detect(domain)
                checks["apex_exposure"] = {
                    "custom_actions_found": apex_result.custom_actions_found,
                    "potentially_unsafe": apex_result.potentially_unsafe,
                    "action_names": apex_result.action_names,
                    "severity": apex_result.severity,
                }

                # Check 7: File exposure
                file_checker = FileChecker(endpoint)
                file_result = await file_checker.check()
                checks["file_exposure"] = {
                    "content_accessible": file_result.content_accessible,
                    "content_version_accessible": file_result.content_version_accessible,
                    "content_document_accessible": file_result.content_document_accessible,
                    "severity": file_result.severity,
                }

            else:
                # Aura is closed — mark subsequent checks as not applicable
                checks["object_access"] = []
                checks["user_enumeration"] = {"vulnerable": False, "severity": "none"}
                checks["apex_exposure"] = {"custom_actions_found": 0, "potentially_unsafe": 0, "severity": "none"}
                checks["file_exposure"] = {"content_accessible": False, "severity": "none"}

            # Check 5: Self-registration (independent of Aura)
            selfreg_checker = SelfRegChecker()
            selfreg_result = await selfreg_checker.check(domain)
            checks["self_registration"] = {
                "enabled": selfreg_result.enabled,
                "endpoint_url": selfreg_result.endpoint_url,
                "http_status": selfreg_result.http_status,
                "severity": selfreg_result.severity,
            }

            # Risk scoring
            risk = self.risk_scorer.score(checks)

        except Exception as e:
            log.error("assessment.error", error=str(e))
            error_message = str(e)
            risk = self.risk_scorer.score(checks)

        elapsed = int((datetime.now(timezone.utc) - start).total_seconds())

        # Create assessment record
        assessment = Assessment(
            id=uuid.uuid4(),
            site_id=site.id,
            assessment_date=datetime.now(timezone.utc),
            risk_score=risk.score,
            severity=risk.severity,
            checks=checks,
            remediation_summary=risk.remediation_summary,
            scan_duration_seconds=elapsed,
            error_message=error_message,
        )
        db.add(assessment)

        # Update site assessment status
        site.assessment_status = "complete"

        await db.flush()

        log.info(
            "assessment.complete",
            risk_score=risk.score,
            severity=risk.severity,
            duration_seconds=elapsed,
        )

        return assessment
