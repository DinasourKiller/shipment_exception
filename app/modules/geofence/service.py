"""Geofencing, Dynamic Corridors & Dwell Anomaly Service."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, EntityNotFoundException, ValidationException
from app.core.logging import get_logger
from app.modules.geofence.geometry import (
    calculate_cross_track_deviation_meters,
    is_point_in_circular_geofence,
    is_point_in_polygon,
)
from app.modules.geofence.models import GeofenceZone, ShipmentDwellEvent
from app.modules.geofence.repository import GeofenceRepository
from app.modules.geofence.schemas import (
    GeofenceZoneCreateRequest,
    GeofenceZoneResponse,
    GeofenceZoneUpdateRequest,
    PaginatedGeofenceResponse,
    ShipmentDwellEventResponse,
    SpatialEvaluationRequest,
    SpatialEvaluationResponse,
)
from app.modules.shipments.repository import ShipmentRepository

logger = get_logger("control_tower.geofence.service")


class GeofenceService:
    """Business logic for spatial perimeters, route corridor monitoring, and dwell tracking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.geofence_repo = GeofenceRepository(session)
        self.shipment_repo = ShipmentRepository(session)

    async def create_geofence_zone(
        self,
        request: GeofenceZoneCreateRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> GeofenceZoneResponse:
        """Create and validate a new circular or polygonal geofence perimeter."""
        existing = await self.geofence_repo.get_by_code(request.zone_code)
        if existing:
            raise ConflictException(f"Geofence zone with code '{request.zone_code}' already exists")

        geom_type = request.geometry_type.upper()
        if geom_type == "CIRCULAR":
            if request.center_latitude is None or request.center_longitude is None:
                raise ValidationException("Circular geofences require center_latitude and center_longitude")
            if not request.radius_meters or request.radius_meters <= 0:
                raise ValidationException("Circular geofences require a positive radius_meters")
        elif geom_type == "POLYGON":
            if not request.polygon_coordinates or len(request.polygon_coordinates) < 3:
                raise ValidationException("Polygon geofences require at least 3 [latitude, longitude] vertices")
        else:
            raise ValidationException(f"Unsupported geometry type '{request.geometry_type}'. Use CIRCULAR or POLYGON")

        zone = GeofenceZone(
            zone_code=request.zone_code.upper().strip(),
            name=request.name.strip(),
            description=request.description,
            zone_type=request.zone_type.upper().strip(),
            geometry_type=geom_type,
            center_latitude=request.center_latitude,
            center_longitude=request.center_longitude,
            radius_meters=request.radius_meters,
            polygon_coordinates=request.polygon_coordinates,
            max_permitted_dwell_minutes=request.max_permitted_dwell_minutes,
            is_active=request.is_active,
            metadata_json=request.metadata_json or {},
        )

        saved_zone = await self.geofence_repo.create_zone(zone)
        await self.session.commit()

        # Phase 15 System Audit Trail
        try:
            from app.modules.audit.service import AuditService
            audit_svc = AuditService(self.session)
            await audit_svc.record_event(
                action="GEOFENCE_ZONE_CREATED",
                resource_type="GEOFENCE_ZONE",
                resource_id=str(saved_zone.id),
                actor_id=actor_id,
                diff_summary={
                    "zone_code": saved_zone.zone_code,
                    "name": saved_zone.name,
                    "zone_type": saved_zone.zone_type,
                    "geometry_type": saved_zone.geometry_type,
                },
            )
            await self.session.commit()
        except Exception as audit_err:
            logger.debug("Audit record skipped for geofence: %s", audit_err)

        return GeofenceZoneResponse.model_validate(saved_zone)

    async def get_geofence_zone(self, zone_id: uuid.UUID) -> GeofenceZoneResponse:
        """Fetch geofence zone by ID."""
        zone = await self.geofence_repo.get_by_id(zone_id)
        if not zone:
            raise EntityNotFoundException("GeofenceZone", str(zone_id))
        return GeofenceZoneResponse.model_validate(zone)

    async def list_geofence_zones(
        self,
        active_only: bool = False,
        zone_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedGeofenceResponse:
        """List paginated geofence zones."""
        items, total = await self.geofence_repo.list_zones(
            active_only=active_only,
            zone_type=zone_type,
            search=search,
            page=page,
            page_size=page_size,
        )
        total_pages = max(1, (total + page_size - 1) // page_size)
        return PaginatedGeofenceResponse(
            items=[GeofenceZoneResponse.model_validate(z) for z in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def update_geofence_zone(
        self,
        zone_id: uuid.UUID,
        request: GeofenceZoneUpdateRequest,
    ) -> GeofenceZoneResponse:
        """Update existing geofence zone boundary or settings."""
        zone = await self.geofence_repo.get_by_id(zone_id)
        if not zone:
            raise EntityNotFoundException("GeofenceZone", str(zone_id))

        if request.name is not None:
            zone.name = request.name.strip()
        if request.description is not None:
            zone.description = request.description
        if request.zone_type is not None:
            zone.zone_type = request.zone_type.upper().strip()
        if request.geometry_type is not None:
            zone.geometry_type = request.geometry_type.upper().strip()
        if request.center_latitude is not None:
            zone.center_latitude = request.center_latitude
        if request.center_longitude is not None:
            zone.center_longitude = request.center_longitude
        if request.radius_meters is not None:
            zone.radius_meters = request.radius_meters
        if request.polygon_coordinates is not None:
            zone.polygon_coordinates = request.polygon_coordinates
        if request.max_permitted_dwell_minutes is not None:
            zone.max_permitted_dwell_minutes = request.max_permitted_dwell_minutes
        if request.is_active is not None:
            zone.is_active = request.is_active
        if request.metadata_json is not None:
            zone.metadata_json = request.metadata_json

        updated = await self.geofence_repo.update_zone(zone)
        await self.session.commit()
        return GeofenceZoneResponse.model_validate(updated)

    async def delete_geofence_zone(self, zone_id: uuid.UUID) -> None:
        """Delete a geofence zone."""
        zone = await self.geofence_repo.get_by_id(zone_id)
        if not zone:
            raise EntityNotFoundException("GeofenceZone", str(zone_id))
        await self.geofence_repo.delete_zone(zone)
        await self.session.commit()

    async def evaluate_shipment_spatial_telemetry(
        self,
        request: SpatialEvaluationRequest,
    ) -> SpatialEvaluationResponse:
        """Comprehensive spatial evaluation: geofence perimeters, route corridor deviation, and dwell anomalies."""
        shipment = await self.shipment_repo.get_by_id(request.shipment_id)
        if not shipment:
            raise EntityNotFoundException("Shipment", str(request.shipment_id))

        eval_time = request.timestamp or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        # 1. Fetch active geofences and test inclusion
        active_zones = await self.geofence_repo.get_all_active_zones()
        matching_zones: List[GeofenceZone] = []

        for zone in active_zones:
            inside = False
            if zone.geometry_type == "CIRCULAR":
                inside = is_point_in_circular_geofence(
                    request.latitude,
                    request.longitude,
                    zone.center_latitude,
                    zone.center_longitude,
                    zone.radius_meters,
                )
            elif zone.geometry_type == "POLYGON":
                inside = is_point_in_polygon(
                    request.latitude,
                    request.longitude,
                    zone.polygon_coordinates,
                )
            if inside:
                matching_zones.append(zone)

        current_zone_names = [z.name for z in matching_zones]
        primary_zone = matching_zones[0] if matching_zones else None

        generated_exception_id = None
        generated_exception_type = None
        is_restricted_breach = False

        # 2. Check for RESTRICTED_AREA intrusion
        for zone in matching_zones:
            if zone.zone_type == "RESTRICTED_AREA":
                is_restricted_breach = True
                exc = await self._trigger_spatial_exception(
                    shipment=shipment,
                    exception_type="GEOFENCE_BREACH",
                    severity="CRITICAL",
                    title=f"Restricted Geofence Intrusion: {zone.name}",
                    description=(
                        f"Shipment {shipment.tracking_number} breached restricted boundary '{zone.name}' "
                        f"({zone.zone_code}) at coordinates ({request.latitude:.4f}, {request.longitude:.4f})."
                    ),
                    metadata_payload={
                        "zone_code": zone.zone_code,
                        "zone_name": zone.name,
                        "latitude": request.latitude,
                        "longitude": request.longitude,
                    },
                )
                if exc:
                    generated_exception_id = exc.id
                    generated_exception_type = "GEOFENCE_BREACH"
                break

        # 3. Temporal Dwell & Stationary Detention Analysis
        is_stationary = request.speed_kmh < 3.0
        active_dwell = await self.geofence_repo.get_active_dwell_for_shipment(shipment.id)
        dwell_duration_minutes = 0.0
        is_unauthorized_dwell = False
        is_dwell_active = False

        if is_stationary:
            is_dwell_active = True
            if active_dwell:
                # Existing dwell continuing
                active_dwell.stationary_pings_count += 1
                dwell_duration_minutes = max(
                    0.0,
                    (eval_time - active_dwell.dwell_started_at).total_seconds() / 60.0,
                )
                active_dwell.dwell_duration_minutes = dwell_duration_minutes
                active_dwell.latitude = request.latitude
                active_dwell.longitude = request.longitude
                if request.location_name:
                    active_dwell.location_name = request.location_name

                # Check permitted limit
                max_permitted = (
                    primary_zone.max_permitted_dwell_minutes
                    if primary_zone
                    else 60  # Default 60 mins for unscheduled off-terminal stops
                )

                if dwell_duration_minutes > max_permitted:
                    is_unauthorized_dwell = True
                    active_dwell.is_authorized = False

                    # Trigger alert once when threshold is breached
                    if not active_dwell.is_alert_dispatched and not generated_exception_id:
                        zone_desc = f"in '{primary_zone.name}'" if primary_zone else "at unauthorized waypoint"
                        exc = await self._trigger_spatial_exception(
                            shipment=shipment,
                            exception_type="UNAUTHORIZED_DWELL",
                            severity="HIGH",
                            title=f"Excessive Dwell Detention: {dwell_duration_minutes:.0f} mins stationary",
                            description=(
                                f"Vehicle stationary for {dwell_duration_minutes:.0f} mins {zone_desc} "
                                f"(permitted limit: {max_permitted} mins) at ({request.latitude:.4f}, {request.longitude:.4f})."
                            ),
                            metadata_payload={
                                "dwell_id": str(active_dwell.id),
                                "dwell_duration_minutes": round(dwell_duration_minutes, 1),
                                "permitted_minutes": max_permitted,
                                "geofence_zone": primary_zone.zone_code if primary_zone else None,
                            },
                        )
                        if exc:
                            active_dwell.is_alert_dispatched = True
                            active_dwell.exception_id = exc.id
                            generated_exception_id = exc.id
                            generated_exception_type = "UNAUTHORIZED_DWELL"

                await self.geofence_repo.update_dwell_event(active_dwell)
            else:
                # Commence new dwell
                new_dwell = ShipmentDwellEvent(
                    shipment_id=shipment.id,
                    geofence_zone_id=primary_zone.id if primary_zone else None,
                    latitude=request.latitude,
                    longitude=request.longitude,
                    location_name=request.location_name or (primary_zone.name if primary_zone else None),
                    dwell_started_at=eval_time,
                    dwell_duration_minutes=0.0,
                    stationary_pings_count=1,
                    is_authorized=True,
                    is_alert_dispatched=False,
                )
                await self.geofence_repo.create_dwell_event(new_dwell)
        else:
            # Vehicle in motion (speed >= 3.0 km/h)
            if active_dwell:
                # Conclude ongoing dwell
                active_dwell.dwell_ended_at = eval_time
                active_dwell.dwell_duration_minutes = max(
                    0.0,
                    (eval_time - active_dwell.dwell_started_at).total_seconds() / 60.0,
                )
                await self.geofence_repo.update_dwell_event(active_dwell)

        # 4. Dynamic Route Corridor Deviation Evaluation
        corridor_deviation_km = None
        is_corridor_deviated = False

        # Attempt to compute route corridor if planned milestones/origin-dest exist
        origin_lat, origin_lon, dest_lat, dest_lon = self._extract_route_corridor_vector(shipment)
        if (
            origin_lat is not None
            and origin_lon is not None
            and dest_lat is not None
            and dest_lon is not None
        ):
            dev_meters = calculate_cross_track_deviation_meters(
                current_lat=request.latitude,
                current_lon=request.longitude,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
                dest_lat=dest_lat,
                dest_lon=dest_lon,
            )
            corridor_deviation_km = round(dev_meters / 1000.0, 2)
            # Threshold: 50 km cross-track deviation considered corridor departure
            if corridor_deviation_km > 50.0 and not generated_exception_id:
                is_corridor_deviated = True
                exc = await self._trigger_spatial_exception(
                    shipment=shipment,
                    exception_type="ROUTE_DEVIATION",
                    severity="HIGH",
                    title=f"Dynamic Corridor Breach: {corridor_deviation_km} km Off Planned Route",
                    description=(
                        f"Shipment {shipment.tracking_number} departed the planned corridor by {corridor_deviation_km} km "
                        f"at coordinates ({request.latitude:.4f}, {request.longitude:.4f})."
                    ),
                    metadata_payload={
                        "corridor_deviation_km": corridor_deviation_km,
                        "latitude": request.latitude,
                        "longitude": request.longitude,
                    },
                )
                if exc:
                    generated_exception_id = exc.id
                    generated_exception_type = "ROUTE_DEVIATION"

        await self.session.commit()

        # Build summary narrative
        summary_parts = []
        if current_zone_names:
            summary_parts.append(f"Inside zone(s): {', '.join(current_zone_names)}")
        else:
            summary_parts.append("Open corridor (outside registered geofences)")

        if is_dwell_active:
            summary_parts.append(f"Stationary dwell {dwell_duration_minutes:.1f} mins")
        else:
            summary_parts.append(f"In motion ({request.speed_kmh:.1f} km/h)")

        if corridor_deviation_km is not None:
            summary_parts.append(f"Corridor offset: {corridor_deviation_km:.1f} km")

        if generated_exception_type:
            summary_parts.append(f"⚠️ Exception triggered: {generated_exception_type}")

        return SpatialEvaluationResponse(
            shipment_id=shipment.id,
            latitude=request.latitude,
            longitude=request.longitude,
            speed_kmh=request.speed_kmh,
            current_geofence_zones=current_zone_names,
            is_inside_restricted_zone=is_restricted_breach,
            is_dwell_active=is_dwell_active,
            dwell_duration_minutes=dwell_duration_minutes,
            is_unauthorized_dwell=is_unauthorized_dwell,
            corridor_deviation_km=corridor_deviation_km,
            is_corridor_deviated=is_corridor_deviated,
            generated_exception_id=generated_exception_id,
            generated_exception_type=generated_exception_type,
            evaluation_summary=" | ".join(summary_parts),
        )

    async def list_dwell_events_for_shipment(
        self,
        shipment_id: uuid.UUID,
    ) -> List[ShipmentDwellEventResponse]:
        """Fetch all dwell and detention event history for a given shipment."""
        dwells = await self.geofence_repo.list_dwells_for_shipment(shipment_id)
        results = []
        for d in dwells:
            resp = ShipmentDwellEventResponse.model_validate(d)
            if d.geofence_zone:
                resp.geofence_zone_name = d.geofence_zone.name
            results.append(resp)
        return results

    def _extract_route_corridor_vector(
        self,
        shipment,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Extract or approximate origin and destination GPS vectors for corridor computation."""
        # 1. Inspect origin and destination facility coordinates from shipment metadata or landmarks
        origin_lat = None
        origin_lon = None
        dest_lat = None
        dest_lon = None

        # Check landmarks for standard demo origins/destinations
        city_coords = {
            "chicago": (41.8781, -87.6298),
            "dallas": (32.7767, -96.7970),
            "boston": (42.3601, -71.0589),
            "atlanta": (33.7490, -84.3880),
            "los angeles": (34.0522, -118.2437),
            "new york": (40.7128, -74.0060),
            "houston": (29.7604, -95.3698),
        }

        if hasattr(shipment, "origin_city") and shipment.origin_city:
            clean_origin = shipment.origin_city.lower()
            if clean_origin in city_coords:
                origin_lat, origin_lon = city_coords[clean_origin]

        if hasattr(shipment, "destination_city") and shipment.destination_city:
            clean_dest = shipment.destination_city.lower()
            if clean_dest in city_coords:
                dest_lat, dest_lon = city_coords[clean_dest]

        return origin_lat, origin_lon, dest_lat, dest_lon

    async def _trigger_spatial_exception(
        self,
        shipment,
        exception_type: str,
        severity: str,
        title: str,
        description: str,
        metadata_payload: dict,
    ):
        """Create an operational shipment exception and publish real-time alert."""
        try:
            from app.modules.exceptions.models import ShipmentException

            exc = ShipmentException(
                shipment_id=shipment.id,
                exception_type=exception_type,
                severity=severity,
                status="OPEN",
                title=title,
                description=description,
                sla_breach_at=datetime.now(timezone.utc) + timedelta(hours=3),
                metadata_payload=metadata_payload,
            )
            self.session.add(exc)
            await self.session.flush()

            # Broadcast real-time WebSocket alert (Phase 16)
            try:
                from app.modules.realtime.broadcaster import broadcaster
                from app.modules.realtime.schemas import CHANNEL_ALERTS_ALL, EVENT_EXCEPTION_TRIGGERED
                broadcaster.publish_nowait(
                    channel=CHANNEL_ALERTS_ALL,
                    event_type=EVENT_EXCEPTION_TRIGGERED,
                    payload={
                        "exception_id": str(exc.id),
                        "shipment_id": str(shipment.id),
                        "tracking_number": shipment.tracking_number,
                        "exception_type": exception_type,
                        "severity": severity,
                        "title": title,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as ws_err:
                logger.debug("WebSocket broadcast skipped: %s", ws_err)

            logger.info("Automatically generated spatial exception %s (%s) for shipment %s", exc.id, exception_type, shipment.id)
            return exc
        except Exception as err:
            logger.warning("Failed to auto-generate spatial exception: %s", err)
            return None
