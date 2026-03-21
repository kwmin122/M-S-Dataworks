"""Shared rate limiter instance — importable from routers without circular deps."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],  # Global default: 60 req/min per IP
)
