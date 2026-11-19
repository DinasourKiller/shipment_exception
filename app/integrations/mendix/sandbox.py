"""Mock Mendix Sandbox Router for Development & Integration Testing.

Simulates Mendix REST endpoints so the control tower can ingest shipments
and push exception updates in local and sandbox environments without needing
a live enterprise Mendix server.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, status

from app.integrations.mendix.schemas import (
    MendixAddressModel,
    MendixCargoItemModel,
    MendixCarrierModel,
    MendixExceptionSyncRequest,
    MendixMilestoneModel,
    MendixPartyModel,
    MendixShipmentListResponse,
    MendixShipmentPayload,
)

sandbox_router = APIRouter(prefix="/mock/mendix", tags=["Mendix Sandbox"])

# Seed data for sandbox
MOCK_SHIPMENTS: Dict[str, MendixShipmentPayload] = {
    "MDX-SHP-1001": MendixShipmentPayload(
        mendixId="MDX-SHP-1001",
        orderNumber="ORD-2026-001",
        trackingNumber="1Z9999999999999999",
        statusCode="IN_TRANSIT",
        transportType="ROAD",
        carrier=MendixCarrierModel(code="APEX", name="Apex Logistics"),
        shipper=MendixPartyModel(
            partyId="PTY-SHIP-01",
            companyName="Acme Industrial Corp",
            contactPerson="Alice Brown",
            phone="+1-555-1234",
            email="shipping@acmeindustrial.com",
            address=MendixAddressModel(
                street="100 Factory Lane",
                city="Chicago",
                state="IL",
                postalCode="60601",
                countryCode="USA",
                lat=41.8781,
                lng=-87.6298,
            ),
        ),
        consignee=MendixPartyModel(
            partyId="PTY-CONS-01",
            companyName="Global Retail Warehouse",
            contactPerson="Bob Johnson",
            phone="+1-555-5678",
            email="receiving@globalretail.com",
            address=MendixAddressModel(
                street="500 Distribution Blvd",
                city="Dallas",
                state="TX",
                postalCode="75201",
                countryCode="USA",
                lat=32.7767,
                lng=-96.7970,
            ),
        ),
        cargoItems=[
            MendixCargoItemModel(
                itemSku="SKU-ELEC-409",
                itemDescription="High-precision sensor arrays",
                quantity=20,
                weightKg=450.5,
                volumeCbm=2.8,
                declaredValue=85000.0,
                currency="USD",
            )
        ],
        milestones=[
            MendixMilestoneModel(
                id="MS-01",
                code="PICKUP_COMPLETED",
                description="Departed Shipper Dock",
                location="Chicago, IL",
                targetTime="2026-11-19T06:00:00Z",
                completedTime="2026-11-19T06:15:00Z",
                status="COMPLETED",
            ),
            MendixMilestoneModel(
                id="MS-02",
                code="HUB_TRANSIT",
                description="Arrived Transit Hub",
                location="St. Louis, MO",
                targetTime="2026-11-19T14:00:00Z",
                completedTime=None,
                status="IN_PROGRESS",
            ),
        ],
        plannedDeparture="2026-11-19T06:00:00Z",
        actualDeparture="2026-11-19T06:15:00Z",
        expectedDelivery="2026-11-20T18:00:00Z",
        customAttributes={"priority": "HIGH", "temperatureControl": False},
    ),
    "MDX-SHP-1002": MendixShipmentPayload(
        mendixId="MDX-SHP-1002",
        orderNumber="ORD-2026-002",
        trackingNumber="TRACK-AIR-9921",
        statusCode="DELAYED",
        transportType="AIR",
        carrier=MendixCarrierModel(code="SKYCARGO", name="Skyward Air Cargo"),
        shipper=MendixPartyModel(
            companyName="BioPharma Labs",
            contactPerson="Dr. Alan Grant",
            phone="+1-555-4321",
            email="dispatch@biopharma.org",
            address=MendixAddressModel(
                street="88 Biotech Way",
                city="Boston",
                state="MA",
                postalCode="02115",
                countryCode="USA",
            ),
        ),
        consignee=MendixPartyModel(
            companyName="St. Jude Medical Center",
            contactPerson="Dr. Ellie Sattler",
            phone="+1-555-8765",
            email="pharmacy@stjude.org",
            address=MendixAddressModel(
                street="12 Medical Plaza",
                city="Atlanta",
                state="GA",
                postalCode="30303",
                countryCode="USA",
            ),
        ),
        cargoItems=[
            MendixCargoItemModel(
                itemSku="MED-VACC-001",
                itemDescription="Temperature-controlled vaccines",
                quantity=5,
                weightKg=50.0,
                volumeCbm=0.5,
                declaredValue=250000.0,
                currency="USD",
            )
        ],
        expectedDelivery="2026-11-19T22:00:00Z",
        customAttributes={"priority": "CRITICAL", "temperatureControlled": True, "targetTempC": 4.0},
    ),
}


@sandbox_router.get("/health", status_code=status.HTTP_200_OK)
async def mendix_health_check():
    """Simulates Mendix REST health endpoint."""
    return {"status": "UP", "system": "Mendix Logistics REST API", "timestamp": datetime.now(timezone.utc).isoformat()}


@sandbox_router.get("/shipments/{external_reference}", response_model=MendixShipmentPayload)
async def get_mendix_shipment(
    external_reference: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Simulates retrieving a shipment by reference ID from Mendix."""
    if x_api_key == "invalid-key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Mendix API Key")

    shipment = MOCK_SHIPMENTS.get(external_reference)
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{external_reference}' not found in Mendix database",
        )
    return shipment


@sandbox_router.get("/shipments", response_model=MendixShipmentListResponse)
async def list_mendix_shipments(
    updatedSince: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Simulates paginated list of shipments from Mendix."""
    if x_api_key == "invalid-key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Mendix API Key")

    items = list(MOCK_SHIPMENTS.values())[:limit]
    return MendixShipmentListResponse(totalCount=len(items), items=items)


@sandbox_router.post("/shipments/{external_reference}/exceptions", status_code=status.HTTP_202_ACCEPTED)
async def sync_exception_to_mendix(
    external_reference: str,
    payload: MendixExceptionSyncRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Simulates Mendix receiving an operational exception notification from Control Tower."""
    if x_api_key == "invalid-key":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Mendix API Key")

    if external_reference not in MOCK_SHIPMENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment '{external_reference}' not found",
        )

    return {
        "status": "ACCEPTED",
        "mendixId": external_reference,
        "syncTimestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Exception notice recorded in Mendix for {external_reference}",
    }
