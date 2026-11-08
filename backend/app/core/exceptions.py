class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
class AuthenticationError(Exception):
    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(message)
class AuthorizationError(Exception):
    def __init__(self, message: str = "Insufficient permissions"):
        self.message = message
        super().__init__(message)
class NotFoundError(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(message)
class ConflictError(Exception):
    def __init__(self, message: str = "Resource conflict"):
        self.message = message
        super().__init__(message)
class RateLimitError(Exception):
    def __init__(self, message: str = "Rate limit exceeded"):
        self.message = message
        super().__init__(message)
class ConfigurationError(Exception):
    def __init__(self, message: str = "Configuration error"):
        self.message = message
        super().__init__(message)
