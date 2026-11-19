"""Mendix Data Transformation Pipeline.

Transforms external Mendix REST JSON payloads into normalized Canonical models
used by core Control Tower domain modules.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.integrations.base.canonical import (
    CanonicalAddress,
    CanonicalLineItem,
    CanonicalMilestone,
    CanonicalParty,
    CanonicalShipment,
    CanonicalShipmentStatus,
    CanonicalTransportMode,
)
from app.integrations.base.exceptions import IntegrationDataMappingException
from app.integrations.mendix.schemas import (
    MendixAddressModel,
    MendixCargoItemModel,
    MendixMilestoneModel,
    MendixPartyModel,
    MendixShipmentPayload,
)

logger = get_logger("control_tower.integrations.mendix.transformer")

# Mapping of Mendix status codes to CanonicalShipmentStatus
STATUS_MAP: Dict[str, CanonicalShipmentStatus] = {
    "CREATED": CanonicalShipmentStatus.CREATED,
    "NEW": CanonicalShipmentStatus.CREATED,
    "DRAFT": CanonicalShipmentStatus.CREATED,
    "BOOKED": CanonicalShipmentStatus.BOOKED,
    "CONFIRMED": CanonicalShipmentStatus.BOOKED,
    "PICKED_UP": CanonicalShipmentStatus.PICKED_UP,
    "LOADED": CanonicalShipmentStatus.PICKED_UP,
    "IN_TRANSIT": CanonicalShipmentStatus.IN_TRANSIT,
    "ON_WAY": CanonicalShipmentStatus.IN_TRANSIT,
    "OUT_FOR_DELIVERY": CanonicalShipmentStatus.OUT_FOR_DELIVERY,
    "DELIVERED": CanonicalShipmentStatus.DELIVERED,
    "COMPLETED": CanonicalShipmentStatus.DELIVERED,
    "DELAYED": CanonicalShipmentStatus.DELAYED,
    "LATE": CanonicalShipmentStatus.DELAYED,
    "EXCEPTION": CanonicalShipmentStatus.EXCEPTION,
    "ALERT": CanonicalShipmentStatus.EXCEPTION,
    "CANCELLED": CanonicalShipmentStatus.CANCELLED,
    "VOID": CanonicalShipmentStatus.CANCELLED,
}

# Mapping of Mendix transport types to CanonicalTransportMode
TRANSPORT_MAP: Dict[str, CanonicalTransportMode] = {
    "ROAD": CanonicalTransportMode.ROAD,
    "TRUCK": CanonicalTransportMode.ROAD,
    "HIGHWAY": CanonicalTransportMode.ROAD,
    "AIR": CanonicalTransportMode.AIR,
    "FLIGHT": CanonicalTransportMode.AIR,
    "PLANE": CanonicalTransportMode.AIR,
    "OCEAN": CanonicalTransportMode.OCEAN,
    "SEA": CanonicalTransportMode.OCEAN,
    "VESSEL": CanonicalTransportMode.OCEAN,
    "RAIL": CanonicalTransportMode.RAIL,
    "TRAIN": CanonicalTransportMode.RAIL,
    "MULTIMODAL": CanonicalTransportMode.MULTIMODAL,
    "INTERMODAL": CanonicalTransportMode.MULTIMODAL,
}


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Safely parses ISO-8601 string into timezone-aware UTC datetime."""
    if not value:
        return None
    try:
        # Standardize trailing 'Z' to '+00:00' for Python fromisoformat
        clean_val = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as exc:
        logger.warning(f"Failed to parse datetime '{value}': {exc}")
        return None


class MendixDataTransformer:
    """Pipeline transforming Mendix payloads into canonical models."""

    @classmethod
    def transform_address(cls, mdx_addr: Optional[MendixAddressModel]) -> CanonicalAddress:
        if not mdx_addr:
            return CanonicalAddress(city="Unknown", country_code="XX")
        return CanonicalAddress(
            street=mdx_addr.street,
            city=mdx_addr.city,
            state_province=mdx_addr.state,
            postal_code=mdx_addr.postalCode,
            country_code=mdx_addr.countryCode.upper(),
            latitude=mdx_addr.lat,
            longitude=mdx_addr.lng,
        )

    @classmethod
    def transform_party(cls, mdx_party: MendixPartyModel) -> CanonicalParty:
        return CanonicalParty(
            party_id=mdx_party.partyId,
            name=mdx_party.companyName,
            address=cls.transform_address(mdx_party.address),
            contact_name=mdx_party.contactPerson,
            contact_email=mdx_party.email,
            contact_phone=mdx_party.phone,
        )

    @classmethod
    def transform_cargo_item(cls, item: MendixCargoItemModel) -> CanonicalLineItem:
        return CanonicalLineItem(
            sku=item.itemSku,
            description=item.itemDescription,
            quantity=item.quantity,
            weight_kg=item.weightKg,
            volume_cbm=item.volumeCbm,
            declared_value=item.declaredValue,
            currency=item.currency or "USD",
        )

    @classmethod
    def transform_milestone(cls, m: MendixMilestoneModel) -> CanonicalMilestone:
        return CanonicalMilestone(
            milestone_id=m.id,
            event_code=m.code,
            title=m.description,
            location_name=m.location,
            planned_time=_parse_iso_datetime(m.targetTime),
            actual_time=_parse_iso_datetime(m.completedTime),
            status=m.status.upper(),
            notes=m.notes,
        )

    @classmethod
    def to_canonical_shipment(cls, raw: Any) -> CanonicalShipment:
        """Transforms a raw Mendix payload (dict or MendixShipmentPayload) into CanonicalShipment."""
        try:
            if isinstance(raw, dict):
                mdx = MendixShipmentPayload(**raw)
            elif isinstance(raw, MendixShipmentPayload):
                mdx = raw
            else:
                raise ValueError(f"Unsupported payload type: {type(raw)}")

            # Status resolution
            normalized_status = STATUS_MAP.get(
                mdx.statusCode.upper(),
                CanonicalShipmentStatus.CREATED,
            )

            # Mode resolution
            normalized_mode = TRANSPORT_MAP.get(
                mdx.transportType.upper(),
                CanonicalTransportMode.ROAD,
            )

            # Addresses resolution
            origin = (
                cls.transform_address(mdx.originLocation)
                if mdx.originLocation
                else cls.transform_party(mdx.shipper).address
            )
            destination = (
                cls.transform_address(mdx.destinationLocation)
                if mdx.destinationLocation
                else cls.transform_party(mdx.consignee).address
            )

            # Parse timestamps
            expected_delivery_dt = _parse_iso_datetime(mdx.expectedDelivery)
            if not expected_delivery_dt:
                raise ValueError("Expected delivery timestamp is missing or invalid")

            # Transform line items and calculate totals
            line_items = [cls.transform_cargo_item(it) for it in mdx.cargoItems]
            total_weight = sum(it.weight_kg for it in line_items)
            total_volume = sum(it.volume_cbm for it in line_items if it.volume_cbm is not None) or None
            total_packages = sum(it.quantity for it in line_items) if line_items else 1

            # Transform milestones
            milestones = [cls.transform_milestone(m) for m in mdx.milestones]

            return CanonicalShipment(
                external_reference=mdx.mendixId,
                order_number=mdx.orderNumber,
                tracking_number=mdx.trackingNumber,
                source_system="MENDIX",
                status=normalized_status,
                transport_mode=normalized_mode,
                shipper=cls.transform_party(mdx.shipper),
                consignee=cls.transform_party(mdx.consignee),
                origin=origin,
                destination=destination,
                carrier_code=mdx.carrier.code,
                carrier_name=mdx.carrier.name,
                total_weight_kg=total_weight,
                total_volume_cbm=total_volume,
                total_packages=total_packages,
                line_items=line_items,
                milestones=milestones,
                pickup_time_planned=_parse_iso_datetime(mdx.plannedDeparture),
                pickup_time_actual=_parse_iso_datetime(mdx.actualDeparture),
                estimated_delivery=expected_delivery_dt,
                actual_delivery=_parse_iso_datetime(mdx.actualDelivery),
                raw_metadata=mdx.customAttributes,
            )

        except Exception as exc:
            logger.error(f"Error mapping Mendix shipment: {exc}")
            raise IntegrationDataMappingException(
                system_name="MENDIX",
                message=str(exc),
                raw_payload=raw,
            ) from exc
