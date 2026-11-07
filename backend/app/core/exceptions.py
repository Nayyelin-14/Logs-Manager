"""
Custom Exceptions

Application-specific exceptions.
"""

class ValidationError(Exception):
    """Raised when input validation fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(message)


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    def __init__(self, message: str = "Insufficient permissions"):
        self.message = message
        super().__init__(message)


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    """Raised when a resource conflict occurs."""
    def __init__(self, message: str = "Resource conflict"):
        self.message = message
        super().__init__(message)


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str = "Rate limit exceeded"):
        self.message = message
        super().__init__(message)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    def __init__(self, message: str = "Configuration error"):
        self.message = message
        super().__init__(message)