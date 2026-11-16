# Asistente AI Act

Asistente RAG en español sobre el Reglamento (UE) 2024/1689 (AI Act). Responde citando el artículo exacto y dice "no lo sé" cuando no hay contexto relevante.

> **Aviso:** esto no es asesoramiento legal. Consulta a un profesional cualificado.

## Stack
Python 3.12, FastAPI, Neon (Postgres + pgvector), Groq, embeddings con Cloudflare Workers AI (bge-m3), Next.js.

## Arranque en local
```bash
cp .env.example .env     # en la raíz; rellena tus claves (ver «Configuración»)
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

## Configuración
Todas las variables viven en un único `.env` **en la raíz del repo** (copia de `.env.example`; nunca se commitea). El backend lo localiza por ruta absoluta, así que funciona se ejecute desde donde se ejecute.

### Cloudflare (embeddings)
1. Crea una cuenta gratuita en Cloudflare y copia tu **Account ID** → `CLOUDFLARE_ACCOUNT_ID`.
2. Crea un **API Token** con permiso *Workers AI* → `CLOUDFLARE_API_TOKEN`.
3. `EMBEDDING_MODEL` ya trae `@cf/baai/bge-m3` (1024 dimensiones). Decisión en [ADR 001](docs/decisiones/001-embeddings.md).

### Neon (base de datos)
1. Crea un proyecto en Neon, región **Frankfurt**. Tiene dos ramas:
   - `development`: su cadena de conexión va en `DATABASE_URL` del `.env` local.
   - `production`: solo para el despliegue; no se usa en local.
2. En el SQL Editor de la rama `development`, ejecuta [db/migrations/001_fragmentos.sql](db/migrations/001_fragmentos.sql) (crea la extensión `vector`, la tabla `fragmentos`, el índice HNSW y la función `buscar_fragmentos`). Decisión en [ADR 002](docs/decisiones/002-base-de-datos.md).

### Cargar y probar los embeddings (desde `backend/`)
```bash
uv run python scripts/probar_truncado.py        # ¿se trunca el texto largo?
uv run python scripts/embed_and_upload.py       # embebe y sube (idempotente: salta lo que no ha cambiado)
uv run python scripts/buscar.py "¿Qué prácticas de IA están prohibidas?" [--tipo articulo]
```

## Estado
Fase 2 (ingesta, embeddings y Neon) completada; siguiente, fase 3. Ver [PROGRESS.md](PROGRESS.md).
