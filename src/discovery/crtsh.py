import httpx
import structlog

from src.discovery.base import BaseDiscoverySource, DiscoveryResult, is_salesforce_cname

logger = structlog.get_logger(__name__)

# Salesforce infrastructure domains to query CT logs for
SALESFORCE_INFRASTRUCTURE_DOMAINS = [
    "siteforce.com",
    "salesforce-experience.com",
    "cloudforce.com",
    "salesforce-sites.com",
]


class CrtShSource(BaseDiscoverySource):
    """
    Certificate Transparency log source via crt.sh.
    Free, no API key required. Queries TLS certificates issued for
    Salesforce infrastructure domains and extracts custom domain SANs.
    """

    source_name = "crtsh"
    BASE_URL = "https://crt.sh"

    async def discover(self, target_cname_patterns: list[str]) -> list[DiscoveryResult]:
        results: list[DiscoveryResult] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for base_domain in SALESFORCE_INFRASTRUCTURE_DOMAINS:
                try:
                    domains = await self._query_crtsh(client, base_domain)
                    for domain in domains:
                        if domain not in seen:
                            seen.add(domain)
                            results.append(
                                DiscoveryResult(
                                    domain=domain,
                                    cname_target=None,
                                    source=self.source_name,
                                    metadata={"ct_base_query": base_domain},
                                )
                            )
                except Exception as e:
                    self.log.warning(
                        "crtsh.query_failed",
                        base_domain=base_domain,
                        error=str(e),
                    )

        self.log.info("crtsh.discovery_complete", total=len(results))
        return results

    async def _query_crtsh(self, client: httpx.AsyncClient, base_domain: str) -> list[str]:
        """Query crt.sh for certificates issued under a base domain."""
        response = await self._get(
            client,
            self.BASE_URL,
            params={"q": f"%.{base_domain}", "output": "json"},
        )

        certs = response.json()
        domains: set[str] = set()

        for cert in certs:
            for name_field in ("name_value", "common_name"):
                value = cert.get(name_field, "")
                # name_value can contain multiple names separated by newlines
                for name in value.split("\n"):
                    name = name.strip().lower().lstrip("*.")
                    if name and not name.endswith(base_domain):
                        # This is a custom domain (not the SF infrastructure domain itself)
                        domains.add(name)

        return list(domains)
