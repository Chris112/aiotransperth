from aiotransperth.exceptions import (
    AuthError,
    InvalidStopError,
    NetworkError,
    RateLimitError,
    TransperthError,
)


def test_hierarchy() -> None:
    for exc in (RateLimitError, AuthError, NetworkError, InvalidStopError):
        assert issubclass(exc, TransperthError)
    assert issubclass(TransperthError, Exception)
