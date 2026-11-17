"""Prueba manual del pipeline completo (llama a Cloudflare y a Neon).

Uso (desde backend/):
    uv run python scripts/preguntar.py "¿Qué prácticas de IA están prohibidas?"
"""

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.db import DatabaseError  # noqa: E402
from app.embeddings.base import EmbeddingError  # noqa: E402
from app.embeddings.factory import crear_embedder  # noqa: E402
from app.llm.base import LLMError  # noqa: E402
from app.llm.factory import crear_llm  # noqa: E402
from app.rag.pipeline import Pipeline  # noqa: E402
from app.rag.recuperacion import BuscadorPostgres  # noqa: E402
from app.schemas import limpiar_pregunta  # noqa: E402


class LLMDebug:
    """Envuelve un LLM y, tras cada intento, imprime la forma de la respuesta (sin secretos).

    Se muestra también cuando el intento falla al extraer el texto, y el texto extraído
    aunque luego no sea JSON válido (el pipeline lo descartará después).
    """

    def __init__(self, llm) -> None:
        self._llm = llm
        self.model = llm.model
        self._intento = 0

    def generar(self, system, usuario, esquema):
        self._intento += 1
        print(f"\n=== [debug] intento {self._intento} ===", file=sys.stderr)
        try:
            r = self._llm.generar(system, usuario, esquema)
        except LLMError as e:
            self._imprimir_diagnostico()
            print(f"[debug] LLMError: {e}", file=sys.stderr)
            raise
        self._imprimir_diagnostico()
        print(
            f"[debug] tokens (normalizados): entrada={r.tokens_entrada} salida={r.tokens_salida}",
            file=sys.stderr,
        )
        texto = r.texto
        print(f"[debug] texto extraído: {len(texto)} caracteres", file=sys.stderr)
        print(f"[debug] primeros 400: {texto[:400]!r}", file=sys.stderr)
        print(f"[debug] últimos 400:  {texto[-400:]!r}", file=sys.stderr)
        return r

    def _imprimir_diagnostico(self) -> None:
        d = getattr(self._llm, "diagnostico", None) or {}
        if not d:
            print("[debug] (sin diagnóstico: la respuesta no llegó a analizarse)", file=sys.stderr)
            return
        print(f"[debug] claves de result: {d.get('claves')}", file=sys.stderr)
        print(
            f"[debug] reasoning_effort enviado: {d.get('reasoning_effort_enviado')}",
            file=sys.stderr,
        )
        print(f"[debug] ruta del texto: {d.get('ruta', '(no reconocida)')}", file=sys.stderr)
        print(f"[debug] finish_reason/status: {d.get('finish')}", file=sys.stderr)
        print(f"[debug] usage: {d.get('usage')}", file=sys.stderr)
        if "output_items" in d:
            print(f"[debug] output items: {d['output_items']}", file=sys.stderr)
        if "razonamiento_chars" in d:
            print(f"[debug] razonamiento: {d['razonamiento_chars']} caracteres", file=sys.stderr)
        else:
            print("[debug] razonamiento: sin ítems de razonamiento", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pregunta al asistente sobre el AI Act.")
    parser.add_argument("pregunta")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="muestra, en cada intento, la forma de la respuesta de Cloudflare (sin secretos)",
    )
    args = parser.parse_args()
    # Evita que un carácter no representable en la consola de Windows corte la salida.
    sys.stdout.reconfigure(errors="replace")

    pregunta = limpiar_pregunta(args.pregunta)[:1000]
    llm = crear_llm()
    if args.debug:
        llm = LLMDebug(llm)
    pipeline = Pipeline(crear_embedder(max_retries=2), BuscadorPostgres(), llm)
    try:
        resultado = pipeline.responder(pregunta)
    except (LLMError, EmbeddingError, DatabaseError) as e:
        sys.exit(f"Error ({type(e).__name__}): {e}")

    r, c = resultado.respuesta, resultado.consumo
    print(f"Estado: {r.estado}\n")
    if r.mensaje:
        print(r.mensaje)
    for a in r.afirmaciones:
        marcas = "".join(f" [{n}]" for n in a.citas)
        print(f"- {a.texto}{marcas}")
    if r.citas:
        print("\nCitas:")
        for cita in r.citas:
            print(f"  [{cita.n}] {cita.cita} ({cita.tipo}, {cita.id})\n      {cita.url}")
    print(f"\n{r.aviso_legal}")
    print(
        f"\nMeta: modelo={r.meta.modelo} latencia={r.meta.latencia_ms} ms "
        f"similitud_max={r.meta.similitud_max}"
    )
    neuronas = "n/d" if c.neuronas is None else f"{c.neuronas:.1f}"
    print(
        f"Consumo: llamadas_llm={c.llamadas_llm} tokens_entrada={c.tokens_entrada} "
        f"tokens_salida={c.tokens_salida} neuronas≈{neuronas} (cuota diaria: 10000)"
    )
    print(
        f"Descartes: afirmaciones={resultado.afirmaciones_descartadas} "
        f"ids={resultado.ids_descartados}"
    )


if __name__ == "__main__":
    main()
