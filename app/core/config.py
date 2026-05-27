from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool) -> bool:
	if value is None:
		return default
	return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
	openai_api_key: str | None
	openai_model: str
	excel_file_path: str
	service_api_key: str | None
	enforce_service_api_key: bool
	rate_limit_enabled: bool
	rate_limit_requests_per_window: int
	rate_limit_window_seconds: int
	log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	project_root = Path(__file__).resolve().parents[2]
	load_dotenv(project_root / ".env")
	excel_name = os.getenv("EXCEL_FILE_PATH", "ReporteMedidores.xlsx")

	return Settings(
		openai_api_key=os.getenv("OPENAI_API_KEY"),
		openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
		excel_file_path=str((project_root / excel_name).resolve()),
		service_api_key=os.getenv("SERVICE_API_KEY"),
		enforce_service_api_key=_as_bool(os.getenv("ENFORCE_SERVICE_API_KEY"), False),
		rate_limit_enabled=_as_bool(os.getenv("RATE_LIMIT_ENABLED"), True),
		rate_limit_requests_per_window=int(os.getenv("RATE_LIMIT_REQUESTS_PER_WINDOW", "60")),
		rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
		log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
	)

