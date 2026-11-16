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
    groq_api_key: str | None = None


settings = Settings()
