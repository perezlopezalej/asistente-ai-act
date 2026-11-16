# Asistente AI Act

## Propósito
Asistente RAG en español sobre el Reglamento (UE) 2024/1689 (AI Act). Responde citando el artículo exacto, dice "no lo sé" si no hay contexto relevante y avisa de que no es asesoramiento legal.

## Stack
Python 3.12 + FastAPI (backend), Neon (Postgres + pgvector; psycopg 3), Groq (generación), embeddings con Cloudflare Workers AI (`@cf/baai/bge-m3`, 1024 dim), Next.js (frontend). Gestión de dependencias con uv.

## Comandos (desde `backend/`)
- `uv sync` — instalar dependencias
- `uv run uvicorn app.main:app --reload` — arrancar la API
- `uv run pytest` — tests
- `uv run ruff check .` — lint (y `uv run ruff format .` para formatear)
- `uv run pip-audit` — auditoría de dependencias

## Convenciones
- Commits convencionales (`feat:`, `fix:`, `chore:`, `docs:`...).
- Una rama por fase o funcionalidad.
- Tests en lo crítico.

## Reglas
- No leer ni mostrar secretos (`.env`, claves).
- Toda respuesta lleva cita de artículo verificada contra los fragmentos recuperados.
- El disclaimer legal debe ser siempre visible.
