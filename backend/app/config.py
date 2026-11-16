from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str | None = None
    supabase_service_key: str | None = None
    groq_api_key: str | None = None
    embedding_model: str | None = None


settings = Settings()
