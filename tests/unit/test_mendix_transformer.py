"""Unit Tests for Mendix Data Transformer.

Verifies schema normalization, address, party, item, and milestone transformations,
and failure handling.
"""

import pytest

from app.integrations.base.canonical import (
    CanonicalShipmentStatus,
    CanonicalTransportMode,
)
from app.integrations.base.exceptions import IntegrationDataMappingException
from app.integrations.mendix.schemas import (
    MendixAddressModel,
    MendixCargoItemModel,
    MendixCarrierModel,
    MendixMilestoneModel,
    MendixPartyModel,
    MendixShipmentPayload,
)
from app.integrations.mendix.transformer import MendixDataTransformer


def test_transform_address_complete():
    """Verify full address mapping with coordinates."""
    mdx_addr = MendixAddressModel(
        street="123 Industrial Way",
        city="Detroit",
        state="MI",
        postalCode="48201",
        countryCode="USA",
        lat=42.3314,
        lng=-83.0458,
    )
    canonical = MendixDataTransformer.transform_address(mdx_addr)
    assert canonical.street == "123 Industrial Way"
    assert canonical.city == "Detroit"
    assert canonical.country_code == "USA"
    assert canonical.latitude == 42.3314
    assert canonical.longitude == -83.0458


def test_transform_address_none():
    """Verify None address gracefully produces default fallback."""
    canonical = MendixDataTransformer.transform_address(None)
    assert canonical.city == "Unknown"
    assert canonical.country_code == "XX"


def test_transform_party_complete():
    """Verify party mapping with nested address."""
    mdx_party = MendixPartyModel(
        partyId="CUST-99",
        companyName="Apex Supplies LLC",
        contactPerson="Jane Doe",
        phone="+1-555-8888",
        email="jane@apex.com",
        address=MendixAddressModel(city="Cleveland", countryCode="USA"),
    )
    party = MendixDataTransformer.transform_party(mdx_party)
    assert party.party_id == "CUST-99"
    assert party.name == "Apex Supplies LLC"
    assert party.contact_name == "Jane Doe"
    assert party.contact_email == "jane@apex.com"
    assert party.address.city == "Cleveland"


def test_to_canonical_shipment_success():
    """Verify end-to-end transformation of full Mendix payload into CanonicalShipment."""
    raw = {
        "mendixId": "MDX-SHP-5000",
        "orderNumber": "ORD-5000",
        "trackingNumber": "TRK-5000",
        "statusCode": "IN_TRANSIT",
        "transportType": "TRUCK",
        "carrier": {"code": "FDX", "name": "FedEx Freight"},
        "shipper": {
            "companyName": "Tech Hub",
            "address": {"city": "San Jose", "countryCode": "USA"},
        },
        "consignee": {
            "companyName": "Retail Store 1",
            "address": {"city": "Phoenix", "countryCode": "USA"},
        },
        "cargoItems": [
            {
                "itemSku": "SKU-1",
                "itemDescription": "Server Racks",
                "quantity": 2,
                "weightKg": 150.0,
                "volumeCbm": 1.2,
            },
            {
                "itemSku": "SKU-2",
                "itemDescription": "Cables",
                "quantity": 10,
                "weightKg": 25.0,
                "volumeCbm": 0.3,
            },
        ],
        "milestones": [
            {
                "code": "DEP",
                "description": "Departed warehouse",
                "targetTime": "2026-11-19T08:00:00Z",
                "completedTime": "2026-11-19T08:05:00Z",
                "status": "COMPLETED",
            }
        ],
        "expectedDelivery": "2026-11-21T18:00:00Z",
    }

    canonical = MendixDataTransformer.to_canonical_shipment(raw)

    assert canonical.external_reference == "MDX-SHP-5000"
    assert canonical.order_number == "ORD-5000"
    assert canonical.tracking_number == "TRK-5000"
    assert canonical.source_system == "MENDIX"
    assert canonical.status == CanonicalShipmentStatus.IN_TRANSIT
    assert canonical.transport_mode == CanonicalTransportMode.ROAD
    assert canonical.carrier_code == "FDX"
    assert canonical.total_weight_kg == 175.0
    assert canonical.total_volume_cbm == pytest.approx(1.5)
    assert canonical.total_packages == 12
    assert len(canonical.line_items) == 2
    assert len(canonical.milestones) == 1
    assert canonical.milestones[0].event_code == "DEP"
    assert canonical.estimated_delivery.year == 2026


def test_to_canonical_shipment_status_and_mode_mapping():
    """Verify various aliases map correctly to normalized enums."""
    test_cases = [
        ("LATE", CanonicalShipmentStatus.DELAYED),
        ("ALERT", CanonicalShipmentStatus.EXCEPTION),
        ("COMPLETED", CanonicalShipmentStatus.DELIVERED),
        ("LOADED", CanonicalShipmentStatus.PICKED_UP),
    ]

    base_payload = {
        "mendixId": "TEST-1",
        "orderNumber": "ORD-1",
        "transportType": "FLIGHT",
        "carrier": {"code": "AA", "name": "American Airlines"},
        "shipper": {"companyName": "S1", "address": {"city": "C1", "countryCode": "US"}},
        "consignee": {"companyName": "C1", "address": {"city": "C2", "countryCode": "US"}},
        "expectedDelivery": "2026-11-20T12:00:00Z",
    }

    for status_str, expected_status in test_cases:
        payload = dict(base_payload)
        payload["statusCode"] = status_str
        canonical = MendixDataTransformer.to_canonical_shipment(payload)
        assert canonical.status == expected_status
        assert canonical.transport_mode == CanonicalTransportMode.AIR


def test_to_canonical_shipment_invalid_payload_raises_mapping_exception():
    """Verify that malformed or incomplete payload raises IntegrationDataMappingException."""
    invalid_raw = {
        "mendixId": "INV-1",
        # missing orderNumber, carrier, shipper, etc.
    }

    with pytest.raises(IntegrationDataMappingException) as exc_info:
        MendixDataTransformer.to_canonical_shipment(invalid_raw)

    assert "Data transformation error" in str(exc_info.value)
