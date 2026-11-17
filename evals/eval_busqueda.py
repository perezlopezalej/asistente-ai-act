"""Evalúa SOLO la búsqueda (sin LLM) y calibra UMBRAL_SIMILITUD con `evals/golden.jsonl`.

Usa el mismo código del pipeline (embedder + BuscadorPostgres). Requiere .env (Cloudflare y
Neon). Los embeddings de las preguntas se cachean en `evals/cache/` (modelo + texto).

Uso (desde `backend/`):
    uv run python ../evals/eval_busqueda.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GOLDEN = RAIZ / "evals" / "golden.jsonl"
CACHE = RAIZ / "evals" / "cache" / "embeddings.json"
SALIDA = RAIZ / "evals" / "resultados"

K_BASE = 5
K_AMPLIO = 20
UMBRALES = [round(0.40 + i * 0.01, 2) for i in range(31)]  # 0,40 … 0,70
MAX_RECHAZOS_INJUSTOS = 1
TIPOS_CON_IDS = ("directa", "coloquial", "caso_concreto")


# --- métricas (puras) ---


def posiciones(ids: list[str], ranking: list[str]) -> dict[str, int | None]:
    """Posición (1-based) de cada id en el ranking, o None si no aparece."""
    return {i: (ranking.index(i) + 1 if i in ranking else None) for i in ids}


def hit_en_k(relevantes: list[str], ranking: list[str], k: int) -> bool:
    return any(i in ranking[:k] for i in relevantes)


def recall_en_k(relevantes: list[str], ranking: list[str], k: int) -> float:
    if not relevantes:
        return 0.0
    return sum(1 for i in relevantes if i in ranking[:k]) / len(relevantes)


def todos_esenciales_en_k(esenciales: list[str], ranking: list[str], k: int) -> bool:
    return all(i in ranking[:k] for i in esenciales)


def rr_primer_esencial(esenciales: list[str], ranking: list[str]) -> float:
    """1/posición del primer esencial que aparece en el ranking; 0 si ninguno aparece."""
    pos = [p for p in posiciones(esenciales, ranking).values() if p is not None]
    return 1 / min(pos) if pos else 0.0


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def metricas(filas: list[dict]) -> dict:
    """Cada fila: ids_relevantes, ids_esenciales, ranking5 (k=5) y ranking20 (k=20)."""
    return {
        "n": len(filas),
        "hit@5": _media([float(hit_en_k(f["ids_relevantes"], f["ranking5"], 5)) for f in filas]),
        "recall@5": _media([recall_en_k(f["ids_relevantes"], f["ranking5"], 5) for f in filas]),
        "esenciales@5": _media(
            [float(todos_esenciales_en_k(f["ids_esenciales"], f["ranking5"], 5)) for f in filas]
        ),
        "mrr": _media([rr_primer_esencial(f["ids_esenciales"], f["ranking20"]) for f in filas]),
    }


def metricas_por_tipo(filas: list[dict]) -> dict[str, dict]:
    res = {"global": metricas(filas)}
    for tipo in TIPOS_CON_IDS:
        sub = [f for f in filas if f["tipo"] == tipo]
        if sub:
            res[tipo] = metricas(sub)
    return res


def curva_umbral(
    sims_con_respuesta: list[float], sims_abstencion: list[float], umbrales: list[float] = UMBRALES
) -> list[dict]:
    """Por umbral: rechazos injustos (con respuesta y sim < umbral) y aceptaciones
    (debe abstenerse y sim >= umbral). Misma condición que el pipeline (rechaza si < umbral)."""
    return [
        {
            "umbral": u,
            "rechazos_injustos": sum(1 for s in sims_con_respuesta if round(s, 6) < u),
            "aceptaciones": sum(1 for s in sims_abstencion if round(s, 6) >= u),
        }
        for u in umbrales
    ]


def recomendar_umbral(curva: list[dict], max_rechazos: int = MAX_RECHAZOS_INJUSTOS) -> float | None:
    """Entre los umbrales con el mínimo de rechazos injustos, el más alto.

    Solo se admite más de 0 rechazos si ningún umbral tiene 0, y nunca más de `max_rechazos`
    (None si el mínimo lo supera).
    """
    if not curva:
        return None
    minimo = min(c["rechazos_injustos"] for c in curva)
    if minimo > max_rechazos:
        return None
    return max(c["umbral"] for c in curva if c["rechazos_injustos"] == minimo)


# --- caché de embeddings ---


def clave_cache(modelo: str, texto: str) -> str:
    return hashlib.sha256(f"{modelo}\n{texto}".encode()).hexdigest()


def vectores_con_cache(
    textos: list[str], modelo: str, embedder, ruta: Path = CACHE
) -> list[list[float]]:
    cache: dict[str, list[float]] = {}
    if ruta.exists():
        cache = json.loads(ruta.read_text(encoding="utf-8"))
    nuevo = False
    for t in textos:
        k = clave_cache(modelo, t)
        if k not in cache:
            cache[k] = embedder.embed_query(t)
            nuevo = True
    if nuevo:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(cache), encoding="utf-8")
    return [cache[clave_cache(modelo, t)] for t in textos]


# --- ejecución ---


def _cargar_golden() -> list[dict]:
    spec = importlib.util.spec_from_file_location(
        "validar_golden", RAIZ / "evals/validar_golden.py"
    )
    vg = importlib.util.module_from_spec(spec)
    sys.modules["validar_golden"] = vg
    spec.loader.exec_module(vg)
    return vg.cargar_jsonl(GOLDEN)


def ejecutar() -> dict:
    sys.path.insert(0, str(RAIZ / "backend"))
    from app.config import settings
    from app.embeddings.factory import crear_embedder
    from app.rag.recuperacion import BuscadorPostgres

    golden = _cargar_golden()
    embedder = crear_embedder()
    vectores = vectores_con_cache(
        [g["pregunta"] for g in golden], settings.embedding_model, embedder
    )
    buscador = BuscadorPostgres()

    filas = []
    for g, v in zip(golden, vectores, strict=True):
        r5 = buscador.buscar(v, K_BASE, 0)
        r20 = buscador.buscar(v, K_AMPLIO, 0)
        ids5 = [f.id for f in r5.citables]
        ids20 = [f.id for f in r20.citables]
        filas.append(
            {
                "id": g["id"],
                "pregunta": g["pregunta"],
                "tipo": g["tipo"],
                "debe_abstenerse": g["debe_abstenerse"],
                "afectada_omnibus": bool(g.get("afectada_omnibus")),
                "ids_relevantes": g["ids_relevantes"],
                "ids_esenciales": g["ids_esenciales"],
                "similitud_max": round(r20.similitud_max, 4),
                "ranking5": ids5,
                "ranking20": ids20,
                "similitudes20": [round(f.similitud, 4) for f in r20.citables],
                "k5_coincide_con_prefijo_k20": ids5 == ids20[:K_BASE],
            }
        )
    return construir_resultado(filas, settings.embedding_model)


def construir_resultado(filas: list[dict], modelo: str) -> dict:
    con_ids = [f for f in filas if f["ids_relevantes"]]
    sin_omnibus = [f for f in con_ids if not f["afectada_omnibus"]]
    fallos = []
    for f in con_ids:
        if not todos_esenciales_en_k(f["ids_esenciales"], f["ranking5"], K_BASE):
            pos = posiciones(f["ids_esenciales"], f["ranking20"])
            faltan = {i: pos[i] for i in f["ids_esenciales"] if i not in f["ranking5"]}
            fallos.append({"id": f["id"], "faltan": faltan})
    con_resp = [f["similitud_max"] for f in filas if not f["debe_abstenerse"]]
    sin_resp = [f["similitud_max"] for f in filas if f["debe_abstenerse"]]
    curva = curva_umbral(con_resp, sin_resp)
    return {
        "generado": datetime.now(UTC).isoformat(timespec="seconds"),
        "modelo_embeddings": modelo,
        "k": [K_BASE, K_AMPLIO],
        "metricas": metricas_por_tipo(con_ids),
        "metricas_sin_omnibus": metricas_por_tipo(sin_omnibus),
        "fallos": fallos,
        "curva_umbral": curva,
        "umbral_recomendado": recomendar_umbral(curva),
        "k5_coincide_con_prefijo_k20": sum(f["k5_coincide_con_prefijo_k20"] for f in filas),
        "preguntas": filas,
    }


# --- informe .md ---


def _f(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def _tabla_metricas(m: dict) -> list[str]:
    out = ["| grupo | n | hit@5 | recall@5 | esenciales@5 | MRR |", "|---|---|---|---|---|---|"]
    for grupo, v in m.items():
        out.append(
            f"| {grupo} | {v['n']} | {_f(v['hit@5'])} | {_f(v['recall@5'])} | "
            f"{_f(v['esenciales@5'])} | {_f(v['mrr'])} |"
        )
    return out


def generar_md(res: dict) -> str:
    por_id = {f["id"]: f for f in res["preguntas"]}
    L = ["# Evaluación de la búsqueda (sin LLM)", ""]
    L += [
        f"Generado {res['generado']} · embeddings `{res['modelo_embeddings']}` · "
        f"k = {res['k'][0]} y {res['k'][1]} (artículos + anexos). 🅾 = pregunta afectada por el "
        "AI Omnibus, que el corpus no incluye.",
        "",
        "## Métricas (preguntas con ids_relevantes)",
        "",
        *_tabla_metricas(res["metricas"]),
        "",
        "Excluyendo las preguntas 🅾:",
        "",
        *_tabla_metricas(res["metricas_sin_omnibus"]),
        "",
        "## Fallos (faltan esenciales en el top 5)",
        "",
    ]
    if res["fallos"]:
        L += [
            "| id | tipo | pregunta | esenciales que faltan (posición en top 20) |",
            "|---|---|---|---|",
        ]
        for fa in res["fallos"]:
            p = por_id[fa["id"]]
            marca = " 🅾" if p["afectada_omnibus"] else ""
            falt = ", ".join(
                f"`{i}`: {pos if pos else 'no aparece'}" for i, pos in fa["faltan"].items()
            )
            L.append(
                f"| {fa['id']}{marca} | {p['tipo']} | {p['pregunta'].replace('|', '/')} | {falt} |"
            )
    else:
        L.append("Ninguno.")
    L += ["", "## Calibración del umbral", ""]
    L += _seccion_umbral(res, por_id)
    n = len(res["preguntas"])
    L += [
        "",
        "## Comprobación del índice aproximado (HNSW)",
        "",
        f"El top 5 de la búsqueda con k=5 coincide con el prefijo de la de k=20 en "
        f"{res['k5_coincide_con_prefijo_k20']} de {n} preguntas. Las métricas @5 usan la "
        "búsqueda con k=5; las posiciones de los fallos y el MRR, la de k=20.",
    ]
    return "\n".join(L) + "\n"


def _seccion_umbral(res: dict, por_id: dict) -> list[str]:
    filas = res["preguntas"]
    rec = res["umbral_recomendado"]
    con = sorted((f for f in filas if not f["debe_abstenerse"]), key=lambda f: f["similitud_max"])
    sin = sorted((f for f in filas if f["debe_abstenerse"]), key=lambda f: -f["similitud_max"])
    L = []
    if rec is None:
        L.append("Ningún umbral del rango cumple el criterio.")
    else:
        c = next(x for x in res["curva_umbral"] if x["umbral"] == rec)
        inj = [f"{f['id']} ({f['similitud_max']:.3f})" for f in con if f["similitud_max"] < rec]
        acep = [f"{f['id']} ({f['similitud_max']:.3f})" for f in sin if f["similitud_max"] >= rec]
        L += [
            f"**Recomendado: {rec:.2f}** — el umbral más alto con como mucho "
            f"{MAX_RECHAZOS_INJUSTOS} rechazo injusto. En ese punto: {c['rechazos_injustos']} "
            f"rechazos injustos ({', '.join(inj) or 'ninguno'}) y {c['aceptaciones']} "
            f"aceptaciones indebidas ({', '.join(acep) or 'ninguna'}). Subir más el umbral "
            "rechazaría más preguntas legítimas; bajarlo solo deja pasar más preguntas sin "
            "respuesta (que la barrera 2, la verificación de citas, aún puede frenar).",
            "",
            f"Similitud máxima de las {len(con)} preguntas con respuesta: mín. "
            f"{con[0]['similitud_max']:.3f}, máx. {con[-1]['similitud_max']:.3f}. "
            f"De las {len(sin)} sin respuesta: mín. {sin[-1]['similitud_max']:.3f}, máx. "
            f"{sin[0]['similitud_max']:.3f}.",
            "",
        ]
    L += ["| umbral | rechazos injustos | aceptaciones |", "|---|---|---|"]
    for c in res["curva_umbral"]:
        mark = " ← recomendado" if c["umbral"] == rec else ""
        L.append(f"| {c['umbral']:.2f}{mark} | {c['rechazos_injustos']} | {c['aceptaciones']} |")
    L += [
        "",
        "### Similitud máxima por pregunta",
        "",
        "| id | tipo | sim_max | debe abstenerse |",
        "|---|---|---|---|",
    ]
    for f in sorted(filas, key=lambda f: f["similitud_max"]):
        marca = " 🅾" if f["afectada_omnibus"] else ""
        L.append(
            f"| {f['id']}{marca} | {f['tipo']} | {f['similitud_max']:.3f} | "
            f"{'sí' if f['debe_abstenerse'] else 'no'} |"
        )
    return L


def main() -> int:
    res = ejecutar()
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "busqueda_base.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    (SALIDA / "busqueda_base.md").write_text(generar_md(res), encoding="utf-8", newline="\n")
    print(
        f"escrito evals/resultados/busqueda_base.{{json,md}} — umbral: {res['umbral_recomendado']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
