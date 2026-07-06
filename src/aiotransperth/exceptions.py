"""Exceptions raised by aiotransperth."""


class TransperthError(Exception):
    """Base for all aiotransperth errors."""


class RateLimitError(TransperthError):
    """Transperth returned HTTP 429; cooldown is sticky (>60 s)."""


class AuthError(TransperthError):
    """A CSRF token could not be obtained or was rejected."""


class NetworkError(TransperthError):
    """The HTTP request itself failed (DNS, timeout, connection)."""


class InvalidStopError(TransperthError):
    """The stop code / station name is not known to Transperth."""
