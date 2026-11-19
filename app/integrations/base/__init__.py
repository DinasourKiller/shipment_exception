"""Base integration exports."""

from app.integrations.base.adapter import BaseIntegrationAdapter
from app.integrations.base.canonical import (
    CanonicalAddress,
    CanonicalLineItem,
    CanonicalMilestone,
    CanonicalParty,
    CanonicalShipment,
    CanonicalShipmentStatus,
    CanonicalTransportMode,
)
from app.integrations.base.exceptions import (
    IntegrationAuthenticationException,
    IntegrationConnectionException,
    IntegrationDataMappingException,
    IntegrationException,
    IntegrationTimeoutException,
)
from app.integrations.base.http_client import ResilientHttpClient

__all__ = [
    "BaseIntegrationAdapter",
    "CanonicalAddress",
    "CanonicalLineItem",
    "CanonicalMilestone",
    "CanonicalParty",
    "CanonicalShipment",
    "CanonicalShipmentStatus",
    "CanonicalTransportMode",
    "IntegrationAuthenticationException",
    "IntegrationConnectionException",
    "IntegrationDataMappingException",
    "IntegrationException",
    "IntegrationTimeoutException",
    "ResilientHttpClient",
]
