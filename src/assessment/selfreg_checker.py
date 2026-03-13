"""
Check 5: Self-Registration Exposure

Maps to: Salesforce Advisory Recommendation #5 — "Disable Self-Registration if Not Required"

Tests whether the self-registration endpoint is accessible and functional.
An open self-registration endpoint allows privilege escalation from unauthenticated
guest access to an authenticated portal session.
"""

from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger(__name__)

SELF_REG_PATHS = [
    "/s/login/SelfRegister",
    "/CommunitiesSelfReg",
    "/s/selfregister",
    "/register",
]

SELF_REG_INDICATORS = [
    "SelfRegister",
    "selfregister",
    "CommunitiesSelfReg",
    "createPortalUser",
    "registerUser",
    "First Name",
    "Last Name",
    "Create Account",
    "Sign Up",
]

TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


@dataclass
class SelfRegResult:
    enabled: bool
    endpoint_url: str | None
    http_status: int | None
    error: str | None = None

    @property
    def severity(self) -> str:
        return "medium" if self.enabled else "none"


class SelfRegChecker:
    """
    Checks for accessible self-registration endpoints.
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)

    async def check(self, domain: str) -> SelfRegResult:
        """Check if self-registration is enabled for the given domain."""
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False,
        ) as client:
            for path in SELF_REG_PATHS:
                url = f"https://{domain}{path}"
                try:
                    response = await client.get(
                        url,
                        headers={"Accept": "text/html"},
                    )

                    if response.status_code == 200:
                        body = response.text[:5000]
                        if any(indicator in body for indicator in SELF_REG_INDICATORS):
                            self.log.warning(
                                "selfreg.enabled",
                                domain=domain,
                                endpoint=url,
                            )
                            return SelfRegResult(
                                enabled=True,
                                endpoint_url=url,
                                http_status=response.status_code,
                            )

                except Exception:
                    continue

        return SelfRegResult(
            enabled=False,
            endpoint_url=None,
            http_status=None,
        )
