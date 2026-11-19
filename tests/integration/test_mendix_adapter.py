"""Integration Tests for Mendix Adapter with Sandbox Harness.

Tests end-to-end communication between MendixClient, ResilientHttpClient,
and the Mendix REST Sandbox endpoints.
"""

from datetime import datetime, timezone
import httpx
import pytest

from app.integrations.base.canonical import CanonicalShipmentStatus, CanonicalTransportMode
from app.integrations.base.exceptions import (
    IntegrationAuthenticationException,
    IntegrationException,
)
from app.integrations.mendix.client import MendixClient
from app.main import create_application


@pytest.fixture
def mendix_adapter():
    """Provides a MendixClient wired directly to the test app using ASGITransport."""
    test_app = create_application()
    transport = httpx.ASGITransport(app=test_app)
    client = MendixClient(
        base_url="http://testserver/api/v1/mock/mendix",
        api_key="valid-test-key",
        timeout_seconds=5.0,
        max_retries=1,
        transport=transport,
    )
    return client


@pytest.mark.asyncio
async def test_mendix_health_check_success(mendix_adapter):
    """Verify health_check() returns True when sandbox is reachable."""
    healthy = await mendix_adapter.health_check()
    assert healthy is True
    await mendix_adapter.close()


@pytest.mark.asyncio
async def test_fetch_shipment_success(mendix_adapter):
    """Verify single shipment fetch and transformation to CanonicalShipment."""
    canonical = await mendix_adapter.fetch_shipment("MDX-SHP-1001")

    assert canonical.external_reference == "MDX-SHP-1001"
    assert canonical.order_number == "ORD-2026-001"
    assert canonical.tracking_number == "1Z9999999999999999"
    assert canonical.carrier_code == "APEX"
    assert canonical.carrier_name == "Apex Logistics"
    assert canonical.status == CanonicalShipmentStatus.IN_TRANSIT
    assert canonical.transport_mode == CanonicalTransportMode.ROAD

    # Verify Shipper & Consignee
    assert canonical.shipper.name == "Acme Industrial Corp"
    assert canonical.shipper.address.city == "Chicago"
    assert canonical.shipper.address.state_province == "IL"
    assert canonical.shipper.address.latitude == 41.8781
    assert canonical.consignee.name == "Global Retail Warehouse"
    assert canonical.consignee.address.city == "Dallas"

    # Verify Cargo Items
    assert len(canonical.line_items) == 1
    item = canonical.line_items[0]
    assert item.sku == "SKU-ELEC-409"
    assert item.quantity == 20
    assert item.weight_kg == 450.5
    assert canonical.total_weight_kg == 450.5
    assert canonical.total_packages == 20

    # Verify Milestones
    assert len(canonical.milestones) == 2
    assert canonical.milestones[0].event_code == "PICKUP_COMPLETED"
    assert canonical.milestones[0].status == "COMPLETED"

    await mendix_adapter.close()


@pytest.mark.asyncio
async def test_fetch_updated_shipments_batch(mendix_adapter):
    """Verify batch retrieval and transformation of updated shipments."""
    since = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc)
    shipments = await mendix_adapter.fetch_updated_shipments(since=since, limit=10)

    assert len(shipments) >= 2
    ref_ids = [s.external_reference for s in shipments]
    assert "MDX-SHP-1001" in ref_ids
    assert "MDX-SHP-1002" in ref_ids

    # Verify second shipment (Air cargo)
    shp2 = next(s for s in shipments if s.external_reference == "MDX-SHP-1002")
    assert shp2.transport_mode == CanonicalTransportMode.AIR
    assert shp2.status == CanonicalShipmentStatus.DELAYED
    assert shp2.carrier_code == "SKYCARGO"

    await mendix_adapter.close()


@pytest.mark.asyncio
async def test_push_exception_notification_success(mendix_adapter):
    """Verify push_exception_notification transmits alert and receives 202 Accepted."""
    exception_payload = {
        "type": "CARRIER_DELAY",
        "severity": "HIGH",
        "status": "OPEN",
        "delay_minutes": 180,
        "summary": "Severe highway congestion causing 3-hour delay on I-55",
        "recommended_action": "Reroute via Highway 57 or reassign to backup carrier",
    }

    result = await mendix_adapter.push_exception_notification(
        external_reference="MDX-SHP-1001",
        exception_data=exception_payload,
    )
    assert result is True
    await mendix_adapter.close()


@pytest.mark.asyncio
async def test_fetch_nonexistent_shipment_raises_404_integration_exception(mendix_adapter):
    """Verify fetching nonexistent reference raises IntegrationException with 404."""
    with pytest.raises(IntegrationException) as exc_info:
        await mendix_adapter.fetch_shipment("NONEXISTENT-REF-999")

    assert exc_info.value.status_code == 404
    assert "Shipment 'NONEXISTENT-REF-999' not found" in str(exc_info.value)
    await mendix_adapter.close()


@pytest.mark.asyncio
async def test_mendix_authentication_failure():
    """Verify that rejected API Key raises IntegrationAuthenticationException."""
    test_app = create_application()
    transport = httpx.ASGITransport(app=test_app)
    unauthorized_client = MendixClient(
        base_url="http://testserver/api/v1/mock/mendix",
        api_key="invalid-key",  # triggers 401 in mock router
        timeout_seconds=5.0,
        max_retries=1,
        transport=transport,
    )

    with pytest.raises(IntegrationAuthenticationException) as exc_info:
        await unauthorized_client.fetch_shipment("MDX-SHP-1001")

    assert exc_info.value.status_code == 502
    assert "Authentication rejected" in str(exc_info.value)
    await unauthorized_client.close()
