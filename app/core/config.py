from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, field_validator, AnyHttpUrl
from typing import Optional, Any, List


class Settings(BaseSettings):
    # --- Project Settings ---
    PROJECT_NAME: str = "Sono"
    API_V1_STR: str = "/api/v1"
    API_PORT: str = "8000"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # --- Security Settings ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_SECRET_KEY: str
    REFRESH_TOKEN_ALGORITHM: str = "HS256"
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # --- Database Settings ---
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    DB_EXPOSE_PORT: str = "5432"
    DATABASE_URL: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v

        return PostgresDsn.build(
            scheme="postgresql",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_HOST"),
            port=int(info.data.get("POSTGRES_PORT", 5432)),
            path=info.data.get("POSTGRES_DB") or "",
        )

    # --- PGAdmin Settings ---
    PGADMIN_DEFAULT_EMAIL: str = ""
    PGADMIN_DEFAULT_PASSWORD: str = ""

    # --- MinIO Storage Settings ---
    MINIO_ENDPOINT: str
    MINIO_PUBLIC_URL: str = ""
    MINIO_ACCESS_KEY: str

    @property
    def minio_public_base(self) -> str:
        if self.MINIO_PUBLIC_URL:
            return self.MINIO_PUBLIC_URL.rstrip("/")
        return f"http://{self.MINIO_ENDPOINT}"

    MINIO_SECRET_KEY: str
    MINIO_USE_HTTPS: bool = False
    MINIO_BUCKET_NAME: str = ""
    MINIO_ROOT_USER: str = ""
    MINIO_ROOT_PASSWORD: str = ""
    MINIO_AGPL_LICENSE: str = "accept"

    # --- SMTP Settings ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    FRONTEND_URL: str = ""

    # --- CORS Settings ---
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # --- Kworb Scraper Database Settings ---
    KWORB_DB_HOST: str = "localhost"
    KWORB_DB_PORT: str = "5433"
    KWORB_DB_USER: str = "kworb_scraper"
    KWORB_DB_PASSWORD: str = ""
    KWORB_DB_NAME: str = "kworb_data"
    KWORB_DATABASE_URL: Optional[PostgresDsn] = None

    @field_validator("KWORB_DATABASE_URL", mode="before")
    @classmethod
    def assemble_kworb_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v

        password = info.data.get("KWORB_DB_PASSWORD")
        if not password:
            return None

        return PostgresDsn.build(
            scheme="postgresql",
            username=info.data.get("KWORB_DB_USER"),
            password=password,
            host=info.data.get("KWORB_DB_HOST"),
            port=int(info.data.get("KWORB_DB_PORT", 5433)),
            path=info.data.get("KWORB_DB_NAME") or "",
        )

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")


settings = Settings()
