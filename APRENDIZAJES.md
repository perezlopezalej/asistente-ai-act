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
