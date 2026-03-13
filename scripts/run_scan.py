"""
CLI for manual scan runs.

Usage:
  python scripts/run_scan.py discovery
  python scripts/run_scan.py assessment <site_id>
  python scripts/run_scan.py assessment --all-pending
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def run_discovery():
    from src.core.config import get_settings
    from src.core.database import AsyncSessionLocal
    from src.discovery.pipeline import DiscoveryPipeline

    print("Starting discovery scan...")
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        pipeline = DiscoveryPipeline(settings)
        summary = await pipeline.run(db)

    print(f"""
Discovery complete:
  Raw discovered:      {summary.raw_discovered}
  After dedup:         {summary.after_dedup}
  DNS resolved:        {summary.dns_resolved}
  Salesforce CNAME:    {summary.salesforce_confirmed}
  HTTP confirmed:      {summary.http_confirmed}
  New sites saved:     {summary.new_sites_saved}
  Updated sites:       {summary.updated_sites}
  Errors:              {summary.errors}
""")


async def run_assessment(site_id: str):
    from src.core.database import AsyncSessionLocal
    from src.core.models import Site
    from src.assessment.pipeline import AssessmentPipeline
    from sqlalchemy import select

    print(f"Running assessment for site {site_id}...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Site).where(Site.id == uuid.UUID(site_id)))
        site = result.scalar_one_or_none()
        if not site:
            print(f"Error: Site {site_id} not found")
            return

        pipeline = AssessmentPipeline()
        assessment = await pipeline.run(site, db)

    print(f"""
Assessment complete for {site.domain}:
  Risk score: {assessment.risk_score}/100
  Severity:   {assessment.severity}
  Duration:   {assessment.scan_duration_seconds}s

Remediation steps:
""")
    for step in (assessment.remediation_summary or []):
        print(f"  • {step}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "discovery":
        asyncio.run(run_discovery())
    elif command == "assessment":
        if len(sys.argv) < 3:
            print("Error: provide a site_id")
            sys.exit(1)
        asyncio.run(run_assessment(sys.argv[2]))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
