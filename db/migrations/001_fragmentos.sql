-- 001_fragmentos.sql
-- Tabla de fragmentos del AI Act con su embedding (bge-m3, 1024 dim) y búsqueda por coseno.
-- Se ejecuta a mano en el SQL Editor de Neon (primero en la rama "development").
-- Es una migración de una sola pasada: si hay que repetirla, borra antes la tabla y la función.

create extension if not exists vector;

create table fragmentos (
    id text primary key,                 -- 'art-5-ap-1', 'rct-3', 'anx-I-sec-A'
    tipo text not null check (tipo in ('articulo', 'considerando', 'anexo')),
    numero text not null,
    apartado text,
    titulo_articulo text,
    capitulo text,
    texto text not null,                 -- texto ORIGINAL (sin la cabecera de contexto)
    cita text not null,
    url_fuente text not null,
    embedding vector(1024) not null,
    modelo_embedding text not null,
    hash_contenido text not null,        -- sha256(modelo + texto embebido): detecta cambios
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- HNSW con distancia coseno (operador <=>).
create index fragmentos_embedding_hnsw
    on fragmentos using hnsw (embedding vector_cosine_ops);

-- HNSW es un índice APROXIMADO: devuelve ~hnsw.ef_search candidatos (40 por defecto) y el
-- WHERE se aplica DESPUÉS. Con tipos = ['articulo'] podrían salir menos de match_count
-- filas aunque existan más. Se corrige según la versión de pgvector instalada:
--   >= 0.8: hnsw.iterative_scan = relaxed_order  -> el índice sigue explorando hasta reunir
--           match_count filas que cumplan el filtro (tope: hnsw.max_scan_tuples = 20000,
--           de sobra para ~850 filas).
--   <  0.8: hnsw.ef_search = 100                 -> más candidatos antes de filtrar.
-- relaxed_order no garantiza el orden exacto, por eso la función reordena en una CTE.
-- La cláusula SET se fija al crear la función, así que el DO elige la variante correcta.
do $migracion$
declare
    version_vector text;
    ajuste text;
begin
    select extversion into version_vector from pg_extension where extname = 'vector';

    if string_to_array(version_vector, '.')::int[] >= array[0, 8] then
        ajuste := 'set hnsw.iterative_scan = relaxed_order';
    else
        ajuste := 'set hnsw.ef_search = 100';
    end if;

    execute format($f$
        create function buscar_fragmentos(
            query_embedding vector(1024),
            match_count int default 5,
            tipos text[] default null
        )
        returns table (
            id text,
            tipo text,
            numero text,
            apartado text,
            titulo_articulo text,
            capitulo text,
            texto text,
            cita text,
            url_fuente text,
            similitud double precision
        )
        language sql stable
        %s
        as $body$
            with candidatos as materialized (
                select f.*, f.embedding <=> query_embedding as distancia
                from fragmentos f
                where tipos is null or f.tipo = any(tipos)
                order by f.embedding <=> query_embedding
                limit match_count
            )
            select c.id, c.tipo, c.numero, c.apartado, c.titulo_articulo, c.capitulo,
                   c.texto, c.cita, c.url_fuente,
                   (1 - c.distancia)::double precision as similitud
            from candidatos c
            order by c.distancia
        $body$
    $f$, ajuste);
end
$migracion$;
