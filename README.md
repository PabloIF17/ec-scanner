# EC-Scanner — Experience Cloud Security Scanner

Internal tool for Inforge to discover and assess Salesforce Experience Cloud sites for guest user security misconfigurations, per the March 2026 Salesforce Security Advisory.

## Quick Start

```bash
# 1. Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys

# 2. Start all services
docker compose up -d

# 3. Run database migrations
docker compose exec api alembic upgrade head

# 4. Seed with sample data (optional)
docker compose exec api python scripts/seed_db.py
```

**Dashboard:** http://localhost:3000
**API docs:** http://localhost:8000/docs

## Architecture

```
[Discovery] → [Assessment] → [Sales Enablement]
 DNS Enum      Aura Probing    Enrichment + Outreach
     ↓               ↓                 ↓
Confirmed EC    Risk Reports    Qualified Pipeline
   Sites
```

Three-phase pipeline communicating via PostgreSQL. Each phase runs independently via Celery tasks.

## Services

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI backend |
| Dashboard | 3000 | React frontend |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Celery broker |
| Celery Worker | — | Background tasks |
| Celery Beat | — | Scheduled scans |

## Manual Scans (CLI)

```bash
# Discovery scan
docker compose exec api python scripts/run_scan.py discovery

# Assessment for a specific site
docker compose exec api python scripts/run_scan.py assessment <site-uuid>
```

## API Keys Required

| Key | Required | Purpose |
|-----|----------|---------|
| `SECURITYTRAILS_API_KEY` | Recommended | Primary discovery source |
| `VIRUSTOTAL_API_KEY` | Optional | Supplementary discovery |
| `CLEARBIT_API_KEY` | Optional | Prospect enrichment |
| `ZOOMINFO_API_KEY` | Optional | Prospect enrichment |
| `APOLLO_API_KEY` | Optional | Prospect enrichment |

Without API keys, only crt.sh (free) and Rapid7 Sonar dataset (pre-downloaded) are used for discovery.

## Assessment Checks

| Check | Maps To | Severity |
|-------|---------|----------|
| Aura Endpoint | Advisory Rec #3 | CRITICAL |
| Object Access | Advisory Rec #1 | CRITICAL-HIGH |
| Sensitive Fields | Spring '26 Guide FLS | HIGH |
| User Enumeration | Advisory Rec #4 | CRITICAL |
| Self-Registration | Advisory Rec #5 | MEDIUM |
| Apex Exposure | Spring '26 Code Guide | LOW |
| File Exposure | Spring '26 File Guide | LOW |

## Legal Notice

Per section 8.3 of the project requirements: all activity is limited to DNS lookups against public passive DNS datasets, HTTP requests to publicly accessible endpoints, and unauthenticated API calls to publicly exposed Aura endpoints.

**Legal review is required before production deployment.** See EXPERIENCE_CLOUD_SCANNER_REQUIREMENTS.md §8.3.

## Development

```bash
# Run tests (requires test database)
pytest

# Run specific test file
pytest tests/assessment/test_risk_scorer.py -v

# Local API development (without Docker)
pip install -r requirements.txt
uvicorn src.api.main:app --reload

# Local dashboard development
cd dashboard && npm install && npm run dev
```
