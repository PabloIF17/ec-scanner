"""
Check 6: Apex & Visualforce Exposure

Maps to: Salesforce code-level best practices in the Spring '26 Guide

Probes for custom Apex controllers accessible to guest users.
Flags potential "without sharing" Apex exposure risks.
"""

import json
import urllib.parse
from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger(__name__)

TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

# Common Apex controller descriptor patterns to probe
APEX_PROBE_DESCRIPTORS = [
    "apex://",
    "c:",  # Custom Lightning Web Components
    "c/",
]


@dataclass
class ApexExposureResult:
    custom_actions_found: int
    potentially_unsafe: int
    action_names: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def severity(self) -> str:
        if self.custom_actions_found == 0:
            return "none"
        if self.potentially_unsafe > 0:
            return "medium"
        return "low"


class ApexDetector:
    """
    Detects custom Apex controllers accessible via the Aura endpoint.
    """

    def __init__(self, endpoint_url: str) -> None:
        self.endpoint_url = endpoint_url
        self.log = structlog.get_logger(__name__)

    async def detect(self, domain: str) -> ApexExposureResult:
        """Probe for custom Apex controller exposure."""
        try:
            custom_actions = await self._discover_app_descriptors(domain)
            unsafe_count = self._assess_risk(custom_actions)

            if custom_actions:
                self.log.info(
                    "apex.custom_actions_found",
                    domain=domain,
                    count=len(custom_actions),
                    unsafe=unsafe_count,
                )

            return ApexExposureResult(
                custom_actions_found=len(custom_actions),
                potentially_unsafe=unsafe_count,
                action_names=custom_actions[:10],  # Store up to 10 action names
            )

        except Exception as e:
            return ApexExposureResult(
                custom_actions_found=0,
                potentially_unsafe=0,
                error=str(e),
            )

    async def _discover_app_descriptors(self, domain: str) -> list[str]:
        """
        Attempt to discover custom Aura descriptors by analyzing the app's
        bootstrap response.
        """
        custom_actions: list[str] = []

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
                verify=False,
            ) as client:
                # The app bootstrap endpoint often reveals registered components
                response = await client.get(
                    f"https://{domain}/s/",
                    headers={"Accept": "text/html"},
                )
                body = response.text[:100000]

                import re
                # Look for Apex controller references in the page source
                apex_refs = re.findall(r'"descriptor"\s*:\s*"(apex://[^"]+)"', body)
                custom_refs = re.findall(r'"descriptor"\s*:\s*"(c:[^"]+)"', body)

                for ref in apex_refs + custom_refs:
                    if ref not in custom_actions:
                        custom_actions.append(ref)

        except Exception:
            pass

        return custom_actions

    def _assess_risk(self, action_names: list[str]) -> int:
        """
        Estimate how many discovered actions might be running without sharing.
        This is a heuristic based on common patterns.
        """
        potentially_unsafe = 0
        risk_patterns = ["getData", "getRecords", "query", "search", "fetch", "load", "get"]

        for action in action_names:
            action_lower = action.lower()
            if any(p in action_lower for p in risk_patterns):
                potentially_unsafe += 1

        return potentially_unsafe
