import httpx
import structlog

from src.discovery.base import BaseDiscoverySource, DiscoveryResult, is_salesforce_cname

logger = structlog.get_logger(__name__)

# Known Salesforce infrastructure domains to pivot on
SALESFORCE_PIVOT_DOMAINS = [
    "siteforce.com",
    "salesforce-experience.com",
    "cloudforce.com",
    "salesforce-sites.com",
]


class VirusTotalSource(BaseDiscoverySource):
    """
    VirusTotal passive DNS — supplementary discovery source.
    Pivots on known Salesforce infrastructure domains to find custom domains.
    Requires VIRUSTOTAL_API_KEY.
    """

    source_name = "virustotal"
    BASE_URL = "https://www.virustotal.com/api/v3"

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key=api_key)
        self._headers = {
            "x-apikey": api_key,
            "Accept": "application/json",
        }

    async def discover(self, target_cname_patterns: list[str]) -> list[DiscoveryResult]:
        if not self.api_key:
            self.log.warning("virustotal.no_api_key")
            return []

        results: list[DiscoveryResult] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for pivot_domain in SALESFORCE_PIVOT_DOMAINS:
                try:
                    subdomains = await self._get_referring_domains(client, pivot_domain)
                    for domain, cname_target in subdomains:
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
                        "virustotal.query_failed",
                        pivot_domain=pivot_domain,
                        error=str(e),
                    )

        self.log.info("virustotal.discovery_complete", total=len(results))
        return results

    async def _get_referring_domains(
        self, client: httpx.AsyncClient, domain: str
    ) -> list[tuple[str, str]]:
        """
        Get domains that have CNAME records pointing to the given domain.
        Uses VirusTotal's domain relationships endpoint.
        """
        referring: list[tuple[str, str]] = []
        cursor: str | None = None

        while True:
            params: dict = {"limit": 40, "relationship": "cname_records"}
            if cursor:
                params["cursor"] = cursor

            try:
                response = await self._get(
                    client,
                    f"{self.BASE_URL}/domains/{domain}/referrer_files",
                    headers=self._headers,
                    params=params,
                )
                data = response.json()
                items = data.get("data", [])

                for item in items:
                    attrs = item.get("attributes", {})
                    domain_name = attrs.get("id", "")
                    if domain_name:
                        referring.append((domain_name, domain))

                cursor = data.get("meta", {}).get("cursor")
                if not cursor or not items:
                    break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break
                raise

        return referring
