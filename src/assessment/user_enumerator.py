"""
Check 4: User Enumeration

Maps to: Salesforce Advisory Recommendation #4 — "Restrict Visibility"

Tests whether guest users can enumerate internal org members via the User object.
Harvested user data enables social engineering and vishing attacks.
"""

import json
import urllib.parse
from dataclasses import dataclass, field

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Fields on User object that, if returned, indicate internal user enumeration is possible
SENSITIVE_USER_FIELDS = [
    "Name", "Email", "UserRole", "Profile", "Title", "Department",
    "Phone", "MobilePhone", "Username", "IsActive", "ManagerId",
]

TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


@dataclass
class UserEnumerationResult:
    vulnerable: bool
    users_visible: bool
    fields_exposed: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def severity(self) -> str:
        return "critical" if self.vulnerable else "none"


def _build_user_query_payload() -> str:
    """Build Aura payload to query internal User records."""
    message = {
        "actions": [
            {
                "id": "0",
                "descriptor": "aura://RecordUiController/ACTION$getObjectInfo",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "objectApiName": "User",
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


class UserEnumerator:
    """
    Tests whether the User object is accessible to guest users.
    Only records field names, never actual user data.
    """

    def __init__(self, endpoint_url: str) -> None:
        self.endpoint_url = endpoint_url
        self.log = structlog.get_logger(__name__)

    async def check(self) -> UserEnumerationResult:
        """Check if guest users can access User object records."""
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT,
                follow_redirects=True,
                verify=False,
            ) as client:
                payload = _build_user_query_payload()
                response = await client.post(
                    self.endpoint_url,
                    content=payload,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )

                return self._parse_response(response.text)

        except Exception as e:
            return UserEnumerationResult(
                vulnerable=False,
                users_visible=False,
                error=str(e),
            )

    def _parse_response(self, body: str) -> UserEnumerationResult:
        """Parse response to determine if user data is accessible."""
        try:
            data = json.loads(body[:20000])
        except (json.JSONDecodeError, ValueError):
            return UserEnumerationResult(vulnerable=False, users_visible=False)

        actions = data.get("actions", [])
        if not actions:
            return UserEnumerationResult(vulnerable=False, users_visible=False)

        action = actions[0]
        state = action.get("state", "")

        if state != "SUCCESS":
            return UserEnumerationResult(vulnerable=False, users_visible=False)

        # Extract only field NAMES from the response, never values
        return_value = action.get("returnValue", {}) or {}
        fields = return_value.get("fields", {}) if isinstance(return_value, dict) else {}

        exposed_fields = []
        for field_name in SENSITIVE_USER_FIELDS:
            if field_name in fields:
                exposed_fields.append(field_name)

        is_vulnerable = len(exposed_fields) > 0

        if is_vulnerable:
            self.log.warning(
                "user_enum.vulnerable",
                fields_exposed=exposed_fields,
            )

        return UserEnumerationResult(
            vulnerable=is_vulnerable,
            users_visible=is_vulnerable,
            fields_exposed=exposed_fields,
        )
