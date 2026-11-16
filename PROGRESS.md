# Progreso

- [x] Fase 1 — Montaje del repo (completada 2026-11-16)
- [x] Fase 2 — Ingesta y almacenamiento (completada)
  - [x] 2a — Parser del HTML de EUR-Lex → `data/processed/chunks.jsonl`
  - [x] 2b — Embeddings (Cloudflare bge-m3) y carga en Neon/pgvector: 854 fragmentos en Neon, ingesta idempotente (hash), búsqueda verificada, sin truncado
- [ ] Fase 3 — Siguiente: generación con Groq y endpoint de respuesta
- [ ] Fase 4
- [ ] Fase 5
- [ ] Fase 6

## Decisiones
- [ADR 001](docs/decisiones/001-embeddings.md): embeddings con Cloudflare `@cf/baai/bge-m3`.
- [ADR 002](docs/decisiones/002-base-de-datos.md): Neon (ramas `development`/`production`) en lugar de Supabase.

## Ideas para fases futuras
- Troceo por artículo y apartado.
- Devolver el artículo completo cuando se recupere un apartado.
- Comparar embeddings (bge-m3 frente a Voyage voyage-4, multilingual-e5, jina-embeddings-v2-base-es) con evaluaciones propias en la fase 4.
- Fragmentos largos: no hay truncado, pero cos(completo, últimos 1800) = 0,68 en `art-5-ap-1`, así que el final de los fragmentos largos pesa poco en el embedding. Evaluar en la fase 4 con preguntas sobre letras finales (p. ej. art. 5.1 h) y, si falla, trocear los apartados largos por letras.
