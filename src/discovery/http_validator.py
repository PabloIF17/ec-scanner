import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog

from src.discovery.dns_resolver import DNSResolution

logger = structlog.get_logger(__name__)

SALESFORCE_RESPONSE_HEADERS = [
    "x-salesforce-request-id",
    "x-sfdc-",
    "x-content-type-options",  # SF always sets this
]

SALESFORCE_HEADER_FINGERPRINTS = {
    "server": ["siteforce", "salesforce"],
    "x-powered-by": ["salesforce"],
}

SALESFORCE_CONTENT_PATTERNS = [
    "siteforce.com",
    "force.com",
    "salesforce.com",
    "aura.context",
    "sfsites",
]

TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


@dataclass
class HTTPValidation:
    domain: str
    is_live: bool
    http_status: int | None
    final_url: str | None
    redirect_target: str | None
    is_salesforce_confirmed: bool
    response_time_ms: int | None
    tls_issuer: str | None
    server_header: str | None
    error: str | None


class HTTPValidator:
    """
    HTTP validator that confirms discovered domains serve Salesforce Experience Cloud.
    Uses HEAD requests with Salesforce fingerprinting to confirm identity.
    """

    def __init__(self, rate_limit_ms: int = 500, concurrency: int = 20) -> None:
        self.rate_limit_ms = rate_limit_ms
        self.concurrency = concurrency
        self.log = structlog.get_logger(__name__)
        self._ua_index = 0

    def _next_ua(self) -> str:
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def validate_all(
        self, resolutions: list[DNSResolution]
    ) -> list[HTTPValidation]:
        """Validate all live, Salesforce-CNAME-resolved domains."""
        live_sf = [r for r in resolutions if r.is_alive and r.is_salesforce]
        self.log.info("http.validating", total=len(live_sf))

        semaphore = asyncio.Semaphore(self.concurrency)

        async def bounded_validate(resolution: DNSResolution) -> HTTPValidation:
            async with semaphore:
                return await self._validate_one(resolution)

        tasks = [bounded_validate(r) for r in live_sf]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        validations = []
        for resolution, result in zip(live_sf, results):
            if isinstance(result, Exception):
                validations.append(
                    HTTPValidation(
                        domain=resolution.domain,
                        is_live=False,
                        http_status=None,
                        final_url=None,
                        redirect_target=None,
                        is_salesforce_confirmed=False,
                        response_time_ms=None,
                        tls_issuer=None,
                        server_header=None,
                        error=str(result),
                    )
                )
            else:
                validations.append(result)

        confirmed = sum(1 for v in validations if v.is_salesforce_confirmed)
        self.log.info("http.validation_complete", total=len(validations), confirmed=confirmed)
        return validations

    async def _validate_one(self, resolution: DNSResolution) -> HTTPValidation:
        """Validate a single domain via HTTP HEAD request."""
        domain = resolution.domain
        start = datetime.now(timezone.utc)

        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False,  # Some SF Experience Cloud sites have cert issues
        ) as client:
            try:
                response = await client.head(
                    f"https://{domain}",
                    headers={"User-Agent": self._next_ua()},
                )
                elapsed_ms = int(
                    (datetime.now(timezone.utc) - start).total_seconds() * 1000
                )

                is_sf = self._is_salesforce_response(response)
                redirect_target = None
                if response.history:
                    redirect_target = str(response.url)

                server_header = response.headers.get("server")
                tls_issuer = None  # Would need cert inspection for this

                return HTTPValidation(
                    domain=domain,
                    is_live=True,
                    http_status=response.status_code,
                    final_url=str(response.url),
                    redirect_target=redirect_target,
                    is_salesforce_confirmed=is_sf,
                    response_time_ms=elapsed_ms,
                    tls_issuer=tls_issuer,
                    server_header=server_header,
                    error=None,
                )

            except httpx.ConnectError:
                return HTTPValidation(
                    domain=domain, is_live=False, http_status=None,
                    final_url=None, redirect_target=None,
                    is_salesforce_confirmed=False, response_time_ms=None,
                    tls_issuer=None, server_header=None, error="Connection failed"
                )
            except httpx.TimeoutException:
                return HTTPValidation(
                    domain=domain, is_live=False, http_status=None,
                    final_url=None, redirect_target=None,
                    is_salesforce_confirmed=False, response_time_ms=None,
                    tls_issuer=None, server_header=None, error="Timeout"
                )
            except Exception as e:
                return HTTPValidation(
                    domain=domain, is_live=False, http_status=None,
                    final_url=None, redirect_target=None,
                    is_salesforce_confirmed=False, response_time_ms=None,
                    tls_issuer=None, server_header=None, error=str(e)
                )

    def _is_salesforce_response(self, response: httpx.Response) -> bool:
        """Fingerprint the HTTP response to confirm Salesforce Experience Cloud."""
        headers_lower = {k.lower(): v.lower() for k, v in response.headers.items()}

        # Check response headers
        for header_name, patterns in SALESFORCE_HEADER_FINGERPRINTS.items():
            header_val = headers_lower.get(header_name, "")
            if any(p in header_val for p in patterns):
                return True

        # Check for Salesforce-specific headers
        for sf_header in SALESFORCE_RESPONSE_HEADERS:
            if sf_header in headers_lower:
                return True

        # Check CSP header for Salesforce domains
        csp = headers_lower.get("content-security-policy", "")
        if any(p in csp for p in SALESFORCE_CONTENT_PATTERNS):
            return True

        # If domain resolves via Salesforce CNAME, that's already strong evidence
        # (CNAME check is done in DNSResolver)
        return False
