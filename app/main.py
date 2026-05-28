from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.analysis import router as analysis_router
from app.core.config import get_settings
from app.core.logging import configure_logging


settings = get_settings()
configure_logging(settings.log_level)

if settings.enforce_service_api_key and not settings.service_api_key:
	raise RuntimeError("ENFORCE_SERVICE_API_KEY is enabled but SERVICE_API_KEY is missing.")


app = FastAPI(
	title="Electrical AI Microservice",
	version="1.0.0",
	description="Microservicio para analisis de consumo electrico.",
)


@app.get("/health", tags=["health"])
def health_check() -> JSONResponse:
	checks = {
		"openai_api_key_configured": bool(settings.openai_api_key),
		"service_api_key_policy_ok": (not settings.enforce_service_api_key) or bool(settings.service_api_key),
	}
	ready = all(checks.values())
	return JSONResponse(
		status_code=200 if ready else 503,
		content={
			"status": "ok" if ready else "degraded",
			"checks": checks,
		},
	)


app.include_router(analysis_router)
