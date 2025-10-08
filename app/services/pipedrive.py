"""Pipedrive API client service with OAuth2 support and webhooks."""
import asyncio
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PipedriveToken
from app.settings import settings

logger = structlog.get_logger()


class PipedriveException(Exception):
    """Base exception for Pipedrive API errors."""

    pass


class PipedriveAuthenticationError(PipedriveException):
    """Pipedrive authentication error."""

    pass


class PipedriveRateLimitError(PipedriveException):
    """Pipedrive rate limit error."""

    pass


class PipedriveClient:
    """
    Pipedrive API client with OAuth2 support.

    Provides methods for interacting with Pipedrive API including:
    - OAuth2 flow
    - Organizations, Persons, Deals management
    - Notes creation
    - Webhook event parsing
    """

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self.semaphore = asyncio.Semaphore(5)  # Rate limiting
        self.base_url = settings.pipedrive_base_url

    async def _get_access_token(self) -> str:
        """Get a valid access token (from DB or API token)."""
        # If API token is configured (for dev), use it
        if settings.pipedrive_api_token:
            return settings.pipedrive_api_token

        # Otherwise, get OAuth token from database
        if not self.db:
            raise PipedriveAuthenticationError("Database session required for OAuth")

        result = await self.db.execute(
            select(PipedriveToken).where(PipedriveToken.is_active == True).order_by(PipedriveToken.created_at.desc())  # noqa
        )
        token = result.scalar_one_or_none()

        if not token:
            raise PipedriveAuthenticationError("No active Pipedrive token found")

        # Check if token is expired
        if token.expires_at and token.expires_at < datetime.now(timezone.utc):
            if token.refresh_token:
                token = await self._refresh_token(token)
            else:
                raise PipedriveAuthenticationError("Token expired and no refresh token available")

        return token.access_token

    async def _refresh_token(self, token: PipedriveToken) -> PipedriveToken:
        """Refresh an expired OAuth token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth.pipedrive.com/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token,
                    "client_id": settings.pipedrive_client_id,
                    "client_secret": settings.pipedrive_client_secret,
                },
            )

            if response.status_code != 200:
                raise PipedriveAuthenticationError(f"Token refresh failed: {response.text}")

            data = response.json()

            # Update token in database
            token.access_token = data["access_token"]
            token.refresh_token = data.get("refresh_token", token.refresh_token)
            token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))

            if self.db:
                await self.db.commit()

            logger.info("pipedrive_token_refreshed")
            return token

    async def _make_request(
        self, method: str, endpoint: str, data: dict[str, Any] | None = None, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated request to Pipedrive API."""
        async with self.semaphore:
            access_token = await self._get_access_token()

            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            url = f"{self.base_url}/{endpoint.lstrip('/')}"

            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        if method.upper() == "GET":
                            response = await client.get(url, headers=headers, params=params)
                        elif method.upper() == "POST":
                            response = await client.post(url, headers=headers, json=data)
                        elif method.upper() == "PUT":
                            response = await client.put(url, headers=headers, json=data)
                        elif method.upper() == "DELETE":
                            response = await client.delete(url, headers=headers)
                        else:
                            raise ValueError(f"Unsupported method: {method}")

                        if response.status_code == 429:
                            # Rate limited
                            retry_after = int(response.headers.get("Retry-After", 60))
                            logger.warning("pipedrive_rate_limited", retry_after=retry_after)
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status_code >= 400:
                            logger.error(
                                "pipedrive_request_failed",
                                status=response.status_code,
                                endpoint=endpoint,
                                response=response.text,
                            )
                            raise PipedriveException(f"Request failed: {response.status_code} - {response.text}")

                        return response.json()

                except httpx.TimeoutException:
                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise PipedriveException("Request timeout")
                except Exception as e:
                    if attempt < 2:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise PipedriveException(f"Request failed: {e}")

    # Organization methods
    async def upsert_organization(self, name: str, external_id: str | None = None, **kwargs) -> dict[str, Any]:
        """Create or update a Pipedrive organization."""
        # Check if organization exists
        if external_id:
            existing = await self.search_organizations(name)
            if existing and len(existing) > 0:
                # Update existing
                org_id = existing[0]["id"]
                return await self._make_request("PUT", f"organizations/{org_id}", data={"name": name, **kwargs})

        # Create new
        logger.info("creating_pipedrive_organization", name=name)
        result = await self._make_request("POST", "organizations", data={"name": name, **kwargs})
        return result.get("data", {})

    async def search_organizations(self, term: str) -> list[dict[str, Any]]:
        """Search for organizations by name."""
        result = await self._make_request("GET", "organizations/search", params={"term": term})
        return result.get("data", {}).get("items", [])

    async def get_organization(self, org_id: int) -> dict[str, Any]:
        """Get organization by ID."""
        result = await self._make_request("GET", f"organizations/{org_id}")
        return result.get("data", {})

    # Person methods
    async def upsert_person(
        self, name: str, email: str | None = None, org_id: int | None = None, **kwargs
    ) -> dict[str, Any]:
        """Create or update a Pipedrive person."""
        data = {"name": name, **kwargs}
        if email:
            data["email"] = [email]
        if org_id:
            data["org_id"] = org_id

        logger.info("creating_pipedrive_person", name=name, org_id=org_id)
        result = await self._make_request("POST", "persons", data=data)
        return result.get("data", {})

    # Deal methods
    async def upsert_deal(
        self, title: str, org_id: int | None = None, person_id: int | None = None, **kwargs
    ) -> dict[str, Any]:
        """Create or update a Pipedrive deal."""
        data = {"title": title, **kwargs}
        if org_id:
            data["org_id"] = org_id
        if person_id:
            data["person_id"] = person_id

        logger.info("creating_pipedrive_deal", title=title, org_id=org_id)
        result = await self._make_request("POST", "deals", data=data)
        return result.get("data", {})

    # Note methods
    async def add_note(
        self,
        content: str,
        org_id: int | None = None,
        person_id: int | None = None,
        deal_id: int | None = None,
    ) -> dict[str, Any]:
        """Add a note to an organization, person, or deal."""
        data = {"content": content}
        if org_id:
            data["org_id"] = org_id
        if person_id:
            data["person_id"] = person_id
        if deal_id:
            data["deal_id"] = deal_id

        logger.info("adding_pipedrive_note", org_id=org_id, person_id=person_id, deal_id=deal_id)
        result = await self._make_request("POST", "notes", data=data)
        return result.get("data", {})

    # Webhook methods
    @staticmethod
    def validate_webhook_signature(payload: bytes, signature: str) -> bool:
        """Validate Pipedrive webhook signature."""
        if not settings.pipedrive_webhook_secret:
            logger.warning("pipedrive_webhook_secret_not_configured")
            return True  # Skip validation if secret not configured

        expected_signature = hmac.new(
            settings.pipedrive_webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    @staticmethod
    def parse_webhook_event(payload: dict[str, Any]) -> dict[str, Any]:
        """Parse a Pipedrive webhook event."""
        event_type = payload.get("event")
        current_data = payload.get("current", {})
        previous_data = payload.get("previous", {})

        return {
            "event_type": event_type,
            "current": current_data,
            "previous": previous_data,
            "meta": payload.get("meta", {}),
        }

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check on the Pipedrive connection."""
        try:
            # Try to get current user info
            result = await self._make_request("GET", "users/me")
            return {"status": "healthy", "user": result.get("data", {}).get("name")}
        except Exception as e:
            logger.error("pipedrive_health_check_failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}
