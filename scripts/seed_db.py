"""
Seed script — populates the database with sample data for development/testing.
Run with: python scripts/seed_db.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import AsyncSessionLocal
from src.core.models import Assessment, Site


SAMPLE_SITES = [
    {
        "domain": "community.acme-corp.com",
        "cname_target": "acme-corp.live.siteforce.com",
        "discovery_source": "securitytrails",
    },
    {
        "domain": "portal.globex-inc.com",
        "cname_target": "globex.live.siteforce.com",
        "discovery_source": "crtsh",
    },
    {
        "domain": "support.initech.io",
        "cname_target": "initech.cdn.salesforce-experience.com",
        "discovery_source": "rapid7",
    },
]

SAMPLE_ASSESSMENTS = [
    {
        "domain": "community.acme-corp.com",
        "risk_score": 87,
        "severity": "HIGH",
        "checks": {
            "aura_endpoint": {"is_open": True, "response_type": "aura_framework", "severity": "critical"},
            "object_access": [
                {"object": "Contact", "accessible": True, "priority": "critical", "record_count_approx": 1500, "sensitive_fields": [{"field": "Email", "category": "email", "severity": "critical"}]},
                {"object": "Account", "accessible": True, "priority": "critical", "record_count_approx": 300, "sensitive_fields": []},
                {"object": "User", "accessible": False, "priority": "critical", "sensitive_fields": []},
            ],
            "user_enumeration": {"vulnerable": False, "users_visible": False, "fields_exposed": [], "severity": "none"},
            "self_registration": {"enabled": True, "endpoint_url": "https://community.acme-corp.com/s/login/SelfRegister", "severity": "medium"},
            "apex_exposure": {"custom_actions_found": 2, "potentially_unsafe": 1, "severity": "low"},
            "file_exposure": {"content_accessible": False, "severity": "none"},
        },
        "remediation_summary": [
            "CRITICAL: Disable 'Allow guest users to access public APIs' in guest user profile.",
            "CRITICAL: Remove Read access to Contact, Account objects from guest user profile.",
            "MEDIUM: Disable self-registration or implement email verification.",
        ],
    },
    {
        "domain": "portal.globex-inc.com",
        "risk_score": 15,
        "severity": "MINIMAL",
        "checks": {
            "aura_endpoint": {"is_open": False, "response_type": "blocked", "severity": "none"},
            "object_access": [],
            "user_enumeration": {"vulnerable": False, "severity": "none"},
            "self_registration": {"enabled": False, "severity": "none"},
            "apex_exposure": {"custom_actions_found": 0, "potentially_unsafe": 0, "severity": "none"},
            "file_exposure": {"content_accessible": False, "severity": "none"},
        },
        "remediation_summary": [],
    },
]


async def seed():
    print("Seeding database with sample data...")

    async with AsyncSessionLocal() as db:
        # Create sites
        site_map: dict[str, uuid.UUID] = {}

        for site_data in SAMPLE_SITES:
            from sqlalchemy import select
            existing = await db.execute(select(Site).where(Site.domain == site_data["domain"]))
            if existing.scalar_one_or_none():
                print(f"  Site already exists: {site_data['domain']}")
                continue

            site = Site(
                id=uuid.uuid4(),
                domain=site_data["domain"],
                cname_target=site_data["cname_target"],
                discovery_source=site_data["discovery_source"],
                discovery_date=datetime.now(timezone.utc),
                http_status=200,
                is_active=True,
                assessment_status="pending",
            )
            db.add(site)
            await db.flush()
            site_map[site_data["domain"]] = site.id
            print(f"  Created site: {site_data['domain']}")

        # Create assessments
        for assessment_data in SAMPLE_ASSESSMENTS:
            domain = assessment_data["domain"]
            if domain not in site_map:
                continue

            site_id = site_map[domain]
            assessment = Assessment(
                id=uuid.uuid4(),
                site_id=site_id,
                assessment_date=datetime.now(timezone.utc),
                risk_score=assessment_data["risk_score"],
                severity=assessment_data["severity"],
                checks=assessment_data["checks"],
                remediation_summary=assessment_data["remediation_summary"],
                scan_duration_seconds=12,
            )
            db.add(assessment)
            print(f"  Created assessment for {domain}: score={assessment_data['risk_score']} ({assessment_data['severity']})")

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
