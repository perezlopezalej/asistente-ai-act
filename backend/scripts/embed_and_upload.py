"""Embebe data/processed/chunks.jsonl y hace upsert en la tabla fragmentos (Neon).

Se salta los fragmentos cuyo hash (texto embebido + modelo) no ha cambiado, así que se
puede relanzar sin gastar cuota. Requiere haber ejecutado db/migrations/001_fragmentos.sql.

Uso (desde backend/): uv run python scripts/embed_and_upload.py
"""

import sys
from pathlib import Path

from pgvector import Vector

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.db import conectar  # noqa: E402
from app.embeddings.factory import crear_embedder  # noqa: E402
from app.embeddings.texto import calcular_hash, texto_para_embedding  # noqa: E402
from app.ingest.chunks import leer_chunks  # noqa: E402

CHUNKS = RAIZ / "data" / "processed" / "chunks.jsonl"
LOTE = 64  # fragmentos por tanda (embebe y sube cada tanda, así un fallo no pierde todo)

UPSERT = """
insert into fragmentos (
    id, tipo, numero, apartado, titulo_articulo, capitulo, texto, cita, url_fuente,
    embedding, modelo_embedding, hash_contenido
) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
on conflict (id) do update set
    tipo = excluded.tipo,
    numero = excluded.numero,
    apartado = excluded.apartado,
    titulo_articulo = excluded.titulo_articulo,
    capitulo = excluded.capitulo,
    texto = excluded.texto,
    cita = excluded.cita,
    url_fuente = excluded.url_fuente,
    embedding = excluded.embedding,
    modelo_embedding = excluded.modelo_embedding,
    hash_contenido = excluded.hash_contenido,
    updated_at = now()
"""


def main() -> None:
    embedder = crear_embedder()
    modelo = embedder.model
    fragmentos = leer_chunks(CHUNKS)
    print(f"{len(fragmentos)} fragmentos en {CHUNKS.name}; modelo {modelo}")

    with conectar() as conn:
        existentes = dict(conn.execute("select id, hash_contenido from fragmentos").fetchall())

        pendientes = []  # (fragmento, texto embebido, hash)
        nuevos = actualizados = saltados = 0
        for fr in fragmentos:
            texto = texto_para_embedding(fr)
            h = calcular_hash(texto, modelo)
            if fr.id not in existentes:
                nuevos += 1
            elif existentes[fr.id] != h:
                actualizados += 1
            else:
                saltados += 1
                continue
            pendientes.append((fr, texto, h))

        print(f"Nuevos: {nuevos} · a actualizar: {actualizados} · sin cambios: {saltados}")

        subidos = 0
        for i in range(0, len(pendientes), LOTE):
            tanda = pendientes[i : i + LOTE]
            vectores = embedder.embed_documents([texto for _, texto, _ in tanda])
            filas = [
                (
                    fr.id,
                    fr.tipo,
                    fr.numero,
                    fr.apartado,
                    fr.titulo_articulo,
                    fr.capitulo,
                    fr.texto,  # el texto ORIGINAL; la cabecera solo se usa para embeber
                    fr.cita,
                    fr.url_fuente,
                    Vector(v),
                    modelo,
                    h,
                )
                for (fr, _, h), v in zip(tanda, vectores, strict=True)
            ]
            with conn.cursor() as cur:
                cur.executemany(UPSERT, filas)
            subidos += len(tanda)
            # flush: con stdout redirigido o en terminales de Windows las líneas pueden
            # quedarse en el búfer y verse tarde o incompletas.
            print(f"  progreso: {subidos}/{len(pendientes)}", flush=True)

        ids_jsonl = {fr.id for fr in fragmentos}
        huerfanos = sorted(set(existentes) - ids_jsonl)

    print("\nResumen")
    print(f"  nuevos:       {nuevos}")
    print(f"  actualizados: {actualizados}")
    print(f"  sin cambios:  {saltados}")
    if huerfanos:
        print(
            f"  AVISO: en la base de datos pero ya no en el jsonl (no se borran): {len(huerfanos)}"
        )
        print(f"    {', '.join(huerfanos[:10])}{' …' if len(huerfanos) > 10 else ''}")


if __name__ == "__main__":
    main()
