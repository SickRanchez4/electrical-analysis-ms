from collections import defaultdict, deque
from threading import Lock
import time

from fastapi import Header, HTTPException, Request

from app.core.config import get_settings


_rate_limit_state: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()


def clear_rate_limit_state() -> None:
	with _rate_limit_lock:
		_rate_limit_state.clear()


def verify_service_api_key(x_api_key: str | None = Header(default=None)) -> None:
	settings = get_settings()
	if settings.enforce_service_api_key and not settings.service_api_key:
		raise HTTPException(status_code=503, detail="Service API key is required but not configured.")

	if not settings.service_api_key:
		return

	if x_api_key != settings.service_api_key:
		raise HTTPException(status_code=401, detail="Unauthorized")


def enforce_rate_limit(request: Request, x_api_key: str | None = Header(default=None)) -> None:
	settings = get_settings()
	if not settings.rate_limit_enabled:
		return

	limit = settings.rate_limit_requests_per_window
	window_seconds = settings.rate_limit_window_seconds
	if limit <= 0 or window_seconds <= 0:
		return

	client_host = request.client.host if request.client else "unknown"
	identifier = f"api_key:{x_api_key}" if x_api_key else f"ip:{client_host}"
	now = time.time()
	cutoff = now - window_seconds

	with _rate_limit_lock:
		hits = _rate_limit_state[identifier]
		while hits and hits[0] < cutoff:
			hits.popleft()

		if len(hits) >= limit:
			raise HTTPException(status_code=429, detail="Too many requests")

		hits.append(now)

