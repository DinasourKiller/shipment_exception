"""Standardized API response wrappers."""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """Standard success response wrapper."""

    success: bool = Field(default=True, description="Indicates operation success")
    data: Optional[DataT] = Field(default=None, description="Response payload")
    message: Optional[str] = Field(default=None, description="Optional informational message")
    correlation_id: Optional[str] = Field(default=None, description="Correlation identifier")


class PaginationMetadata(BaseModel):
    """Pagination metadata model."""

    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total items matching query")
    total_pages: int = Field(..., description="Total pages")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Standard paginated response wrapper."""

    success: bool = Field(default=True, description="Indicates operation success")
    data: List[DataT] = Field(default_factory=list, description="Page items")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")
    correlation_id: Optional[str] = Field(default=None, description="Correlation identifier")


class HealthStatus(BaseModel):
    """Health check status payload."""

    status: str = Field(..., description="Service status: healthy, degraded, or unhealthy")
    timestamp: str = Field(..., description="Current server ISO timestamp")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="SemVer version")
    environment: str = Field(..., description="Deployment environment")
    components: Optional[dict[str, Any]] = Field(default=None, description="Component-level health details")
