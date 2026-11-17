"""Construye el embedder real a partir de la configuración (.env)."""

from app.config import settings
from app.embeddings.cloudflare import CloudflareEmbedder


def crear_embedder(max_retries: int = 5) -> CloudflareEmbedder:
    """`max_retries` bajo (p. ej. 2) para la API: no bloquear una petición ~30 s."""
    if not settings.cloudflare_account_id or not settings.cloudflare_api_token:
        raise SystemExit(
            "Faltan CLOUDFLARE_ACCOUNT_ID y/o CLOUDFLARE_API_TOKEN (rellénalas en el .env "
            "de la raíz del repo)."
        )
    return CloudflareEmbedder(
        settings.cloudflare_account_id,
        settings.cloudflare_api_token,
        settings.embedding_model,
        max_retries=max_retries,
    )
