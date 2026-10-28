from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Application
    app_name: str = "AletheiaOS"
    app_version: str = "1.0.0"
    app_description: str = (
        "AletheiaOS — a neuro-symbolic cognitive architecture integrating episodic "
        "memory, semantic reasoning, formal constraint solving (Z3), SHACL validation, "
        "RDF knowledge graphs, and goal-directed planning."
    )
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = f"sqlite:///{BASE_DIR}/aletheia.db"

    # Ontology / RDF
    ontology_path: str = str(BASE_DIR / "ontology" / "aletheia.owl")
    shapes_path: str = str(BASE_DIR / "ontology" / "shapes.ttl")
    rdf_store_path: str = str(BASE_DIR / "data" / "rdf_store.ttl")

    # CORS
    cors_origins: list[str] = ["*"]

    # Pagination defaults
    default_page_limit: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
