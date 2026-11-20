"""Mendix Integration REST Client Adapter.

Implements BaseIntegrationAdapter using ResilientHttpClient to communicate with Mendix.
Strictly adheres to integration isolation: core modules only interact with Canonical models.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.integrations.base.adapter import BaseIntegrationAdapter
from app.integrations.base.canonical import CanonicalShipment
from app.integrations.base.http_client import ResilientHttpClient
from app.integrations.mendix.schemas import MendixExceptionSyncRequest
from app.integrations.mendix.transformer import MendixDataTransformer

logger = get_logger("control_tower.integrations.mendix.client")


class MendixClient(BaseIntegrationAdapter):
    """Production adapter for Mendix REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        http_client: Optional[ResilientHttpClient] = None,
        transport: Optional[Any] = None,
    ):
        settings = get_settings()
        raw_url = (base_url or settings.MENDIX_BASE_URL).rstrip("/")
        if "enterprise.local" in raw_url:
            raw_url = f"http://127.0.0.1:{settings.PORT}{settings.API_V1_PREFIX}/mock/mendix"
        self._base_url = raw_url
        self._api_key = api_key or settings.MENDIX_API_KEY
        self._timeout = timeout_seconds or float(settings.MENDIX_TIMEOUT_SECONDS)
        self._max_retries = max_retries if max_retries is not None else settings.MENDIX_MAX_RETRIES

        self._headers = {
            "X-API-Key": self._api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        self._http = http_client or ResilientHttpClient(
            system_name=self.system_name,
            base_url=self._base_url,
            default_headers=self._headers,
            timeout_seconds=self._timeout,
            max_retries=self._max_retries,
            transport=transport,
        )

    @property
    def system_name(self) -> str:
        return "MENDIX"

    async def close(self) -> None:
        """Closes underlying HTTP connections."""
        await self._http.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def health_check(self) -> bool:
        """Checks if Mendix REST API endpoint is responding."""
        try:
            resp = await self._http.get("/health")
            return resp.status_code == 200
        except Exception as exc:
            logger.warning(f"Mendix health check failed: {exc}")
            return False

    async def fetch_shipment(self, external_reference: str) -> CanonicalShipment:
        """Fetches single shipment from Mendix and transforms to Canonical format."""
        logger.info(f"Fetching shipment '{external_reference}' from Mendix")
        resp = await self._http.get(f"/shipments/{external_reference}")
        data = resp.json()
        return MendixDataTransformer.to_canonical_shipment(data)

    async def fetch_updated_shipments(
        self,
        since: datetime,
        limit: int = 50,
    ) -> List[CanonicalShipment]:
        """Fetches batch of modified shipments since a given UTC timestamp."""
        iso_since = since.astimezone(timezone.utc).isoformat()
        logger.info(f"Fetching shipments updated since {iso_since} (limit={limit})")

        resp = await self._http.get(
            "/shipments",
            params={"updatedSince": iso_since, "limit": limit},
        )
        data = resp.json()

        # Handle both list response {"items": [...]} and raw array [...]
        items_raw = data.get("items", []) if isinstance(data, dict) else data

        canonical_list: List[CanonicalShipment] = []
        for raw_item in items_raw:
            try:
                canonical = MendixDataTransformer.to_canonical_shipment(raw_item)
                canonical_list.append(canonical)
            except Exception as item_err:
                logger.error(f"Failed to transform Mendix shipment item: {item_err}")
                continue

        logger.info(f"Successfully retrieved and transformed {len(canonical_list)} shipments from Mendix")
        return canonical_list

    async def push_exception_notification(
        self,
        external_reference: str,
        exception_data: Dict[str, Any],
    ) -> bool:
        """Pushes exception notice to Mendix for synchronization."""
        logger.info(f"Pushing exception alert to Mendix for shipment '{external_reference}'")
        sync_payload = MendixExceptionSyncRequest(
            mendixId=external_reference,
            exceptionType=str(exception_data.get("type", "DELAY")),
            severity=str(exception_data.get("severity", "MEDIUM")),
            status=str(exception_data.get("status", "OPEN")),
            impactDelayMinutes=exception_data.get("delay_minutes"),
            summary=str(exception_data.get("summary", "Exception detected")),
            recommendedAction=exception_data.get("recommended_action"),
        )

        resp = await self._http.post(
            f"/shipments/{external_reference}/exceptions",
            json_data=sync_payload.model_dump(),
        )
        return resp.status_code in (200, 201, 202)
