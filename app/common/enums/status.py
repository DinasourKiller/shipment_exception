"""Global enterprise domain enumerations."""

from enum import Enum


class EnvironmentType(str, Enum):
    """Runtime environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class ShipmentStatus(str, Enum):
    """Shipment operational statuses."""
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    EXCEPTION = "EXCEPTION"
    RECOVERED = "RECOVERED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class ExceptionSeverity(str, Enum):
    """Exception business impact severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExceptionStatus(str, Enum):
    """Exception lifecycle status."""
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    RECOVERED = "RECOVERED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class RecoveryOptionType(str, Enum):
    """Approved recovery strategies."""
    REROUTE = "RE_ROUTE"
    ALTERNATE_CARRIER = "ALTERNATE_CARRIER"
    EXPEDITE = "EXPEDITE"
    SPLIT = "SPLIT"


class UserRole(str, Enum):
    """Enterprise application roles."""
    SYSTEM_ADMINISTRATOR = "System Administrator"
    CONTROL_TOWER_ANALYST = "Control Tower Analyst"
    DISPATCHER_PLANNER = "Dispatcher / Planner"
    OPERATIONS_MANAGER = "Operations Manager"
    CARRIER = "Carrier"
    WAREHOUSE_SUPERVISOR = "Warehouse Supervisor"
    CUSTOMER_SERVICE = "Customer Service"
