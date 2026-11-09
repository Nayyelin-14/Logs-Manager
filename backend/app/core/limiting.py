"""Shared in-process rate limiter.

Kept in its own module so route modules can decorate handlers without
importing ``app.main`` (which would create a circular import).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
