"""Construye el LLM real a partir de la configuración (.env)."""

from app.config import settings
from app.llm.base import LLMError
from app.llm.cloudflare import CloudflareLLM


def crear_llm() -> CloudflareLLM:
    if not settings.cloudflare_account_id or not settings.cloudflare_api_token:
        raise LLMError(
            "Faltan CLOUDFLARE_ACCOUNT_ID y/o CLOUDFLARE_API_TOKEN (rellénalas en el .env "
            "de la raíz del repo)."
        )
    return CloudflareLLM(
        settings.cloudflare_account_id,
        settings.cloudflare_api_token,
        settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        reasoning_effort=settings.llm_reasoning_effort,
    )
