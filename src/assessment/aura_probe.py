"""
Check 1: Aura Endpoint Accessibility

Maps to: Salesforce Advisory Recommendation #3 — "Disable Public APIs"

Tests whether the /s/sfsites/aura endpoint accepts unauthenticated API queries.
This is the primary attack vector per the March 2026 Salesforce security advisory.

IMPORTANT: Only sends requests to publicly-accessible endpoints. Does not attempt
authentication, credential bruteforce, or any exploitation beyond observing
what is exposed to the public internet.
"""

from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger(__name__)

AURA_PATHS = [
    "/s/sfsites/aura",
    "/aura",
    "/s/aura",
]

# Standard Aura action payload for endpoint discovery
# Uses aura://RecordUiController as it's a standard framework component
AURA_PROBE_PAYLOAD = (
    "message=%7B%22actions%22%3A%5B%7B%22id%22%3A%220%22%2C%22descriptor%22%3A%22"
    "aura%3A%2F%2FRecordUiController%2FACTION%24getObjectInfo%22%2C%22callingDescriptor%22%3A%22UNKNOWN%22%2C%22params%22%3A%7B%7D%7D%5D%7D"
    "&aura.context=%7B%22mode%22%3A%22PROD%22%2C%22fwuid%22%3A%22%22%2C%22app%22%3A%22siteforce%3AcommunityApp%22%2C%22loaded%22%3A%7B%7D%7D"
    "&aura.token=undefined"
)

# Patterns that indicate an Aura framework response (endpoint is open)
AURA_RESPONSE_INDICATORS = [
    '"actions"',
    '"events"',
    '"errors"',
    '"aura:invalidSession"',
    '"exceptionMessage"',
    "aura",
    "siteforce",
]

# Patterns that indicate Aura is present but blocked
AURA_BLOCKED_INDICATORS = [
    '"aura:clientOutOfSync"',
]

TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


@dataclass
class AuraProbeResult:
    is_open: bool
    endpoint_url: str | None
    response_code: int | None
    response_type: str
    fwuid: str | None
    error: str | None

    @property
    def severity(self) -> str:
        return "critical" if self.is_open else "none"


class AuraProbe:
    """
    Probes the Salesforce Aura endpoint to determine if guest API access is enabled.

    A response in Aura's own JSON format — even an error — indicates the endpoint
    is active and accepting unauthenticated requests. This is the vulnerability.
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger(__name__)

    async def probe(self, domain: str) -> AuraProbeResult:
        """
        Probe all known Aura endpoint paths for the given domain.
        Returns the first open endpoint found, or a closed result.
        """
        # First, try to extract fwuid from the page (needed for valid Aura context)
        fwuid = await self._extract_fwuid(domain)

        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False,
        ) as client:
            for path in AURA_PATHS:
                url = f"https://{domain}{path}"
                try:
                    result = await self._probe_endpoint(client, url, fwuid)
                    if result.is_open:
                        self.log.warning(
                            "aura.endpoint_open",
                            domain=domain,
                            endpoint=url,
                        )
                        return result
                except Exception as e:
                    self.log.debug("aura.probe_failed", domain=domain, path=path, error=str(e))

        return AuraProbeResult(
            is_open=False,
            endpoint_url=None,
            response_code=None,
            response_type="blocked",
            fwuid=fwuid,
            error=None,
        )

    async def _probe_endpoint(
        self, client: httpx.AsyncClient, url: str, fwuid: str | None
    ) -> AuraProbeResult:
        """Send a probe request to an Aura endpoint URL."""
        payload = AURA_PROBE_PAYLOAD
        if fwuid:
            # Inject the actual fwuid for a more realistic request
            payload = payload.replace(
                "%22fwuid%22%3A%22%22",
                f"%22fwuid%22%3A%22{fwuid}%22",
            )

        response = await client.post(
            url,
            content=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        is_open = self._is_aura_response(response)
        response_type = self._classify_response(response)

        return AuraProbeResult(
            is_open=is_open,
            endpoint_url=url,
            response_code=response.status_code,
            response_type=response_type,
            fwuid=fwuid,
            error=None,
        )

    def _is_aura_response(self, response: httpx.Response) -> bool:
        """
        Determine if the response is an Aura framework response.

        An Aura response means the endpoint is accepting unauthenticated requests.
        Even error responses (e.g., "Invalid session") are Aura responses.
        A generic 404 or HTML page is NOT an Aura response.
        """
        if response.status_code not in (200, 400, 401, 403):
            return False

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type and "text/plain" not in content_type:
            # Could still be Aura if content contains JSON
            pass

        try:
            body = response.text[:2000]  # Only inspect first 2KB
            return any(indicator in body for indicator in AURA_RESPONSE_INDICATORS)
        except Exception:
            return False

    def _classify_response(self, response: httpx.Response) -> str:
        """Classify the type of response received."""
        try:
            body = response.text[:500]
        except Exception:
            return "unknown"

        if any(indicator in body for indicator in AURA_RESPONSE_INDICATORS):
            return "aura_framework"
        if response.status_code == 404:
            return "not_found"
        if response.status_code == 403:
            return "forbidden"
        return "non_aura"

    async def _extract_fwuid(self, domain: str) -> str | None:
        """
        Extract the Aura framework UID from the site's homepage.
        The fwuid is embedded in the auraConfig script tag in the HTML source.
        """
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
                verify=False,
            ) as client:
                response = await client.get(
                    f"https://{domain}",
                    headers={"Accept": "text/html"},
                )
                body = response.text

                # Look for fwuid in auraConfig
                import re
                match = re.search(r'"fwuid"\s*:\s*"([^"]+)"', body)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return None
