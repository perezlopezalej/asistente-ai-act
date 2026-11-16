# Asistente AI Act

Asistente RAG en español sobre el Reglamento (UE) 2024/1689 (AI Act). Responde citando el artículo exacto y dice "no lo sé" cuando no hay contexto relevante.

> **Aviso:** esto no es asesoramiento legal. Consulta a un profesional cualificado.

## Stack
Python 3.12, FastAPI, Supabase (pgvector), Groq, embeddings multilingües, Next.js.

## Arranque en local
```bash
cp .env.example .env     # rellena tus claves
cd backend
uv sync
uv run uvicorn app.main:app --reload
# http://127.0.0.1:8000/health
```

## Datos
El texto oficial se descarga a mano (no se versiona `data/raw/`):
1. Abre la versión ES del Reglamento (UE) 2024/1689 en EUR-Lex (CELEX `32024R1689`) y guarda la página como HTML en `data/raw/CELEX_32024R1689_ES_TXT.html`.
2. Desde `backend/`: `uv run python scripts/ingest.py`.

Genera `data/processed/chunks.jsonl` (un fragmento por línea, versionado): un fragmento por apartado de artículo (art. 3: por definición), por considerando y por punto de anexo. Estructura del HTML en [docs/estructura_html.md](docs/estructura_html.md).

## Estado
Fase 1 (montaje del repo) en curso. Ver [PROGRESS.md](PROGRESS.md).
