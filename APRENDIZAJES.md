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
