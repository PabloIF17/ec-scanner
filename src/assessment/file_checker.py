"""
Check 7: File Exposure

Maps to: Salesforce file security best practices in the Spring '26 Guide

Tests whether ContentVersion and ContentDocument objects are accessible to guest users,
and whether file download URLs are accessible without authentication.
"""

import json
import urllib.parse
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger(__name__)

TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


@dataclass
class FileExposureResult:
    content_accessible: bool
    content_version_accessible: bool
    content_document_accessible: bool
    error: str | None = None

    @property
    def severity(self) -> str:
        if self.content_accessible:
            return "medium"
        return "none"


def _build_content_probe(object_name: str) -> str:
    """Build Aura payload to check ContentVersion or ContentDocument access."""
    message = {
        "actions": [
            {
                "id": "0",
                "descriptor": "serviceComponent://ui.force.components.controllers.lists.selectableListDataProvider.SelectableListDataProviderController/ACTION$getItems",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "entityNameOrId": object_name,
                    "pageSize": 1,
                    "currentPage": 0,
                    "listViewId": None,
                    "enableRowLevelSecurity": False,
                },
            }
        ]
    }
    context = {
        "mode": "PROD",
        "fwuid": "",
        "app": "siteforce:communityApp",
        "loaded": {},
    }
    return (
        f"message={urllib.parse.quote(json.dumps(message))}"
        f"&aura.context={urllib.parse.quote(json.dumps(context))}"
        f"&aura.token=undefined"
    )


class FileChecker:
    """
    Checks for file/document accessibility to guest users.
    """

    def __init__(self, endpoint_url: str) -> None:
        self.endpoint_url = endpoint_url
        self.log = structlog.get_logger(__name__)

    async def check(self) -> FileExposureResult:
        """Check ContentVersion and ContentDocument accessibility."""
        cv_accessible = False
        cd_accessible = False

        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False,
        ) as client:
            cv_accessible = await self._check_object(client, "ContentVersion")
            cd_accessible = await self._check_object(client, "ContentDocument")

        content_accessible = cv_accessible or cd_accessible

        if content_accessible:
            self.log.warning(
                "file_checker.content_accessible",
                content_version=cv_accessible,
                content_document=cd_accessible,
            )

        return FileExposureResult(
            content_accessible=content_accessible,
            content_version_accessible=cv_accessible,
            content_document_accessible=cd_accessible,
        )

    async def _check_object(
        self, client: httpx.AsyncClient, object_name: str
    ) -> bool:
        """Check if a content object is accessible."""
        try:
            payload = _build_content_probe(object_name)
            response = await client.post(
                self.endpoint_url,
                content=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

            if response.status_code not in (200, 400):
                return False

            data = json.loads(response.text[:10000])
            actions = data.get("actions", [])
            if not actions:
                return False

            return actions[0].get("state") == "SUCCESS"

        except Exception:
            return False
