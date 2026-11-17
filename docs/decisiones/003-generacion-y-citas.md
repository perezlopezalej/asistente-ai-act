# ADR 003 — Generación de respuestas y citas verificadas

- **Estado:** aceptada (2026-11-16)
- **Pendiente:** confirmar con la primera ejecución real el formato de petición/respuesta de gpt-oss en Workers AI (ver «Incertidumbre»); calibrar `UMBRAL_SIMILITUD` y medir la búsqueda híbrida en la fase 4.

## Contexto
El asistente debe responder sobre el Reglamento (UE) 2024/1689 **citando el artículo exacto**, decir «no lo sé» cuando el texto no responde y no confiar nunca en lo que el modelo afirme sobre *dónde* está algo. Restricciones: coste cero, cuota gratuita permanente y datos tratados de forma aceptable para usuarios en el EEE.

## Proveedor del modelo
| Opción | Veredicto |
|---|---|
| **Cloudflare Workers AI, `@cf/openai/gpt-oss-120b`** | Elegida. Misma cuenta y token que los embeddings (nada nuevo que gestionar), cuota gratuita permanente de 10.000 neuronas/día (reinicio 00:00 UTC), modelo de pesos abiertos. Alternativa configurable: `gpt-oss-20b` (~40 % más barato). |
| Groq | Descartada **para este proyecto**: su cuota es **por organización** y otro proyecto propio (un bot) ya la consume en todos los modelos. |
| Cerebras | Descartada: no tiene plan gratuito permanente. |

Coste estimado de gpt-oss-120b: 31.818 neuronas/M tokens de entrada y 68.182/M de salida. Con ~3.000 tokens de entrada y ~400 de salida una pregunta cuesta del orden de 120 neuronas, es decir, unas 80 preguntas/día compartidas con los embeddings. El log de cada pregunta registra los tokens que devuelve la API y las neuronas estimadas.

Se usa detrás de un `Protocol` (`LLM`), como el `Embedder`: `CloudflareLLM` y `FakeLLM` (tests sin red). Esfuerzo de razonamiento `low`, temperatura 0,1 y `LLM_MAX_TOKENS=3000` (los tokens de razonamiento cuentan dentro del tope; con 1000 la primera ejecución real salió truncada: `finish_reason=length`, ~3.700 caracteres de razonamiento).

## Decisiones de diseño
1. **Citas por afirmación, no por respuesta.** El modelo devuelve `{"sin_informacion", "afirmaciones": [{"texto", "fragmentos": [ids]}]}`. Cada frase queda ligada a sus fuentes, se puede descartar una frase sin perder la respuesta entera, y el frontend puede enseñar qué fuente respalda qué frase.
2. **Verificación en código, determinista** (`rag/verificacion.py`): se descartan ids que no estén entre los fragmentos *realmente enviados* (el modelo puede inventar o citar uno que el presupuesto de contexto dejó fuera); se descartan las afirmaciones sin al menos un id de tipo artículo/anexo (los considerandos solo acompañan); si no queda ninguna, el estado es `sin_informacion`. La numeración `[n]` la hace el backend por orden de aparición y `cita`, `tipo` y `url` salen **siempre de la base de datos**, nunca del modelo. Se registra cuántas afirmaciones e ids se descartaron.
3. **Dos barreras de abstención.** (1) Si la similitud del mejor artículo/anexo es `< UMBRAL_SIMILITUD` (0,50, provisional) se responde `sin_informacion` **sin llamar al LLM**: ahorra neuronas y evita que el modelo improvise con fragmentos irrelevantes. (2) El prompt ofrece explícitamente `sin_informacion=true` si los fragmentos no responden. El mensaje explica el límite (solo el texto del Reglamento) y va en el campo `mensaje` de la respuesta (`afirmaciones` y `citas` vacías); en `respondida`, `mensaje` es `null`.
4. **Salida estructurada, pero validada siempre en nuestro código.** Se envía `response_format` con el JSON Schema *pelado* (los modelos nativos de Workers AI no esperan el envoltorio de OpenAI `{name, schema, strict}`) y, además, el prompt dicta la forma exacta. Con pydantic se valida SIEMPRE; salida inválida → 1 reintento; segundo fallo → error controlado (502). Sin streaming.
5. **Contención de prompt injection** (no se puede «resolver», se contiene; OWASP LLM01): la pregunta va delimitada en `<pregunta>…</pregunta>` neutralizando esas etiquetas si aparecen dentro (también las de `<fragmento>`); el system prompt declara que pregunta y fragmentos son datos y que no se siguen órdenes contenidas en ellos; el prompt no contiene secretos; el modelo no tiene herramientas; y lo que el modelo produce solo se acepta tras la verificación del punto 2 (aunque un atacante lograra desviarlo, no puede inventar citas ni cambiar `aviso_legal`, que lo añade el backend).
6. **Contexto:** `K_ARTICULOS=5` artículos/anexos (citables) y `K_CONSIDERANDOS=2` considerandos (marcados como «contexto interpretativo, no citable como fuente principal»), con presupuesto de 10.000 caracteres: por orden de relevancia, sin cortar fragmentos a mitad (se salta el que no cabe; solo el primero se trunca si él solo lo supera, con aviso en el log). Los citables van antes que los considerandos.
7. **Privacidad en logs:** id de petición, longitud de la pregunta, estado, latencia, similitud, descartes y consumo; **nunca el texto de la pregunta**.
8. **Truncado:** si `finish_reason == "length"` no se reintenta (volvería a truncarse y gastaría neuronas): `LLMTruncadoError` → 502 y aviso en el log. El reintento queda para JSON inválido por otras causas.
9. **Prompt y alcance:** si los fragmentos solo cubren parte de la pregunta, se responde solo esa parte; ante preguntas sobre un caso concreto (¿mi sistema es de alto riesgo?) se explica lo que establece el Reglamento sin dictaminar el caso. `X-Request-ID` del cliente solo se acepta con formato `^[A-Za-z0-9-]{1,64}$`, si no se genera un uuid4.
10. **Errores:** 429 o cuota agotada → 503 «inténtalo más tarde»; cualquier otro fallo del proveedor o de la base de datos → 502 genérico. Nunca claves ni trazas en la respuesta.

## Búsqueda híbrida: pospuesta a la fase 4
Combinar la búsqueda vectorial con texto completo (p. ej. para consultas con «artículo 5» o términos literales) podría mejorar la recuperación, pero no hay medidas todavía. Primero se construye el conjunto de evaluación de la fase 4 y se mide la recuperación actual; solo se añade complejidad si los datos lo justifican.

## Incertidumbre: formato de gpt-oss en Workers AI
La documentación consultada el 2026-11-16 es contradictoria: la ficha del modelo describe `messages`, `max_tokens`, `temperature` y `response_format`; el changelog y el blog de lanzamiento dicen que `/ai/run` acepta y devuelve el formato *Responses API* (`input`, `reasoning.effort`); no hay ejemplos de respuesta ni nombre documentado del campo de razonamiento en la variante `messages`; y la página de JSON mode no lista gpt-oss entre los modelos compatibles.
Por eso: la petición usa `messages` + `response_format` + `reasoning_effort: "low"` en la raíz (la primera ejecución real confirmó que la respuesta llega en formato chat completions, `result.choices`); la respuesta se lee con un extractor tolerante (`choices[].message.content`, `output[]` de la Responses API, `output_text`, `response`); la petición y la lectura viven en un solo fichero (`llm/cloudflare.py`: `_cuerpo()` y `_extraer()`); y si la forma no se reconoce se registra solo la lista de claves de la respuesta, nunca su contenido.

## Consecuencias
- Dependemos de la cuota gratuita de Cloudflare compartida entre embeddings y generación; si se agota, la API responde 503 hasta las 00:00 UTC.
- Una afirmación con un id válido pero mal elegido (el modelo cita un artículo que no la respalda) **no** se detecta en código: se medirá en la fase 4 con evaluaciones propias.
- El prompt prohíbe números de artículo en el texto de las afirmaciones, pero el código solo elimina marcadores `[n]`; comprobarlo también es trabajo de la fase 4.
