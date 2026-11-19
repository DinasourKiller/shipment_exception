"""Base Integration Adapter Interface.

Defines the contract that all external logistics adapters must fulfill.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.integrations.base.canonical import CanonicalShipment


class BaseIntegrationAdapter(ABC):
    """Abstract interface for external ERP/TMS/Mendix adapters."""

    @property
    @abstractmethod
    def system_name(self) -> str:
        """Name of the external system."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifies operational connectivity and authentication with external system."""
        pass

    @abstractmethod
    async def fetch_shipment(self, external_reference: str) -> CanonicalShipment:
        """Fetches a single shipment by its external identifier and transforms it to Canonical model."""
        pass

    @abstractmethod
    async def fetch_updated_shipments(
        self,
        since: datetime,
        limit: int = 50,
    ) -> List[CanonicalShipment]:
        """Fetches batch of shipments modified since a specified timestamp."""
        pass

    @abstractmethod
    async def push_exception_notification(
        self,
        external_reference: str,
        exception_data: Dict[str, Any],
    ) -> bool:
        """Pushes an exception notification or recovery update back to the external system."""
        pass
