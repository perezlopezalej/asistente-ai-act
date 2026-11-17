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
    # Calibrado en la fase 4b: con 0.46 hay 0 rechazos injustos y 9 aceptaciones, igual que con
    # 0.48 pero sin rechazar g-022; g-038 está en 0.459, así que 0.45 deja margen. La barrera 1
    # solo filtra lo evidente: las distribuciones se solapan (con respuesta 0.464-0.806,
    # sin respuesta 0.257-0.605).
    umbral_similitud: float = 0.45
    k_articulos: int = 5
    k_considerandos: int = 2
    presupuesto_contexto_caracteres: int = 10000


settings = Settings()
