from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# El .env vive en la raíz del repo (ver README); ruta absoluta para que funcione
# se ejecute desde backend/ o desde cualquier otro directorio.
RAIZ = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")

    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    embedding_model: str = "@cf/baai/bge-m3"
    database_url: str | None = None

    # Generación (Cloudflare Workers AI, misma cuenta y token que los embeddings)
    llm_model: str = "@cf/openai/gpt-oss-120b"
    llm_max_tokens: int = 3000
    llm_reasoning_effort: str = "low"
    llm_temperature: float = 0.1

    # Recuperación y abstención
    umbral_similitud: float = 0.50  # provisional: se calibra en la fase 4
    k_articulos: int = 5
    k_considerandos: int = 2
    presupuesto_contexto_caracteres: int = 10000


settings = Settings()
