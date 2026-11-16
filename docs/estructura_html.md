# Estructura del HTML de EUR-Lex (AI Act, ES)

Fichero: `data/raw/CELEX_32024R1689_ES_TXT.html` (descarga manual, no versionado).
Totales reales: 113 artículos, 180 considerandos, 13 anexos.

| Elemento | Selector | Notas |
|---|---|---|
| Considerando | `div.eli-subdivision#rct_N` | Tabla de 2 celdas: `(N)` y texto en `p.oj-normal` |
| Capítulo | `div#cpt_IV` | Número en `p.oj-ti-section-1`; título en `div.eli-title p.oj-ti-section-2` |
| Sección | `div#cpt_III.sct_1` | Mismo patrón; anidada en el capítulo |
| Artículo | `div.eli-subdivision#art_N` | Anidado en capítulo/sección; número en `p.oj-ti-art` |
| Título artículo | `div.eli-title#art_N.tit_1 p.oj-sti-art` | |
| Apartado | `div#NNN.MMM` (p. ej. `005.001`) | Texto `"1.&nbsp;&nbsp;&nbsp;..."` en `p.oj-normal` |
| Letras a), b)… | `table > tr > td` anidadas dentro del apartado | Se aplanan al texto del apartado |
| Definiciones (art. 3) | filas `table` directas bajo el artículo: `1)`, `2)`… | Sin `div` de apartado |
| Anexo | `div.eli-container#anx_X` | Título en `p.oj-doc-ti` ("ANEXO III") + subtítulo en el siguiente `p.oj-doc-ti` |
| Puntos de anexo | filas de `table` de primer nivel (`1.`) o `p.oj-ti-grseq-1` | "Sección A/B/C" en I y VIII; "Sección 1/2" en XI |

## Particularidades
- Artículos sin apartados (texto directo o lista en tabla): 3, 4, 16, 32, 39, 66, 85, 87, 94, 102-110, 113, entre otros.
- `&nbsp;` y saltos de línea duros dentro de `<p>`: hay que normalizar espacios.
- Notas al pie: `<a><span class="oj-super oj-note-tag">N</span></a>`: se eliminan.
- `<link rel="canonical">` apunta a la versión `/eng`; la URL de origen se construye a mano con el ancla del `id`.
