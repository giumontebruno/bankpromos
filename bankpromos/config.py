import os
from pathlib import Path
from typing import Optional


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    val = get_env(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    val = get_env(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


class Config:
    DEFAULT_DB_PATH = "/app/data/bankpromos.db"
    LOCAL_DB_PATH = "data/bankpromos.db"

    def __init__(self):
        self.port: int = get_env_int("PORT", 8000)
        self.host: str = "0.0.0.0"

        env_db = os.environ.get("BANKPROMOS_DB_PATH")
        if env_db:
            self.db_path = env_db
        elif os.path.exists(self.LOCAL_DB_PATH):
            self.db_path = self.LOCAL_DB_PATH
        else:
            self.db_path = self.DEFAULT_DB_PATH

        self.cache_hours: int = get_env_int("BANKPROMOS_CACHE_HOURS", 12)
        self.debug: bool = get_env_bool("BANKPROMOS_DEBUG", False)
        self.disable_live_scraping: bool = get_env_bool("BANKPROMOS_DISABLE_LIVE_SCRAPING", False)

        self.cors_origins: list = []
        cors_env = get_env("BANKPROMOS_CORS_ORIGINS")
        if cors_env:
            self.cors_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
        else:
            self.cors_origins = ["*"]

    def ensure_db_dir(self) -> None:
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def get_database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    def validate_db_exists(self) -> dict:
        db_file = Path(self.db_path)
        exists = db_file.exists()
        size = db_file.stat().st_size if exists else 0
        return {
            "db_path": self.db_path,
            "exists": exists,
            "size_bytes": size,
        }


config = Config()