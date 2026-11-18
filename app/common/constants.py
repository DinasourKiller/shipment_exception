"""Global constants for the Control Tower application."""

CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"

# Pagination defaults
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Security constants
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
CSRF_TOKEN_HEADER = "X-CSRF-Token"

# Datetime format standard
ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
