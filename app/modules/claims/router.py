"""Carrier Claims & SLA Penalty Settlement API Router."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import ApiResponse
from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.database.connection import get_db_session
from app.dependencies import get_current_user
from app.modules.authentication.models import User
from app.modules.claims.schemas import (
    AutoClaimFromExceptionRequest,
    CarrierClaimResponse,
    ClaimCreateRequest,
    ClaimDisputeRequest,
    ClaimRejectRequest,
    ClaimSettleRequest,
    ClaimsSummaryResponse,
    PaginatedClaimsResponse,
)
from app.modules.claims.service import ClaimService

logger = get_logger("control_tower.claims.router")

router = APIRouter(prefix="/claims", tags=["Claims & SLA Penalties"])


def get_claim_service(session: AsyncSession = Depends(get_db_session)) -> ClaimService:
    return ClaimService(session=session)


@router.post(
    "",
    response_model=ApiResponse[CarrierClaimResponse],
    status_code=status.HTTP_201_CREATED,
    summary="File a new carrier claim or contractual penalty",
)
async def create_claim(
    request: ClaimCreateRequest,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(
        require_roles("System Administrator", "Operations Manager", "Control Tower Analyst", "Dispatcher / Planner")
    ),
) -> ApiResponse[CarrierClaimResponse]:
    """Manually register a financial claim or contractual penalty against a carrier."""
    user_role = current_user.roles[0].name if current_user.roles else "Operator"
    data = await service.create_claim(
        request=request,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=user_role,
    )
    return ApiResponse(
        success=True,
        data=data,
        message=f"Claim {data.claim_number} filed against {data.carrier_code}.",
    )


@router.post(
    "/auto-from-exception",
    response_model=ApiResponse[CarrierClaimResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Automatically derive a claim from an operational exception",
)
async def auto_create_claim_from_exception(
    request: AutoClaimFromExceptionRequest,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(
        require_roles("System Administrator", "Operations Manager", "Control Tower Analyst")
    ),
) -> ApiResponse[CarrierClaimResponse]:
    """Derive an automated carrier penalty based on calculated impact and SLA breach duration."""
    user_role = current_user.roles[0].name if current_user.roles else "Operator"
    data = await service.auto_create_from_exception(
        request=request,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=user_role,
    )
    return ApiResponse(
        success=True,
        data=data,
        message=f"Automated claim {data.claim_number} generated from exception.",
    )


@router.get(
    "/summary",
    response_model=ApiResponse[ClaimsSummaryResponse],
    summary="Get executive claims and recovery KPI totals",
)
async def get_claims_summary(
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ClaimsSummaryResponse]:
    """Retrieve financial aggregations of total claims filed, disputed amounts, and settled recoveries."""
    data = await service.get_summary()
    return ApiResponse(
        success=True,
        data=data,
        message="Claims financial summary retrieved successfully.",
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedClaimsResponse],
    summary="List carrier claims and penalties",
)
async def list_claims(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    carrier_code: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    claim_type: Optional[str] = Query(default=None),
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PaginatedClaimsResponse]:
    """Search and filter claims by carrier, status, and classification."""
    data = await service.list_claims(
        page=page,
        page_size=page_size,
        carrier_code=carrier_code,
        status=status,
        claim_type=claim_type,
    )
    return ApiResponse(
        success=True,
        data=data,
        message="Claims retrieved successfully.",
    )


@router.get(
    "/export/csv",
    summary="Export claims ledger to RFC-4180 CSV",
)
async def export_claims_csv(
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(
        require_roles("System Administrator", "Operations Manager", "Control Tower Analyst", "Compliance Auditor")
    ),
) -> Response:
    """Download full claims reconciliation ledger for corporate accounts payable / ERP."""
    csv_content = await service.export_claims_csv()
    filename = f"carrier_claims_ledger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get(
    "/{claim_id}",
    response_model=ApiResponse[CarrierClaimResponse],
    summary="Get claim details and dispute timeline",
)
async def get_claim(
    claim_id: uuid.UUID,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[CarrierClaimResponse]:
    """Retrieve full claim record and chronological audit dispute events."""
    data = await service.get_claim(claim_id)
    return ApiResponse(
        success=True,
        data=data,
        message="Claim retrieved successfully.",
    )


@router.post(
    "/{claim_id}/dispute",
    response_model=ApiResponse[CarrierClaimResponse],
    summary="Carrier dispute or counter-offer submission",
)
async def dispute_claim(
    claim_id: uuid.UUID,
    request: ClaimDisputeRequest,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(
        require_roles("System Administrator", "Operations Manager", "Carrier")
    ),
) -> ApiResponse[CarrierClaimResponse]:
    """Allow a carrier to challenge claim justification and submit an optional counter-offer amount."""
    user_role = current_user.roles[0].name if current_user.roles else "Carrier"
    data = await service.submit_dispute(
        claim_id=claim_id,
        request=request,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=user_role,
    )
    return ApiResponse(
        success=True,
        data=data,
        message="Claim dispute recorded. Status updated to CARRIER_DISPUTED.",
    )


@router.post(
    "/{claim_id}/settle",
    response_model=ApiResponse[CarrierClaimResponse],
    summary="Finalize agreed claim settlement",
)
async def settle_claim(
    claim_id: uuid.UUID,
    request: ClaimSettleRequest,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(
        require_roles("System Administrator", "Operations Manager")
    ),
) -> ApiResponse[CarrierClaimResponse]:
    """Authorize final payout or invoice offset settlement."""
    user_role = current_user.roles[0].name if current_user.roles else "Manager"
    data = await service.settle_claim(
        claim_id=claim_id,
        request=request,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=user_role,
    )
    return ApiResponse(
        success=True,
        data=data,
        message=f"Claim {data.claim_number} settled for ${data.settled_amount_usd:,.2f}.",
    )


@router.post(
    "/{claim_id}/reject",
    response_model=ApiResponse[CarrierClaimResponse],
    summary="Reject carrier claim",
)
async def reject_claim(
    claim_id: uuid.UUID,
    request: ClaimRejectRequest,
    service: ClaimService = Depends(get_claim_service),
    current_user: User = Depends(
        require_roles("System Administrator", "Operations Manager")
    ),
) -> ApiResponse[CarrierClaimResponse]:
    """Dismiss and close a claim."""
    user_role = current_user.roles[0].name if current_user.roles else "Manager"
    data = await service.reject_claim(
        claim_id=claim_id,
        request=request,
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=user_role,
    )
    return ApiResponse(
        success=True,
        data=data,
        message="Claim marked as REJECTED.",
    )

