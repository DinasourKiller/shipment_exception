"""Analytics, Reporting & Trend Engine API Endpoints.

Provides REST endpoints for carrier scorecards, root-cause Pareto distributions,
SLA compliance percentages, cumulative financial exposure, and CSV exports.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.modules.analytics.schemas import (
    CarrierPerformanceResponse,
    FinancialExposureSummary,
    RootCauseDistributionResponse,
    SLAComplianceMetric,
)
from app.modules.analytics.service import AnalyticsService
from app.modules.authentication.models import User

router = APIRouter()


def get_analytics_service(session: AsyncSession = Depends(get_db_session)) -> AnalyticsService:
    """Dependency producing initialized AnalyticsService."""
    return AnalyticsService(session=session)


@router.get(
    "/carrier-performance",
    response_model=ApiResponse[CarrierPerformanceResponse],
    status_code=status.HTTP_200_OK,
    summary="Carrier performance scorecards",
    description="Calculates multi-dimensional performance scores, exception rates, and rating grades for all carriers.",
)
async def get_carrier_scorecards(
    service: AnalyticsService = Depends(get_analytics_service),
    _: User = Depends(require_permissions("reporting:read")),
) -> ApiResponse[CarrierPerformanceResponse]:
    scorecards = await service.get_carrier_performance()
    return ApiResponse(
        success=True,
        data=scorecards,
        message=f"Retrieved performance metrics for {scorecards.total_carriers} carriers.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/root-cause-distribution",
    response_model=ApiResponse[RootCauseDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Root cause Pareto distribution",
    description="Retrieves disruption frequency breakdown and financial loss by exception category.",
)
async def get_root_cause_distribution(
    service: AnalyticsService = Depends(get_analytics_service),
    _: User = Depends(require_permissions("reporting:read")),
) -> ApiResponse[RootCauseDistributionResponse]:
    distribution = await service.get_root_cause_distribution()
    return ApiResponse(
        success=True,
        data=distribution,
        message="Root cause Pareto distribution calculated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/sla-compliance",
    response_model=ApiResponse[SLAComplianceMetric],
    status_code=status.HTTP_200_OK,
    summary="Operational SLA resolution compliance",
    description="Retrieves SLA compliance percentages and breach rates across all operational disruptions.",
)
async def get_sla_compliance(
    service: AnalyticsService = Depends(get_analytics_service),
    _: User = Depends(require_permissions("reporting:read")),
) -> ApiResponse[SLAComplianceMetric]:
    metrics = await service.get_sla_compliance()
    return ApiResponse(
        success=True,
        data=metrics,
        message="SLA compliance metrics calculated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/financial-exposure",
    response_model=ApiResponse[FinancialExposureSummary],
    status_code=status.HTTP_200_OK,
    summary="Cumulative financial damage summary",
    description="Retrieves aggregated monetary loss, delay charges, cargo spoilage, and contractual fines.",
)
async def get_financial_exposure(
    service: AnalyticsService = Depends(get_analytics_service),
    _: User = Depends(require_permissions("reporting:read")),
) -> ApiResponse[FinancialExposureSummary]:
    exposure = await service.get_financial_exposure()
    return ApiResponse(
        success=True,
        data=exposure,
        message="Financial exposure summary calculated successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/export/exceptions-csv",
    status_code=status.HTTP_200_OK,
    summary="Export exceptions report as CSV",
    description="Streams a formatted CSV download containing all exceptions joined with shipment and SLA data.",
)
async def export_exceptions_csv(
    service: AnalyticsService = Depends(get_analytics_service),
    _: User = Depends(require_permissions("reporting:read")),
) -> Response:
    csv_data = await service.generate_exceptions_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=operational_exceptions_report.csv",
        },
    )
