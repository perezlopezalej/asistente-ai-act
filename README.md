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

## Estado
Fase 1 (montaje del repo) en curso. Ver [PROGRESS.md](PROGRESS.md).
