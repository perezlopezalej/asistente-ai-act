# Aprendizajes

## 1. uv frente a npm (Python para gente de JavaScript)

| JavaScript | Python (uv) | Para qué sirve |
|---|---|---|
| `npm` | `uv` | Gestor de dependencias y entornos |
| `node_modules/` | `.venv/` | Dependencias instaladas, aisladas por proyecto (no se commitea) |
| `package.json` | `pyproject.toml` | Metadatos, dependencias y configuración de herramientas |
| `package-lock.json` | `uv.lock` | Versiones exactas resueltas (sí se commitea) |
| `npm install` | `uv sync` | Instalar según el lock |
| `npm install x` / `-D x` | `uv add x` / `uv add --group dev x` | Añadir dependencia (normal / desarrollo) |
| `npx cmd` / `npm run` | `uv run cmd` | Ejecutar dentro del entorno |
| `npm audit` | `uv run pip-audit` | Buscar vulnerabilidades conocidas en dependencias |

- Un venv es un entorno virtual: una carpeta con su propio Python y paquetes, equivalente a tener `node_modules` por proyecto. `uv` lo crea y gestiona solo.
- `pip-audit` consulta bases de datos de vulnerabilidades (PyPI/OSV) sobre lo instalado; `npm audit` hace lo mismo con el registro de npm.

## 2. Git y GitHub

- **Rama default:** la primera rama que se sube a un repo vacío se convierte en la default de GitHub. Por eso hay que subir `main` primero y después las ramas de trabajo.
- **Conflicto de merge:** ocurre cuando dos ramas cambian las mismas líneas y Git no sabe cuál conservar. Con Dependabot se resuelve comentando `@dependabot rebase` en su PR: rehace la rama sobre el `main` actual.
- **LF frente a CRLF:** Windows termina las líneas con CRLF; Linux y macOS, con LF. Mezclarlos genera diffs ruidosos y puede romper scripts en CI (que corre en Linux). `.gitattributes` con `* text=auto eol=lf` normaliza todo a LF en el repo y en el checkout.
- **gh CLI:** `gh pr create` abre un PR, `gh pr checks` muestra el estado de CI y `gh pr merge` lo fusiona.

## 3. Parser de HTML y datos (BeautifulSoup, pydantic, JSONL)

- **BeautifulSoup frente a cheerio:** ambos recorren el DOM con selectores CSS. `soup.select("div#art_5")` equivale a `$("div#art_5")`; `.get_text(" ")` a `.text()`; `.find_parent()` a `.closest()`. Se usa con `lxml` como motor, que tolera mejor el HTML antiguo de EUR-Lex.
- **pydantic frente a zod:** el modelo `Fragmento` (clase con tipos) hace de esquema y de tipo a la vez, como `z.object` + `z.infer`. Valida al construir y `model_dump_json()` serializa.
- **JSONL:** un objeto JSON por línea. Se puede escribir y leer en streaming, `git diff` muestra solo las líneas cambiadas y un fallo no corrompe el resto del fichero (un JSON grande sí).

## 4. Embeddings y base vectorial (Cloudflare, Neon, pgvector)

- **`Protocol` frente a `interface` de TypeScript:** ambos describen un contrato (`embed_documents`, `embed_query`). La diferencia: en Python el `Protocol` es *estructural*; cualquier clase con esos métodos lo cumple sin declarar `implements`, y solo importa para el type checker (en ejecución es tipado por patos). Por eso `FakeEmbedder` y `CloudflareEmbedder` son intercambiables en los tests.
- **psycopg 3 frente a `pg` de Node:** `psycopg.connect(url)` equivale a `new Client({connectionString})`. Los parámetros van como `%s` (en `pg`, `$1`) y se pasan aparte para evitar inyección SQL; el tipo `vector` se registra con `register_vector(conn)`, y los vectores se envían envueltos en `Vector(lista)`. `with conn:` cierra la conexión como un `try/finally`.
- **pgvector:** extensión de Postgres que añade el tipo `vector(N)` y operadores de distancia: `<->` (euclídea), `<#>` (producto interno negativo) y `<=>` (coseno). La dimensión debe coincidir con el modelo (bge-m3 → 1024).
- **Similitud coseno:** mide el ángulo entre dos vectores, no su longitud: 1 = misma dirección, 0 = sin relación. Con textos, es lo habitual porque importa el tema y no la magnitud. pgvector devuelve *distancia* (`<=>`), así que la similitud es `1 - distancia`.
- **Índice HNSW:** grafo de vecinos por capas que busca el vecino más cercano de forma *aproximada* pero muy rápida (`using hnsw (embedding vector_cosine_ops)`). El operador del índice debe coincidir con el de la consulta (coseno ↔ `<=>`). Con ~850 filas un escaneo exacto bastaría; se usa HNSW porque es lo que escalaría.
- **HNSW + filtro (WHERE):** al ser aproximado, el índice devuelve ~`hnsw.ef_search` candidatos (40 por defecto) y el `WHERE` se aplica *después*. Con `tipos = ['articulo']` podrían salir menos filas de las pedidas aunque existan. Soluciones: *iterative scan* (pgvector ≥ 0.8, `hnsw.iterative_scan = relaxed_order`: el índice sigue explorando hasta reunir las filas pedidas que cumplan el filtro) o, en versiones anteriores, subir `hnsw.ef_search` (p. ej. 100). Con `relaxed_order` el orden no es exacto, por eso `buscar_fragmentos` reordena el resultado en una CTE. Se fija con una cláusula `SET` en la función, y la migración elige la variante según la versión.
- **Ramas de Neon:** como las ramas de git pero de la base de datos (copy-on-write). `development` (la `DATABASE_URL` del `.env` local) y `production` (solo despliegue) comparten esquema pero no datos, así que probar migraciones o recargar embeddings no toca producción.
- **Idempotencia por hash:** se guarda `sha256(modelo + texto embebido)`; al relanzar la carga solo se re-embeben los fragmentos nuevos o cambiados, y el upsert (`on conflict (id) do update`) evita duplicados.
- **Cabecera de contexto:** se embebe «Artículo 5. Título. Apartado 1: texto» para que el vector capte *dónde* está el fragmento; en la base de datos se guarda el texto original sin cabecera.

## 5. Dos trampas encontradas al cargar los embeddings

- **Test de truncado: probar prefijos mayores que el límite sospechado.** Comparar el texto completo con un prefijo *menor* que el supuesto límite no demuestra nada: el vector cambia aunque no haya truncado. Hay que probar prefijos cada vez mayores y buscar identidad (cos ≥ 0,9999). Resultado con `art-5-ap-1`: 0,94 → 0,96 → 0,98 → 0,99, creciendo sin llegar a la identidad, así que **no hay truncado**. El dato de 512 tokens que se barajaba era de AI Search, no del modelo bge-m3.
- **Las variables de entorno del sistema ganan al `.env`.** En pydantic-settings, igual que `dotenv` en Node (que no pisa variables ya definidas), una variable de entorno de Windows tiene prioridad sobre el `.env`. Una `DATABASE_URL` global olvidada rompió la conexión aunque el `.env` estuviera bien. Ante un fallo raro de configuración, comprueba primero el entorno (`$env:DATABASE_URL` en PowerShell) y usa `scripts/diagnostico_db.py`.

## 6. Generación con citas (RAG, JSON mode, prompt injection)

- **JSON mode y decodificación restringida:** al pedir `response_format` con un JSON Schema, el servidor puede *restringir* la generación token a token para que solo se emitan secuencias válidas (decodificación restringida). Es parecido a validar con zod, pero *durante* la generación y no después. No todos los modelos ni proveedores lo aplican (en Workers AI gpt-oss no figura en la lista de compatibles), y aun aplicándose solo garantiza la *forma*, no la *verdad* (un id puede ser válido como texto y estar inventado). Por eso se valida SIEMPRE en nuestro código con pydantic, con 1 reintento y error controlado.
- **El envoltorio importa:** OpenAI espera `{type: "json_schema", json_schema: {name, schema, strict}}`; los modelos nativos de Workers AI esperan el JSON Schema "pelado" dentro de `json_schema`. Mismo concepto, forma distinta: hay que leer la ficha de cada proveedor.
- **Abstención («no lo sé») con dos barreras:** (1) *umbral de similitud* antes de llamar al modelo: barato y determinista, pero tosco (el 0,60 es provisional y se calibra con evaluaciones); (2) *salida explícita en el prompt* (`sin_informacion=true`) para cuando los fragmentos recuperados parecen cercanos pero no responden. Una sola barrera no basta: la primera deja pasar ruido y la segunda depende de que el modelo obedezca.
- **Citas por afirmación y verificadas en código:** pedir al modelo «frase + ids de fragmentos» y comprobar los ids contra lo que *realmente* se le envió. El modelo nunca decide la cita legible ni la URL: salen de la base de datos por id. Lo que el modelo cita debe ser un *dato verificable*, no una afirmación a creer.
- **Prompt injection es contención, no solución:** no existe un filtro que la elimine (OWASP LLM01). Se reduce el daño posible: pregunta delimitada y declarada como dato, etiquetas del delimitador neutralizadas, sin secretos en el prompt, sin herramientas y salida verificada por código (el atacante puede conseguir una respuesta rara, pero no citas inventadas ni cambiar el aviso legal). Es el mismo principio que no confiar en la entrada del cliente en una API.
- **Cuotas por organización, no por proyecto:** Groq cuenta la cuota por organización, así que otro proyecto que use la misma consumía la de este. Antes de elegir un proveedor gratuito conviene mirar *quién comparte* la cuota, no solo cuánta hay. En Cloudflare las «neuronas» (10.000/día gratis) se comparten entre embeddings y generación; por eso se registra el consumo de cada pregunta.
- **Razonamiento y `max_tokens`:** en los modelos de razonamiento (gpt-oss) `max_tokens` **incluye los tokens de razonamiento**, no solo los de la respuesta visible. Con `max_tokens=1000` y esfuerzo `low`, el modelo gastó ~3.700 caracteres pensando y el JSON se cortó a medias (`finish_reason: "length"`, `completion_tokens=1000`). Lecciones: (1) dimensionar el tope contando el razonamiento (3000 por defecto aquí); (2) un `finish_reason="length"` no se reintenta, porque volvería a cortarse y gastaría cuota: se lanza un error específico y se sube el tope; (3) leer `finish_reason` es lo primero que hay que mirar cuando un JSON llega incompleto (para eso existe `preguntar.py --debug`); (4) el nombre del parámetro depende del formato de la API: en chat completions es `reasoning_effort` en la raíz, no `reasoning: {effort}` (Responses API).
- **Sync + hilos en FastAPI:** un endpoint declarado con `def` (no `async def`) se ejecuta en un pool de hilos, así que usar `psycopg` y `httpx` síncronos no bloquea el servidor. En Node el equivalente sería no bloquear el event loop con una llamada síncrona.
- **`Depends` y `dependency_overrides`:** FastAPI inyecta el `Pipeline` con `Depends(get_pipeline)`; los tests lo sustituyen con `app.dependency_overrides[get_pipeline] = ...` y un `FakeLLM`, algo así como inyectar un mock en el contenedor de dependencias.
- **Desajuste de vocabulario usuario/texto legal:** el usuario dice «chatbot» y el Reglamento dice «sistemas de IA destinados a interactuar directamente con personas físicas» (art. 50). Los embeddings capturan significado, pero no siempre acercan una jerga a su término legal: la búsqueda no encontró el art. 50. Remedios a medir en la fase 4: reescribir la pregunta a terminología legal antes de buscar, o búsqueda híbrida.
- **Similitudes planas = búsqueda sin resultado claro:** cuando los mejores candidatos salen casi iguales (0,516-0,526), ninguno destaca y el ranking es casi ruido; una similitud alta y aislada indica un acierto. Mirar la *forma* de la distribución, no solo el máximo. Por eso el umbral (0,50, provisional) se calibra con preguntas etiquetadas, incluidas las que no tienen respuesta (con 0,60 se rechazó una legítima de 0,526; RGPD daba 0,455 y una inyección 0,321).
- **Diagnóstico «¿viene de los datos o del modelo?»:** ante un fallo raro (el modelo escribe «labúsqueda», sin espacio), antes de tocar el prompt se comprueba si el defecto ya está en la entrada (los fragmentos). Aquí no lo estaba, así que es del modelo (temperatura/tamaño). Aislar la capa evita arreglar donde no toca.
