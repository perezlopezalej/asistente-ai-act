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
