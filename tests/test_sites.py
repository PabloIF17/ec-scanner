import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_site(client: AsyncClient):
    response = await client.post("/api/v1/sites", json={
        "domain": "portal.example.com",
        "cname_target": "example.live.siteforce.com",
        "discovery_source": "manual",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["domain"] == "portal.example.com"
    assert data["assessment_status"] == "pending"
    return data["id"]


@pytest.mark.asyncio
async def test_list_sites(client: AsyncClient):
    # Create a site first
    await client.post("/api/v1/sites", json={"domain": "test.example.com"})

    response = await client.get("/api/v1/sites")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_get_site_not_found(client: AsyncClient):
    response = await client.get("/api/v1/sites/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_site_rejected(client: AsyncClient):
    domain = "duplicate.example.com"
    await client.post("/api/v1/sites", json={"domain": domain})
    response = await client.post("/api/v1/sites", json={"domain": domain})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_exclude_site(client: AsyncClient):
    create_response = await client.post("/api/v1/sites", json={"domain": "exclude-me.example.com"})
    site_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/sites/{site_id}/exclude")
    assert response.status_code == 200
    assert response.json()["is_excluded"] is True
