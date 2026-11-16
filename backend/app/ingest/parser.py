"""Parser del HTML de EUR-Lex (AI Act, ES) a fragmentos con su cita."""

import re
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

URL_BASE = "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32024R1689"

_APARTADO_ID = re.compile(r"^\d{3}\.\d{3}$")
_NUM_INICIAL = re.compile(r"^(\d+)\.\s*")
_PUNTO_LABEL = re.compile(r"^(\d+)\.$")
_DEFINICION_LABEL = re.compile(r"^(\d+)\)$")
_TERMINO = re.compile(r"«([^»]+)»")


class Fragmento(BaseModel):
    id: str
    tipo: Literal["articulo", "considerando", "anexo"]
    numero: str
    apartado: str | None = None
    titulo_articulo: str | None = None
    capitulo: str | None = None
    texto: str
    cita: str
    url_fuente: str


def _limpiar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.replace("\xa0", " ")).strip()


def _texto(tag: Tag) -> str:
    """Texto plano de un elemento, sin notas al pie y con espacios normalizados."""
    for nota in tag.select("a:has(span.oj-note-tag)"):
        nota.decompose()
    # Separador " " para que la letra "a)" y su texto no se peguen.
    return _limpiar(tag.get_text(" "))


def _hijos(tag: Tag) -> list[Tag]:
    return [c for c in tag.children if isinstance(c, Tag)]


def _capitulo(art: Tag) -> str | None:
    cpt = art.find_parent("div", id=re.compile(r"^cpt_[IVX]+$"))
    if cpt is None:
        return None
    num = cpt.find("p", class_="oj-ti-section-1")
    titulo = cpt.find("div", class_="eli-title")
    if num is None:
        return None
    partes = [_limpiar(num.get_text(" "))]
    if titulo is not None:
        partes.append(_limpiar(titulo.get_text(" ")))
    return " — ".join(partes)


def _considerandos(soup: BeautifulSoup) -> list[Fragmento]:
    resultado = []
    for div in soup.select("div.eli-subdivision[id^=rct_]"):
        n = div["id"].removeprefix("rct_")
        celdas = div.find_all("td")
        texto = _texto(celdas[1]) if len(celdas) > 1 else _texto(div)
        resultado.append(
            Fragmento(
                id=f"rct-{n}",
                tipo="considerando",
                numero=n,
                texto=texto,
                cita=f"Considerando {n}",
                url_fuente=f"{URL_BASE}#{div['id']}",
            )
        )
    return resultado


def _contenido_articulo(art: Tag) -> list[Tag]:
    return [
        c
        for c in _hijos(art)
        if "oj-ti-art" not in (c.get("class") or []) and "eli-title" not in (c.get("class") or [])
    ]


def _articulos(soup: BeautifulSoup) -> list[Fragmento]:
    resultado = []
    for art in soup.select("div.eli-subdivision[id^=art_]"):
        n = art["id"].removeprefix("art_")
        titulo_tag = art.select_one("div.eli-title p.oj-sti-art")
        titulo = _limpiar(titulo_tag.get_text(" ")) if titulo_tag else None
        capitulo = _capitulo(art)
        contenido = _contenido_articulo(art)
        base = {
            "tipo": "articulo",
            "numero": n,
            "titulo_articulo": titulo,
            "capitulo": capitulo,
        }
        apartados = [
            c for c in contenido if c.name == "div" and _APARTADO_ID.match(c.get("id", ""))
        ]
        if apartados:
            for div in apartados:
                texto = _texto(div)
                m = _NUM_INICIAL.match(texto)
                ap = m.group(1) if m else str(int(div["id"].split(".")[1]))
                resultado.append(
                    Fragmento(
                        id=f"art-{n}-ap-{ap}",
                        apartado=ap,
                        texto=texto,
                        cita=f"Artículo {n}, apartado {ap}",
                        url_fuente=f"{URL_BASE}#{art['id']}",
                        **base,
                    )
                )
        elif n == "3":
            resultado.extend(_definiciones(art, base))
        else:
            texto = _limpiar(" ".join(_texto(c) for c in contenido))
            resultado.append(
                Fragmento(
                    id=f"art-{n}",
                    texto=texto,
                    cita=f"Artículo {n}",
                    url_fuente=f"{URL_BASE}#{art['id']}",
                    **base,
                )
            )
    return resultado


def _definiciones(art: Tag, base: dict) -> list[Fragmento]:
    """Artículo 3: un fragmento por definición (filas de tabla `N)`)."""
    resultado = []
    for tabla in art.find_all("table", recursive=False):
        celdas = tabla.find_all("td", recursive=True)
        if len(celdas) < 2:
            continue
        m = _DEFINICION_LABEL.match(_limpiar(celdas[0].get_text(" ")))
        if not m:
            continue
        n = m.group(1)
        texto = _texto(celdas[1])
        termino = _TERMINO.search(texto)
        cita = f"Artículo 3, punto {n}"
        if termino:
            cita += f" («{termino.group(1)}»)"
        resultado.append(
            Fragmento(
                id=f"art-3-ap-{n}",
                apartado=n,
                texto=texto,
                cita=cita,
                url_fuente=f"{URL_BASE}#{art['id']}",
                **base,
            )
        )
    return resultado


def _etiqueta_seccion(texto: str) -> str:
    """'Sección A — Lista...' -> 'A'; 'Sección 1' -> '1'."""
    m = re.match(r"^Secci[oó]n\s+(\w+)", texto)
    return m.group(1) if m else texto


def _abrir(unidades: list, sec: str | None, punto: str | None) -> tuple:
    unidad = (sec, punto, [])
    unidades.append(unidad)
    return unidad


def _anexos(soup: BeautifulSoup) -> list[Fragmento]:
    resultado = []
    for anx in soup.select("div.eli-container[id^=anx_]"):
        n = anx["id"].removeprefix("anx_")
        hijos = _hijos(anx)
        titulos = [c for c in hijos if "oj-doc-ti" in (c.get("class") or [])]
        subtitulo = _limpiar(titulos[1].get_text(" ")) if len(titulos) > 1 else None
        resto = [c for c in hijos if c not in titulos[:2]]

        # unidades: (seccion, punto|None, [textos])
        unidades: list[tuple[str | None, str | None, list[str]]] = []
        seccion: str | None = None
        actual: tuple[str | None, str | None, list[str]] | None = None

        for el in resto:
            clases = el.get("class") or []
            if el.name == "p" and "oj-ti-grseq-1" in clases:
                t = _limpiar(_texto(el))
                if re.match(r"^Secci[oó]n\s", t):
                    seccion = _etiqueta_seccion(t)
                    actual = _abrir(unidades, seccion, None)
                    continue
                m = _NUM_INICIAL.match(t)
                if m:
                    actual = _abrir(unidades, seccion, m.group(1))
                    actual[2].append(t)
                    continue
            if el.name == "table":
                celdas = el.find_all("td")
                m = _PUNTO_LABEL.match(_limpiar(celdas[0].get_text(" "))) if celdas else None
                if m:
                    actual = _abrir(unidades, seccion, m.group(1))
                    actual[2].append(_texto(celdas[1]) if len(celdas) > 1 else _texto(el))
                    continue
            if actual is None:
                actual = _abrir(unidades, seccion, None)
            actual[2].append(_texto(el))

        # Secciones/anexos sin puntos: un único fragmento (sin punto).
        con_puntos = {s for s, p, _ in unidades if p is not None}
        for sec, punto, textos in unidades:
            texto = _limpiar(" ".join(textos))
            if not texto:
                continue
            etiqueta_sec = f"sección {sec}" if sec else None
            if punto is not None:
                ap = f"{sec}.{punto}" if sec else punto
                partes = [f"Anexo {n}"] + ([etiqueta_sec] if etiqueta_sec else [])
                partes.append(f"punto {punto}")
                ident = f"anx-{n}" + (f"-sec-{sec}" if sec else "") + f"-p-{punto}"
            elif sec in con_puntos:
                ap = f"{sec}.intro" if sec else "intro"
                partes = (
                    [f"Anexo {n}"] + ([etiqueta_sec] if etiqueta_sec else []) + ["introducción"]
                )
                ident = f"anx-{n}" + (f"-sec-{sec}" if sec else "") + "-intro"
            else:
                ap = sec
                partes = [f"Anexo {n}"] + ([etiqueta_sec] if etiqueta_sec else [])
                ident = f"anx-{n}" + (f"-sec-{sec}" if sec else "")
            resultado.append(
                Fragmento(
                    id=ident,
                    tipo="anexo",
                    numero=n,
                    apartado=ap,
                    titulo_articulo=subtitulo,
                    texto=texto,
                    cita=", ".join(partes),
                    url_fuente=f"{URL_BASE}#{anx['id']}",
                )
            )
    return resultado


def parsear(html_path: str | Path) -> list[Fragmento]:
    """Lee el HTML de EUR-Lex y devuelve los fragmentos: considerandos, artículos y anexos."""
    soup = BeautifulSoup(Path(html_path).read_text(encoding="utf-8"), "lxml")
    return _considerandos(soup) + _articulos(soup) + _anexos(soup)
