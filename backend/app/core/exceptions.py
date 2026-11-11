class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# DB-API/driver errors that specifically mean the connection went away. The
# type names cover asyncpg's connection errors without importing asyncpg.
_CONNECTION_LOST_TYPE_NAMES = frozenset(
    {
        "ClientConnectionResetError",
        "ConnectionClosedError",
        "ConnectionDoesNotExistError",
    }
)

# Text fallbacks for drivers that only expose a message (for example asyncpg's
# "connection was closed in the middle of operation"). These are matched only
# on the exception chain of a DBAPIError, never on arbitrary failures.
_CONNECTION_LOST_MARKERS = (
    "connection reset",
    "connection was closed in the middle of operation",
    "connection is closed",
    "connection has been closed",
    "connection already closed",
    "server closed the connection unexpectedly",
    "connection lost",
    "could not connect",
    "connection refused",
    "terminating connection due to administrator command",
)


def _exception_chain(exc: BaseException):
    """Yield exc and its wrapped/caused exceptions (SQLAlchemy uses ``orig``)."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for attribute in ("orig", "__cause__", "__context__"):
            nested = getattr(current, attribute, None)
            if isinstance(nested, BaseException):
                stack.append(nested)


def _is_connection_loss(exc: BaseException) -> bool:
    """Narrow check for a wrapped DNS failure or dropped/reset connection."""
    import socket

    chain = list(_exception_chain(exc))
    for cause in chain:
        if isinstance(cause, socket.gaierror):
            return True
        if isinstance(cause, ConnectionError):
            return True
        if type(cause).__name__ in _CONNECTION_LOST_TYPE_NAMES:
            return True

    text = " ".join(str(cause).lower() for cause in chain)
    return any(marker in text for marker in _CONNECTION_LOST_MARKERS)


def is_transient_db_error(exc: BaseException) -> bool:
    """Return True when a database failure is likely to succeed on retry.

    Used by the native Syslog listener, the HTTPS Syslog route and API-key
    authentication to decide between "retry / 503" and "permanent failure".
    Validation, integrity and query errors are never transient; wrapped
    connection resets and DNS resolution failures are.
    """
    if isinstance(exc, ValidationError):
        return False

    import socket
    from asyncio import TimeoutError as AsyncTimeoutError

    from sqlalchemy.exc import (
        DBAPIError,
        DisconnectionError,
        InterfaceError,
        OperationalError,
        TimeoutError as SATimeoutError,
    )

    if isinstance(
        exc,
        (
            OperationalError,
            InterfaceError,
            DisconnectionError,
            SATimeoutError,
            AsyncTimeoutError,
            TimeoutError,
            ConnectionError,
            socket.gaierror,
        ),
    ):
        return True

    if isinstance(exc, DBAPIError):
        if getattr(exc, "connection_invalidated", False):
            return True
        return _is_connection_loss(exc)

    return False
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
