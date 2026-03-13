import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.models import Site
from src.discovery.base import DiscoveryResult, is_excluded_public_domain, SALESFORCE_CNAME_PATTERNS
from src.discovery.crtsh import CrtShSource
from src.discovery.dns_resolver import DNSResolution, DNSResolver
from src.discovery.http_validator import HTTPValidation, HTTPValidator
from src.discovery.rapid7_sonar import Rapid7SonarSource
from src.discovery.securitytrails import SecurityTrailsSource
from src.discovery.virustotal import VirusTotalSource

logger = structlog.get_logger(__name__)


@dataclass
class DiscoverySummary:
    raw_discovered: int
    after_dedup: int
    dns_resolved: int
    salesforce_confirmed: int
    http_confirmed: int
    new_sites_saved: int
    updated_sites: int
    errors: int


class DiscoveryPipeline:
    """
    Orchestrates the full discovery pipeline:
    1. Fan out to all data sources concurrently
    2. Deduplicate and normalize results
    3. DNS resolution + CNAME verification
    4. HTTP validation + Salesforce fingerprinting
    5. Persist confirmed sites to database
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.log = structlog.get_logger(__name__)
        self._build_sources()

    def _build_sources(self) -> None:
        self.sources = []

        # Always include free sources
        self.sources.append(CrtShSource())
        self.sources.append(Rapid7SonarSource(data_dir=self.settings.rapid7_data_dir))

        # Add API-key sources if configured
        if self.settings.securitytrails_api_key:
            self.sources.append(SecurityTrailsSource(self.settings.securitytrails_api_key))

        if self.settings.virustotal_api_key:
            self.sources.append(VirusTotalSource(self.settings.virustotal_api_key))

        self.log.info("discovery.sources_loaded", count=len(self.sources))

    async def run(self, db: AsyncSession) -> DiscoverySummary:
        """Run the full discovery pipeline."""
        start = datetime.now(timezone.utc)
        self.log.info("discovery.pipeline_started", sources=len(self.sources))

        # Step 1: Fan out to all sources concurrently
        raw_results = await self._collect_from_sources()
        self.log.info("discovery.raw_collected", total=len(raw_results))

        # Step 2: Deduplicate and filter
        unique_results = self._deduplicate(raw_results)
        self.log.info("discovery.after_dedup", total=len(unique_results))

        # Step 3: DNS resolution
        domains = [r.domain for r in unique_results]
        dns_resolver = DNSResolver()
        resolutions = await dns_resolver.resolve_all(domains)

        dns_alive = [r for r in resolutions if r.is_alive]
        dns_sf = [r for r in resolutions if r.is_salesforce]
        self.log.info(
            "discovery.dns_resolved",
            alive=len(dns_alive),
            salesforce_cname=len(dns_sf),
        )

        # Step 4: HTTP validation
        http_validator = HTTPValidator(
            rate_limit_ms=self.settings.scan_rate_limit_ms,
            concurrency=self.settings.scan_concurrency,
        )
        validations = await http_validator.validate_all(resolutions)
        http_confirmed = [v for v in validations if v.is_live]

        # Step 5: Merge cname data from DNS resolution into validation results
        cname_map = {r.domain: r.cname_target for r in resolutions}
        source_map = {r.domain: r.source for r in unique_results}

        # Step 6: Persist to database
        new_count, updated_count = await self._persist_sites(
            db=db,
            validations=http_confirmed,
            cname_map=cname_map,
            source_map=source_map,
        )

        errors = sum(1 for r in resolutions if r.error is not None)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        self.log.info(
            "discovery.pipeline_complete",
            elapsed_seconds=elapsed,
            new_sites=new_count,
            updated=updated_count,
        )

        return DiscoverySummary(
            raw_discovered=len(raw_results),
            after_dedup=len(unique_results),
            dns_resolved=len(dns_alive),
            salesforce_confirmed=len(dns_sf),
            http_confirmed=len(http_confirmed),
            new_sites_saved=new_count,
            updated_sites=updated_count,
            errors=errors,
        )

    async def _collect_from_sources(self) -> list[DiscoveryResult]:
        """Query all discovery sources concurrently."""
        tasks = [
            source.discover(SALESFORCE_CNAME_PATTERNS)
            for source in self.sources
        ]
        results_per_source = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[DiscoveryResult] = []
        for source, result in zip(self.sources, results_per_source):
            if isinstance(result, Exception):
                self.log.error(
                    "discovery.source_failed",
                    source=source.source_name,
                    error=str(result),
                )
            else:
                all_results.extend(result)

        return all_results

    def _deduplicate(self, results: list[DiscoveryResult]) -> list[DiscoveryResult]:
        """
        Deduplicate and normalize discovered domains.
        - Strip www. prefix
        - Lowercase
        - Exclude public-facing my.site.com and force.com domains
        """
        seen: set[str] = set()
        unique: list[DiscoveryResult] = []

        for result in results:
            # Normalize domain
            domain = result.domain.lower().strip()
            domain = domain.lstrip("www.") if domain.startswith("www.") else domain

            # Exclude non-production domains as public-facing URLs
            if is_excluded_public_domain(domain):
                continue

            if domain not in seen:
                seen.add(domain)
                result.domain = domain
                unique.append(result)

        return unique

    async def _persist_sites(
        self,
        db: AsyncSession,
        validations: list[HTTPValidation],
        cname_map: dict[str, str | None],
        source_map: dict[str, str],
    ) -> tuple[int, int]:
        """Upsert validated sites to the database."""
        new_count = 0
        updated_count = 0
        now = datetime.now(timezone.utc)

        for validation in validations:
            domain = validation.domain
            cname_target = cname_map.get(domain)
            source = source_map.get(domain, "unknown")

            # Check if site already exists
            stmt = select(Site).where(Site.domain == domain)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing site
                existing.is_active = validation.is_live
                existing.http_status = validation.http_status
                existing.http_redirect_target = validation.redirect_target
                existing.last_validated = now
                if cname_target:
                    existing.cname_target = cname_target
                existing.metadata_ = {
                    "server_header": validation.server_header,
                    "response_time_ms": validation.response_time_ms,
                    "is_salesforce_confirmed": validation.is_salesforce_confirmed,
                }
                updated_count += 1
            else:
                # Create new site
                site = Site(
                    id=uuid.uuid4(),
                    domain=domain,
                    cname_target=cname_target,
                    discovery_source=source,
                    discovery_date=now,
                    http_status=validation.http_status,
                    http_redirect_target=validation.redirect_target,
                    is_active=validation.is_live,
                    last_validated=now,
                    assessment_status="pending",
                    metadata_={
                        "server_header": validation.server_header,
                        "response_time_ms": validation.response_time_ms,
                        "is_salesforce_confirmed": validation.is_salesforce_confirmed,
                    },
                )
                db.add(site)
                new_count += 1

        await db.flush()
        return new_count, updated_count
