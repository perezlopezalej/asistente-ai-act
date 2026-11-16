"""Comprueba si Cloudflare trunca los textos largos al embeber.

Embebe art-5-ap-1 completo, sus primeros ~1.800 caracteres, sus últimos ~1.800 y sus
primeros N caracteres para N = 2500, 3500 y 4500, y muestra las similitudes coseno.

Criterio de truncado (prueba de identidad): si el modelo cortase la entrada en algún punto,
el texto completo y el prefijo que incluye ese punto producirían exactamente el mismo
embedding, porque el modelo vería el mismo texto en ambos casos. Por eso, si
cos(completo, primeros N) >= 0,9999 (idéntico salvo ruido numérico) para algún N, el
modelo está ignorando todo lo que hay a partir de ~N caracteres. El N más bajo que
coincide acota dónde se corta. Si ningún N llega a 0,9999, los tramos finales sí cambian
el vector y no hay truncado en ese rango. Un coseno alto pero < 0,9999 (p. ej. 0,95) es
normal: el principio domina el significado, pero no es identidad.

Uso (desde backend/): uv run python scripts/probar_truncado.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.embeddings.factory import crear_embedder  # noqa: E402
from app.embeddings.similitud import coseno  # noqa: E402
from app.embeddings.texto import texto_para_embedding  # noqa: E402
from app.ingest.chunks import leer_chunks  # noqa: E402

CHUNKS = RAIZ / "data" / "processed" / "chunks.jsonl"
ID = "art-5-ap-1"
TROZO = 1800
UMBRAL = 0.99
LIMITES = (2500, 3500, 4500)
IDENTICO = 0.9999


def main() -> None:
    fragmento = next((f for f in leer_chunks(CHUNKS) if f.id == ID), None)
    if fragmento is None:
        sys.exit(f"No se encuentra {ID} en {CHUNKS}")
    completo = texto_para_embedding(fragmento)
    print(f"{ID}: {len(completo)} caracteres (con cabecera)")

    # Un prefijo >= longitud del texto sería el propio texto: no aporta información.
    limites = [n for n in LIMITES if n < len(completo)]
    textos = [completo, completo[:TROZO], completo[-TROZO:]] + [completo[:n] for n in limites]
    v_completo, v_principio, v_final, *v_prefijos = crear_embedder().embed_documents(textos)

    sim_principio = coseno(v_completo, v_principio)
    sim_final = coseno(v_completo, v_final)
    print(f"cos(completo, primeros {TROZO}) = {sim_principio:.4f}")
    print(f"cos(completo, últimos  {TROZO}) = {sim_final:.4f}")

    identicos = []
    for n, v in zip(limites, v_prefijos, strict=True):
        sim = coseno(v_completo, v)
        print(f"cos(completo, primeros {n}) = {sim:.4f}")
        if sim >= IDENTICO:
            identicos.append(n)

    if identicos:
        print(
            f"\nTRUNCADO: el embedding del texto completo es idéntico (>= {IDENTICO}) al de los "
            f"primeros {min(identicos)} caracteres. El modelo ignora el texto a partir de "
            f"~{min(identicos)} caracteres: el final de los fragmentos largos no cuenta."
        )
    elif sim_principio > UMBRAL:
        print(
            f"\nAVISO: completo casi igual a principio (> {UMBRAL}) pero sin identidad con "
            "ningún prefijo mayor. Revisa los valores antes de concluir."
        )
    else:
        print("\nOK: ningún prefijo reproduce el embedding completo; no hay indicio de truncado.")


if __name__ == "__main__":
    main()
