# Asistente AI Act

Asistente RAG en español sobre el Reglamento (UE) 2024/1689 (AI Act). Responde citando el artículo exacto y dice "no lo sé" cuando no hay contexto relevante.

> **Basado en el texto original del Reglamento (UE) 2024/1689; no incluye la modificación del Reglamento (UE) 2026/1744 (AI Omnibus).**

> **Aviso:** esto no es asesoramiento legal. Consulta a un profesional cualificado.

## Stack
Python 3.12, FastAPI, Neon (Postgres + pgvector), Cloudflare Workers AI (generación con gpt-oss-120b y embeddings con bge-m3), Next.js.

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

### Cloudflare (embeddings y generación)
1. Crea una cuenta gratuita en Cloudflare y copia tu **Account ID** → `CLOUDFLARE_ACCOUNT_ID`.
2. Crea un **API Token** con permiso *Workers AI* → `CLOUDFLARE_API_TOKEN`.
3. `EMBEDDING_MODEL` ya trae `@cf/baai/bge-m3` (1024 dimensiones). Decisión en [ADR 001](docs/decisiones/001-embeddings.md).
4. `LLM_MODEL` trae `@cf/openai/gpt-oss-120b` (alternativa: `@cf/openai/gpt-oss-20b`). Decisión en [ADR 003](docs/decisiones/003-generacion-y-citas.md).
5. Embeddings y generación comparten la cuota gratuita de **10.000 neuronas/día** (se reinicia a las 00:00 UTC). El log de cada pregunta incluye los tokens y las neuronas estimadas.

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

## Preguntar al asistente
Con la API arrancada (`uv run uvicorn app.main:app --reload`, desde `backend/`):

```bash
curl -X POST http://127.0.0.1:8000/preguntar \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "¿Qué prácticas de IA están prohibidas?"}'
```

`pregunta`: 1-1000 caracteres (se eliminan los caracteres de control). Respuesta:

```json
{
  "estado": "respondida",
  "afirmaciones": [
    {"texto": "Está prohibido comercializar sistemas de IA que usen técnicas subliminales para alterar el comportamiento de una persona causándole perjuicio.", "citas": [1]},
    {"texto": "También se prohíbe el uso de sistemas de puntuación social con efectos perjudiciales.", "citas": [1, 2]}
  ],
  "citas": [
    {"n": 1, "id": "art-5-ap-1", "cita": "Artículo 5, apartado 1", "tipo": "articulo", "url": "https://eur-lex.europa.eu/…"},
    {"n": 2, "id": "rct-31", "cita": "Considerando 31", "tipo": "considerando", "url": "https://eur-lex.europa.eu/…"}
  ],
  "mensaje": null,
  "aviso_legal": "Esta información se basa únicamente en el texto del Reglamento (UE) 2024/1689 y no constituye asesoramiento legal. Consulta a un profesional cualificado.",
  "meta": {"modelo": "@cf/openai/gpt-oss-120b", "latencia_ms": 2300, "similitud_max": 0.7421}
}
```

(El ejemplo es ilustrativo.) Si el Reglamento no contiene información relevante, `estado` es `"sin_informacion"`, `afirmaciones` y `citas` están vacíos y `mensaje` explica el límite del asistente (en `respondida`, `mensaje` es `null`). El **`aviso_legal` lo añade siempre el backend**. Las citas (`cita`, `tipo`, `url`) salen de la base de datos, nunca del modelo, y cada afirmación debe apoyarse en al menos un artículo o anexo (los considerandos solo acompañan).

Errores: `503` si Cloudflare limita o agota la cuota («inténtalo más tarde»), `502` ante cualquier otro fallo del proveedor, `422` si la pregunta no es válida. La respuesta lleva la cabecera `X-Request-ID`: se reutiliza la del cliente si cumple `^[A-Za-z0-9-]{1,64}$`; si no, se genera un uuid4.

Prueba manual sin levantar la API (llama a Cloudflare y a Neon; muestra respuesta, meta y consumo):
```bash
uv run python scripts/preguntar.py "¿Qué prácticas de IA están prohibidas?"
```

## Estado
Fase 2 (ingesta, embeddings y Neon) completada; fase 3 (generación con citas y `POST /preguntar`) implementada, pendiente de la primera ejecución real. Ver [PROGRESS.md](PROGRESS.md).
