import asyncio
from dataclasses import dataclass, field

import dns.asyncresolver
import dns.exception
import structlog

from src.discovery.base import is_salesforce_cname

logger = structlog.get_logger(__name__)

PUBLIC_DNS_SERVERS = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]


@dataclass
class DNSResolution:
    domain: str
    is_alive: bool
    ip_addresses: list[str] = field(default_factory=list)
    cname_chain: list[str] = field(default_factory=list)
    cname_target: str | None = None
    is_salesforce: bool = False
    error: str | None = None


class DNSResolver:
    """
    Async DNS resolver that resolves CNAME chains for discovered domains.
    Confirms Salesforce infrastructure presence via CNAME fingerprinting.
    """

    def __init__(self, nameservers: list[str] | None = None, timeout: float = 5.0) -> None:
        self.nameservers = nameservers or PUBLIC_DNS_SERVERS
        self.timeout = timeout
        self.log = structlog.get_logger(__name__)

    async def resolve_all(
        self, domains: list[str], concurrency: int = 50
    ) -> list[DNSResolution]:
        """Resolve all domains concurrently, respecting concurrency limit."""
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_resolve(domain: str) -> DNSResolution:
            async with semaphore:
                return await self._resolve_one(domain)

        tasks = [bounded_resolve(domain) for domain in domains]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved = []
        for domain, result in zip(domains, results):
            if isinstance(result, Exception):
                resolved.append(
                    DNSResolution(domain=domain, is_alive=False, error=str(result))
                )
            else:
                resolved.append(result)

        alive_count = sum(1 for r in resolved if r.is_alive)
        sf_count = sum(1 for r in resolved if r.is_salesforce)
        self.log.info(
            "dns.resolution_complete",
            total=len(resolved),
            alive=alive_count,
            salesforce=sf_count,
        )
        return resolved

    async def _resolve_one(self, domain: str) -> DNSResolution:
        """Resolve a single domain, following CNAME chain."""
        resolver = dns.asyncresolver.Resolver()
        resolver.nameservers = self.nameservers
        resolver.timeout = self.timeout
        resolver.lifetime = self.timeout * 2

        cname_chain: list[str] = []
        final_cname: str | None = None
        ip_addresses: list[str] = []

        try:
            # Follow CNAME chain
            current = domain
            for _ in range(10):  # Max 10 hops
                try:
                    cname_answer = await resolver.resolve(current, "CNAME")
                    cname_target = str(cname_answer[0].target).rstrip(".")
                    cname_chain.append(cname_target)
                    final_cname = cname_target
                    current = cname_target
                except dns.resolver.NoAnswer:
                    break
                except dns.resolver.NXDOMAIN:
                    break

            # Resolve A records
            try:
                a_answer = await resolver.resolve(current, "A")
                ip_addresses = [str(r) for r in a_answer]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                pass

            is_alive = bool(ip_addresses)
            is_salesforce = final_cname is not None and is_salesforce_cname(final_cname)

            return DNSResolution(
                domain=domain,
                is_alive=is_alive,
                ip_addresses=ip_addresses,
                cname_chain=cname_chain,
                cname_target=final_cname,
                is_salesforce=is_salesforce,
            )

        except dns.exception.DNSException as e:
            return DNSResolution(domain=domain, is_alive=False, error=str(e))
        except Exception as e:
            return DNSResolution(domain=domain, is_alive=False, error=f"Unexpected: {e}")
