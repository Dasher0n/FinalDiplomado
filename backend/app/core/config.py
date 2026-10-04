"""Configuracion central resuelta desde variables de entorno y .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Sommelier de juegos"
    environment: Literal["dev", "test", "prod"] = "dev"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:4200", "http://127.0.0.1:4200"]
    )
    database_url: str = "sqlite+aiosqlite:///./data/sommelier.db"

    openai_api_key: SecretStr = SecretStr("")
    llm_enabled: bool = True
    llm_model: str = "gpt-5.1"
    llm_model_fast: str = "gpt-5.1"
    llm_model_web: str = "gpt-5.1"
    llm_temperature: float = 0.2
    llm_max_plan_steps: int = 8
    critic_max_retries: int = 1
    web_search_enabled: bool = True

    fuzzy_umbral_directo: float = 90
    fuzzy_umbral_ambiguo: float = 75
    users_rated_min: int = 1000
    artefactos_dir: Path = Path("../artefactos")
    bgp_sitename: str = ""
    demo_user_email: str = "demo@sommelier.local"

    # Usuarios y sesión: las claves y el secreto vienen del entorno y nunca se registran.
    jwt_secret: SecretStr = SecretStr("")
    jwt_horas: int = 12
    clave_usuario_cafe: SecretStr = SecretStr("")
    clave_usuario_coleccionista: SecretStr = SecretStr("")

    @field_validator("jwt_horas", mode="before")
    @classmethod
    def horas_por_defecto(cls, value: object) -> object:
        return 12 if isinstance(value, str) and not value.strip() else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key.get_secret_value().strip())

    @property
    def llm_active(self) -> bool:
        return self.llm_enabled and self.has_openai_key

    @property
    def web_search_active(self) -> bool:
        return self.web_search_enabled and self.llm_active


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
