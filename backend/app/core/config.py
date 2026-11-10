"""Configuration centralisée (12-factor) : toutes les valeurs viennent de l'environnement."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BIBLIO_", extra="ignore")

    app_name: str = "BiblioTrack"
    environment: str = "dev"
    database_url: str = "sqlite:///./biblio.db"

    # Sécurité / JWT
    jwt_secret: str = Field(default="change-me-in-production-please-32b+", min_length=32)
    jwt_algorithm: str = "HS256"
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)
    access_token_minutes: int = 60
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # Règles métier (paramétrables, valeurs par défaut documentées dans docs/REGLES_METIER.md)
    max_active_loans: int = 5
    loan_duration_days: int = 21
    renewal_days: int = 14
    max_renewals: int = 1
    late_fee_per_day: str = "0.50"
    late_fee_cap: str = "20.00"
    lost_item_fee: str = "30.00"
    max_active_reservations: int = 3
    reservation_hold_days: int = 3

    # Intégration externe (Open Library)
    openlibrary_base_url: str = "https://openlibrary.org"
    openlibrary_timeout_seconds: float = 3.0

    # Initialisation : schéma + maintenance au démarrage de l'application (désactivé en conteneur
    # multi-workers, où `python -m app.prestart` s'en charge une seule fois).
    init_on_startup: bool = True
    # Données de démonstration au démarrage
    seed_on_startup: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
