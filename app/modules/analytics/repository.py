"""Analytics & Reporting Database Repository.

Executes aggregation queries across Shipments, Exceptions, Impact Assessments,
and Carrier Recovery plans.
"""

from typing import Any, Dict, List, Tuple
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.exceptions.models import ExceptionSeverity, ExceptionStatus, ShipmentException
from app.modules.impact.models import ImpactAssessment
from app.modules.recovery.models import RecoveryPlan, RecoveryStatus
from app.modules.shipments.models import Shipment


class AnalyticsRepository:
    """Provides analytical aggregation data access across operational domains."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_carrier_scorecard_data(self) -> List[Dict[str, Any]]:
        """Aggregates shipment volume, disruption counts, and on-time performance by carrier."""
        # 1. Total shipments and on-time count per carrier
        shipment_stmt = select(
            Shipment.carrier_code,
            Shipment.carrier_name,
            func.count(distinct(Shipment.id)).label("total_shipments"),
            func.count(
                distinct(
                    case(
                        (
                            (Shipment.status == "DELIVERED")
                            & (Shipment.actual_delivery.is_not(None))
                            & (Shipment.actual_delivery <= Shipment.estimated_delivery),
                            Shipment.id,
                        ),
                        else_=None,
                    )
                )
            ).label("on_time_count"),
        ).group_by(Shipment.carrier_code, Shipment.carrier_name)

        shipment_rows = (await self.session.execute(shipment_stmt)).all()

        # 2. Exceptions count per carrier
        exc_stmt = (
            select(
                Shipment.carrier_code,
                func.count(distinct(ShipmentException.id)).label("exceptions_count"),
            )
            .join(ShipmentException, Shipment.id == ShipmentException.shipment_id)
            .group_by(Shipment.carrier_code)
        )
        exc_rows = dict((await self.session.execute(exc_stmt)).all())

        # 3. Average recovery turnaround hours per carrier
        rec_stmt = (
            select(
                RecoveryPlan.carrier_code,
                func.coalesce(func.avg(RecoveryPlan.estimated_recovery_hours), 0.0).label("avg_rec_hours"),
            )
            .where(RecoveryPlan.status.in_([RecoveryStatus.DISPATCHED.value, RecoveryStatus.COMPLETED.value]))
            .group_by(RecoveryPlan.carrier_code)
        )
        rec_rows = dict((await self.session.execute(rec_stmt)).all())

        results = []
        for row in shipment_rows:
            carrier_code = row.carrier_code
            tot = row.total_shipments
            on_time = row.on_time_count
            exc_count = exc_rows.get(carrier_code, 0)
            avg_rec = float(rec_rows.get(carrier_code, 2.5))

            results.append({
                "carrier_code": carrier_code,
                "carrier_name": row.carrier_name,
                "total_shipments": tot,
                "on_time_count": on_time,
                "exceptions_count": exc_count,
                "avg_recovery_hours": round(avg_rec, 1),
            })

        return results

    async def get_root_cause_distribution_data(self) -> List[Dict[str, Any]]:
        """Calculates distribution of disruptions by exception type with associated financial damage."""
        stmt = (
            select(
                ShipmentException.exception_type,
                func.count(distinct(ShipmentException.id)).label("count"),
                func.coalesce(func.sum(ImpactAssessment.financial_impact), 0.0).label("total_loss"),
            )
            .outerjoin(ImpactAssessment, ShipmentException.id == ImpactAssessment.exception_id)
            .group_by(ShipmentException.exception_type)
            .order_by(func.count(distinct(ShipmentException.id)).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "exception_type": r.exception_type,
                "count": r.count,
                "total_loss": round(float(r.total_loss), 2),
            }
            for r in rows
        ]

    async def get_sla_compliance_data(self) -> Dict[str, Any]:
        """Calculates resolution SLA adherence metrics and duration averages."""
        stmt = select(
            func.count(ShipmentException.id).label("total_exceptions"),
            func.count(case((ShipmentException.is_sla_breached == True, 1), else_=None)).label("breached_count"),  # noqa: E712
            func.count(
                case(
                    (
                        (ShipmentException.status == ExceptionStatus.RESOLVED.value)
                        & (ShipmentException.resolved_at.is_not(None))
                        & (ShipmentException.sla_breach_at.is_not(None))
                        & (ShipmentException.resolved_at <= ShipmentException.sla_breach_at),
                        1,
                    ),
                    else_=None,
                )
            ).label("resolved_within_sla"),
            func.count(
                case(
                    (
                        (ShipmentException.severity == ExceptionSeverity.CRITICAL.value)
                        & (ShipmentException.is_sla_breached == False),  # noqa: E712
                        1,
                    ),
                    else_=None,
                )
            ).label("critical_adherent"),
            func.count(case((ShipmentException.severity == ExceptionSeverity.CRITICAL.value, 1), else_=None)).label("critical_total"),
        )
        row = (await self.session.execute(stmt)).one()
        return {
            "total_exceptions": row.total_exceptions,
            "breached_count": row.breached_count,
            "resolved_within_sla": row.resolved_within_sla,
            "critical_adherent": row.critical_adherent,
            "critical_total": row.critical_total,
        }

    async def get_financial_exposure_data(self) -> Dict[str, Any]:
        """Calculates financial exposure metrics from all impact assessments."""
        stmt = select(
            func.count(ImpactAssessment.id).label("assessments_count"),
            func.coalesce(func.sum(ImpactAssessment.financial_impact), 0.0).label("total_exposure"),
            func.coalesce(func.sum(ImpactAssessment.delay_cost), 0.0).label("total_delay"),
            func.coalesce(func.sum(ImpactAssessment.cargo_damage_cost), 0.0).label("total_cargo"),
            func.coalesce(func.sum(ImpactAssessment.contractual_penalty_cost), 0.0).label("total_contract"),
            func.coalesce(
                func.sum(case((ImpactAssessment.is_auto_escalated == True, ImpactAssessment.financial_impact), else_=0.0)),  # noqa: E712
                0.0,
            ).label("auto_escalated_exposure"),
        )
        row = (await self.session.execute(stmt)).one()
        return {
            "assessments_count": row.assessments_count,
            "total_exposure_usd": round(float(row.total_exposure), 2),
            "delay_costs_usd": round(float(row.total_delay), 2),
            "cargo_damage_usd": round(float(row.total_cargo), 2),
            "contractual_penalties_usd": round(float(row.total_contract), 2),
            "auto_escalated_exposure_usd": round(float(row.auto_escalated_exposure), 2),
        }

    async def get_exceptions_for_export(self) -> List[Tuple[ShipmentException, Shipment]]:
        """Fetches exception records joined with shipments for CSV reporting."""
        stmt = (
            select(ShipmentException, Shipment)
            .join(Shipment, ShipmentException.shipment_id == Shipment.id)
            .order_by(ShipmentException.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.all())
