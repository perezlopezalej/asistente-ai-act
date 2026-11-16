# ADR 001 — Proveedor de embeddings

- **Estado:** aceptada (2026-11-16)
- **Pendiente:** comparar con Voyage (voyage-4) en la fase 4, con evaluaciones propias.

## Contexto
El asistente necesita embeddings multilingües (español jurídico) para ~850 fragmentos del AI Act y para cada pregunta. Restricciones: coste cero o casi cero, **uso legítimo en una app con usuarios en el EEE** y sin tarjeta obligatoria. Hay que embeber el corpus una vez (y de nuevo si cambia el modelo o la cabecera) y cada consulta después.

## Opciones evaluadas
| Opción | Veredicto |
|---|---|
| **Cloudflare Workers AI, `@cf/baai/bge-m3`** | Elegida. 1024 dim, multilingüe, 60.000 tokens de contexto, REST simple, cuota gratuita suficiente para este corpus. |
| Voyage `voyage-4` | Buena calidad, pero sin tarjeta el límite es de **3 RPM**: inviable para ingerir. A comparar en la fase 4. |
| Jina v3 | El plan gratuito es **no comercial**. |
| Mistral embeddings | Descartada: el plan gratuito exige aceptar que los datos se usen para entrenar. Aceptable con el texto público del reglamento, **no con documentos privados** (Zitly). Además, límite de ~1 petición/segundo. |
| Cohere | La clave *trial* **no permite uso en producción**. |
| Gemini | El nivel gratuito **no está permitido para apps con usuarios en el EEE** y puede **usar los datos para entrenar**. |
| Hugging Face Inference Providers | Descartada: los usuarios gratuitos reciben menos de 0,10 $/mes en créditos, insuficiente y sujeto a cambios. |

## Decisión
`@cf/baai/bge-m3` en Cloudflare Workers AI, vía REST con `httpx` detrás de un `Protocol` (`Embedder`). Se guarda el nombre del modelo y un hash (texto embebido + modelo) por fragmento para saber qué hay que re-embeber.

## Consecuencias
- **Portabilidad:** bge-m3 es un modelo abierto: se puede autoalojar (o cambiar de proveedor que lo ofrezca) **sin re-embeber**, porque los vectores son los mismos.
- La dimensión (1024) queda fijada en el esquema (`vector(1024)`); cambiar a un modelo de otra dimensión exige migración y re-embeber todo.
- Dependemos de la cuota gratuita de Cloudflare y de su esquema de respuesta, que no está documentado en detalle: el cliente lo valida (nº de vectores y dimensiones).
- Se embebe "cabecera de contexto + texto" (p. ej. `Artículo 5. Prácticas de IA prohibidas. Apartado 1: …`); el texto original se guarda aparte.
- Cambiar de modelo o de cabecera cambia el hash y fuerza el re-embebido (`scripts/embed_and_upload.py`).
- La comparación con Voyage en la fase 4 puede revisar esta decisión.
