"""
Check 2: Object Access Enumeration

Maps to: Salesforce Advisory Recommendation #1 — "Audit Guest User Configurations"

Tests which Salesforce objects are accessible to the guest user via the Aura API.
Requires Check 1 (Aura endpoint) to be open.

IMPORTANT: Does NOT store actual record data. Only records object names,
approximate record counts, and field names as metadata.
"""

import json
import urllib.parse
from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Objects to probe, ordered by priority (Critical → High → Medium → Low)
PROBE_OBJECTS = [
    # Critical
    {"api_name": "User", "priority": "critical"},
    {"api_name": "Contact", "priority": "critical"},
    {"api_name": "Account", "priority": "critical"},
    # High
    {"api_name": "Lead", "priority": "high"},
    {"api_name": "Opportunity", "priority": "high"},
    {"api_name": "Case", "priority": "high"},
    # Medium
    {"api_name": "ContentVersion", "priority": "medium"},
    {"api_name": "ContentDocument", "priority": "medium"},
    {"api_name": "EmailMessage", "priority": "medium"},
    # Low
    {"api_name": "Task", "priority": "low"},
    {"api_name": "Event", "priority": "low"},
]

TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


@dataclass
class ObjectAccessResult:
    object_api_name: str
    priority: str
    accessible: bool
    record_count_approx: int | None
    fields_returned: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def severity(self) -> str:
        if not self.accessible:
            return "none"
        return self.priority


@dataclass
class ObjectEnumerationResult:
    objects: list[ObjectAccessResult]

    @property
    def accessible_objects(self) -> list[ObjectAccessResult]:
        return [o for o in self.objects if o.accessible]

    @property
    def critical_objects(self) -> list[ObjectAccessResult]:
        return [o for o in self.accessible_objects if o.priority == "critical"]


def _build_list_action(object_api_name: str) -> str:
    """Build an Aura action payload to list records of an object."""
    message = {
        "actions": [
            {
                "id": "0",
                "descriptor": "serviceComponent://ui.force.components.controllers.lists.selectableListDataProvider.SelectableListDataProviderController/ACTION$getItems",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "entityNameOrId": object_api_name,
                    "pageSize": 3,
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


class ObjectEnumerator:
    """
    Enumerates accessible Salesforce objects via the Aura API.
    Only invoked when Check 1 confirms the Aura endpoint is open.
    """

    def __init__(self, endpoint_url: str, fwuid: str | None = None) -> None:
        self.endpoint_url = endpoint_url
        self.fwuid = fwuid
        self.log = structlog.get_logger(__name__)

    async def enumerate(self) -> ObjectEnumerationResult:
        """Probe all target objects and return accessibility results."""
        results: list[ObjectAccessResult] = []

        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False,
        ) as client:
            for obj_def in PROBE_OBJECTS:
                result = await self._probe_object(client, obj_def["api_name"], obj_def["priority"])
                results.append(result)

                if result.accessible:
                    self.log.warning(
                        "object_enum.accessible",
                        object=obj_def["api_name"],
                        priority=obj_def["priority"],
                        record_count=result.record_count_approx,
                    )

        accessible = sum(1 for r in results if r.accessible)
        self.log.info("object_enum.complete", probed=len(results), accessible=accessible)
        return ObjectEnumerationResult(objects=results)

    async def _probe_object(
        self, client: httpx.AsyncClient, api_name: str, priority: str
    ) -> ObjectAccessResult:
        """Probe a single Salesforce object for guest user access."""
        try:
            payload = _build_list_action(api_name)
            response = await client.post(
                self.endpoint_url,
                content=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

            if response.status_code not in (200, 400):
                return ObjectAccessResult(
                    object_api_name=api_name,
                    priority=priority,
                    accessible=False,
                    record_count_approx=None,
                )

            data = self._parse_aura_response(response.text)
            if data is None:
                return ObjectAccessResult(
                    object_api_name=api_name,
                    priority=priority,
                    accessible=False,
                    record_count_approx=None,
                )

            accessible, count, fields = self._extract_access_info(data)
            return ObjectAccessResult(
                object_api_name=api_name,
                priority=priority,
                accessible=accessible,
                record_count_approx=count,
                fields_returned=fields,
            )

        except Exception as e:
            return ObjectAccessResult(
                object_api_name=api_name,
                priority=priority,
                accessible=False,
                record_count_approx=None,
                error=str(e),
            )

    def _parse_aura_response(self, body: str) -> dict | None:
        """Parse an Aura JSON response body."""
        try:
            data = json.loads(body[:50000])
            return data
        except (json.JSONDecodeError, ValueError):
            return None

    def _extract_access_info(
        self, data: dict
    ) -> tuple[bool, int | None, list[str]]:
        """
        Extract accessibility, approximate record count, and field names from Aura response.
        Does NOT extract actual field values — only metadata.
        """
        actions = data.get("actions", [])
        if not actions:
            return False, None, []

        action = actions[0] if actions else {}
        state = action.get("state", "")

        if state == "ERROR":
            # ERROR state means the object query was attempted but returned an error
            # This might mean no access, or it might be a different error
            errors = action.get("error", [])
            error_msgs = [str(e.get("message", "")) for e in errors]
            # "Entity_ACCESS" error = no access. Other errors = object might be accessible
            no_access_indicators = ["Entity_ACCESS", "INSUFFICIENT_ACCESS", "sObject type"]
            if any(ind in " ".join(error_msgs) for ind in no_access_indicators):
                return False, None, []
            # Other errors — object might exist but query failed for other reasons
            return False, None, []

        if state == "SUCCESS":
            return_value = action.get("returnValue", {}) or {}
            records = return_value.get("records", []) if isinstance(return_value, dict) else []
            count = return_value.get("total", None) if isinstance(return_value, dict) else None

            # Extract only FIELD NAMES, never field values
            field_names: list[str] = []
            if records and isinstance(records, list) and len(records) > 0:
                first_record = records[0]
                if isinstance(first_record, dict):
                    field_names = list(first_record.keys())

            return True, count, field_names

        return False, None, []
