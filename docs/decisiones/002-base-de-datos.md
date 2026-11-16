# ADR 002 — Base de datos: Neon en lugar de Supabase

- **Estado:** aceptada (2026-11-16). Sustituye la elección inicial de Supabase.

## Contexto
Hace falta Postgres con `pgvector` para guardar los fragmentos y sus embeddings. El plan gratuito de Supabase limita a **2 proyectos activos por usuario**, y ya están ocupados con otros proyectos.

## Opciones
- **Supabase (gratis):** incluye auth/storage/API que aquí no se usan, pero el límite de proyectos lo bloquea.
- **Neon (gratis):** Postgres serverless estándar con `pgvector`, región UE (Frankfurt).

## Decisión
**Neon**, región Frankfurt, accedido con `psycopg 3` + el paquete `pgvector` mediante `DATABASE_URL`.

## Consecuencias
- **Postgres estándar:** sin SDK propietario; migrar a otro Postgres (incluido Supabase) es cambiar `DATABASE_URL`.
- **Región UE:** los datos quedan en Frankfurt.
- **Scale-to-zero con arranque en frío:** tras un rato inactiva, la base se suspende y la primera consulta tarda más (del orden de segundos). Aceptable en desarrollo; a vigilar en producción (timeouts de conexión y reintento).
- **Dos ramas de Neon para separar entornos:**
  - `development`: su cadena de conexión es la `DATABASE_URL` del `.env` local. Aquí se prueban migraciones y cargas.
  - `production`: solo para el despliegue; nunca se usa en local.
- Las migraciones (`db/migrations/`) se ejecutan a mano en el SQL Editor de Neon, primero en `development` y luego en `production`.
- Se pierde lo que da Supabase y no necesitamos (auth, storage, API REST autogenerada); si hiciera falta, se resolvería aparte.
