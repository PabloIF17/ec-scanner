import httpx
import structlog

from src.discovery.base import BaseDiscoverySource, DiscoveryResult

logger = structlog.get_logger(__name__)

CNAME_SEARCH_PATTERNS = [
    "live.siteforce.com",
    "cdn.salesforce-experience.com",
    "cloudforce.com",
    "salesforce-sites.com",
]


class SecurityTrailsSource(BaseDiscoverySource):
    """
    SecurityTrails API — primary discovery source.
    Queries passive DNS for domains with CNAMEs pointing to Salesforce infrastructure.
    Requires a paid API key (SECURITYTRAILS_API_KEY).
    """

    source_name = "securitytrails"
    BASE_URL = "https://api.securitytrails.com/v1"

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key=api_key)
        self._headers = {
            "APIKEY": api_key,
            "Accept": "application/json",
        }

    async def discover(self, target_cname_patterns: list[str]) -> list[DiscoveryResult]:
        if not self.api_key:
            self.log.warning("securitytrails.no_api_key")
            return []

        results: list[DiscoveryResult] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for cname_pattern in CNAME_SEARCH_PATTERNS:
                try:
                    domains = await self._search_by_cname(client, cname_pattern)
                    for domain, cname_target in domains:
                        if domain not in seen:
                            seen.add(domain)
                            results.append(
                                DiscoveryResult(
                                    domain=domain,
                                    cname_target=cname_target,
                                    source=self.source_name,
                                )
                            )
                except Exception as e:
                    self.log.warning(
                        "securitytrails.query_failed",
                        cname_pattern=cname_pattern,
                        error=str(e),
                    )

        self.log.info("securitytrails.discovery_complete", total=len(results))
        return results

    async def _search_by_cname(
        self, client: httpx.AsyncClient, cname_value: str
    ) -> list[tuple[str, str]]:
        """Search for all domains with a CNAME containing the given value."""
        domains: list[tuple[str, str]] = []
        page = 1

        while True:
            response = await self._post(
                client,
                f"{self.BASE_URL}/domains/list",
                json={
                    "filter": {
                        "cname": cname_value,
                    }
                },
                headers={**self._headers, "Content-Type": "application/json"},
            )
            data = response.json()
            records = data.get("records", [])

            for record in records:
                hostname = record.get("hostname", "")
                # SecurityTrails returns the domain in 'hostname' field
                domains.append((hostname, cname_value))

            # Pagination
            if not data.get("meta", {}).get("next_page"):
                break
            page += 1

            # Safety limit
            if page > 50:
                self.log.warning("securitytrails.pagination_limit_reached", cname=cname_value)
                break

        return domains
