"""Audit Logging & Regulatory Compliance REST API Endpoints."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_correlation_id
from app.core.permissions import require_permissions
from app.database.connection import get_db_session
from app.modules.audit.schemas import (
    ChainIntegrityResponse,
    PaginatedAuditLogsResponse,
)
from app.modules.audit.service import AuditService
from app.modules.authentication.models import User

router = APIRouter()


def get_audit_service(session: AsyncSession = Depends(get_db_session)) -> AuditService:
    """Dependency producing initialized AuditService."""
    return AuditService(session=session)


@router.get(
    "/logs",
    response_model=ApiResponse[PaginatedAuditLogsResponse],
    status_code=status.HTTP_200_OK,
    summary="List paginated forensic audit records",
    description="Returns cryptographically hash-chained audit logs with optional filtering by action, resource, or actor.",
)
async def list_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    action: Optional[str] = Query(None, description="Filter by action category"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    actor_email: Optional[str] = Query(None, description="Filter by actor email"),
    from_date: Optional[datetime] = Query(None, description="Filter start date"),
    to_date: Optional[datetime] = Query(None, description="Filter end date"),
    service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(require_permissions("users:read")),
) -> ApiResponse[PaginatedAuditLogsResponse]:
    result = await service.list_logs(
        page=page,
        page_size=page_size,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_email=actor_email,
        from_date=from_date,
        to_date=to_date,
    )
    return ApiResponse(
        success=True,
        data=result,
        message="Audit logs retrieved successfully.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/verify",
    response_model=ApiResponse[ChainIntegrityResponse],
    status_code=status.HTTP_200_OK,
    summary="Verify cryptographic audit chain integrity",
    description="Verifies the SHA-256 hash linkage from the genesis block to detect any database tampering.",
)
async def verify_chain(
    service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(require_permissions("users:read")),
) -> ApiResponse[ChainIntegrityResponse]:
    integrity = await service.verify_chain_integrity()
    return ApiResponse(
        success=True,
        data=integrity,
        message="Cryptographic integrity verification completed.",
        correlation_id=get_correlation_id(),
    )


@router.get(
    "/export/compliance-csv",
    status_code=status.HTTP_200_OK,
    summary="Export forensic compliance audit trail as CSV",
    description="Downloads signed, auditor-ready CSV file formatted with SHA-256 signatures for regulatory submission.",
)
async def export_audit_csv(
    service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(require_permissions("users:read")),
) -> Response:
    csv_data = await service.export_compliance_csv()
    filename = f"regulatory_audit_trail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
