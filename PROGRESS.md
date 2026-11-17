# Progreso

- [x] Fase 1 — Montaje del repo (completada 2026-11-16)
- [x] Fase 2 — Ingesta y almacenamiento (completada)
  - [x] 2a — Parser del HTML de EUR-Lex → `data/processed/chunks.jsonl`
  - [x] 2b — Embeddings (Cloudflare bge-m3) y carga en Neon/pgvector: 854 fragmentos en Neon, ingesta idempotente (hash), búsqueda verificada, sin truncado
- [x] Fase 3 — Generación con Cloudflare Workers AI y endpoint `POST /preguntar` con citas verificadas (completada; ver ADR 003)
- [ ] Fase 4
- [ ] Fase 5
- [ ] Fase 6

## Decisiones
- [ADR 001](docs/decisiones/001-embeddings.md): embeddings con Cloudflare `@cf/baai/bge-m3`.
- [ADR 002](docs/decisiones/002-base-de-datos.md): Neon (ramas `development`/`production`) en lugar de Supabase.
- [ADR 003](docs/decisiones/003-generacion-y-citas.md): generación con Cloudflare Workers AI (no Groq), citas por afirmación verificadas en código, dos barreras de abstención.

## Ideas para fases futuras
- **Fase 4 (pendientes de la fase 3):**
  - a) Reescritura de consultas: «chatbot» no aparece en el Reglamento (el art. 50 dice «sistemas de IA destinados a interactuar directamente con personas físicas»); la búsqueda no encuentra el art. 50 y las similitudes salen planas (0,516-0,526). Probar que el LLM reescriba la pregunta a terminología legal antes de buscar, y medirlo.
  - b) Calibrar `UMBRAL_SIMILITUD` (0,50, provisional) con preguntas etiquetadas, incluidas preguntas sin respuesta. Referencias: pregunta legítima 0,526; RGPD 0,455; inyección 0,321.
  - c) El modelo omite espacios de vez en cuando («labúsqueda»); verificado que no viene de los datos. Comparar con gpt-oss-20b o con otra temperatura.
  - d) Verificar en código que no haya números de artículo en el texto de las afirmaciones.
- Troceo por artículo y apartado.
- Devolver el artículo completo cuando se recupere un apartado.
- Comparar embeddings (bge-m3 frente a Voyage voyage-4, multilingual-e5, jina-embeddings-v2-base-es) con evaluaciones propias en la fase 4.
- Fase 4: medir si hace falta búsqueda híbrida (vectorial + texto completo) antes de añadirla.
- Fragmentos largos: no hay truncado, pero cos(completo, últimos 1800) = 0,68 en `art-5-ap-1`, así que el final de los fragmentos largos pesa poco en el embedding. Evaluar en la fase 4 con preguntas sobre letras finales (p. ej. art. 5.1 h) y, si falla, trocear los apartados largos por letras.
