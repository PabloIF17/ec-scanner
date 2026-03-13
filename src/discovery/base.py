from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger(__name__)

# CNAME target patterns that indicate a Salesforce Experience Cloud site
SALESFORCE_CNAME_PATTERNS = [
    ".live.siteforce.com",
    ".cdn.salesforce-experience.com",
    ".cloudforce.com",
    ".force.com",
    ".salesforce-sites.com",
    ".my.salesforce.com",
    ".salesforce.com",
]

# Domains to EXCLUDE as public-facing URLs (only valid as CNAME targets)
EXCLUDED_PUBLIC_PATTERNS = [
    ".my.site.com",
    ".force.com",
]


@dataclass
class DiscoveryResult:
    domain: str
    cname_target: str | None
    source: str
    ip_addresses: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def is_salesforce_cname(cname: str) -> bool:
    """Check if a CNAME target points to Salesforce infrastructure."""
    cname_lower = cname.lower().rstrip(".")
    return any(cname_lower.endswith(pattern) for pattern in SALESFORCE_CNAME_PATTERNS)


def is_excluded_public_domain(domain: str) -> bool:
    """Check if a domain should be excluded as a public-facing URL."""
    domain_lower = domain.lower()
    return any(domain_lower.endswith(pattern) for pattern in EXCLUDED_PUBLIC_PATTERNS)


class BaseDiscoverySource(ABC):
    """Abstract base class for all discovery data sources."""

    source_name: str = "unknown"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.log = structlog.get_logger(__name__).bind(source=self.source_name)

    @abstractmethod
    async def discover(self, target_cname_patterns: list[str]) -> list[DiscoveryResult]:
        """Discover domains pointing to any of the given CNAME patterns."""
        ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _get(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Shared GET with automatic retry on transient failures."""
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _post(
        self,
        client: httpx.AsyncClient,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Shared POST with automatic retry on transient failures."""
        response = await client.post(url, json=json, headers=headers)
        response.raise_for_status()
        return response
