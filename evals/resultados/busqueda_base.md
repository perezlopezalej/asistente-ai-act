# Evaluación de la búsqueda (sin LLM)

Generado 2026-11-17T19:05:15+00:00 · embeddings `@cf/baai/bge-m3` · k = 5 y 20 (artículos + anexos). 🅾 = pregunta afectada por el AI Omnibus, que el corpus no incluye.

## Métricas (preguntas con ids_relevantes)

| grupo | n | hit@5 | recall@5 | esenciales@5 | MRR |
|---|---|---|---|---|---|
| global | 29 | 0.862 | 0.559 | 0.483 | 0.665 |
| directa | 15 | 0.933 | 0.733 | 0.600 | 0.746 |
| coloquial | 10 | 0.900 | 0.468 | 0.400 | 0.581 |
| caso_concreto | 4 | 0.500 | 0.133 | 0.250 | 0.569 |

Excluyendo las preguntas 🅾:

| grupo | n | hit@5 | recall@5 | esenciales@5 | MRR |
|---|---|---|---|---|---|
| global | 25 | 0.840 | 0.535 | 0.480 | 0.691 |
| directa | 13 | 0.923 | 0.731 | 0.615 | 0.784 |
| coloquial | 8 | 0.875 | 0.418 | 0.375 | 0.601 |
| caso_concreto | 4 | 0.500 | 0.133 | 0.250 | 0.569 |

## Fallos (faltan esenciales en el top 5)

| id | tipo | pregunta | esenciales que faltan (posición en top 20) |
|---|---|---|---|
| g-001 | directa | ¿Qué características debe tener un software para considerarse un «sistema de IA» según el Reglamento? | `art-3-ap-1`: 9 |
| g-002 | directa | ¿Quién es un «responsable del despliegue» y en qué se diferencia de un proveedor? | `art-3-ap-3`: 14 |
| g-004 | directa | ¿En qué supuestos excepcionales pueden las fuerzas de seguridad identificar personas en tiempo real por biometría en lugares públicos y quién tiene que autorizarlo? | `art-5-ap-1`: no aparece |
| g-006 | directa | ¿Qué usos de la IA en el ámbito educativo se consideran de alto riesgo? | `art-6-ap-2`: no aparece |
| g-008 | directa | ¿Qué tienen que hacer quienes utilizan un sistema de IA de alto riesgo en cuanto a supervisión humana y vigilancia de su funcionamiento? | `art-26-ap-2`: 17 |
| g-013 🅾 | directa | ¿Desde cuándo se aplican las normas de alto riesgo para sistemas de IA integrados en productos regulados del anexo I? | `art-113`: no aparece |
| g-017 | coloquial | Usamos un programa que filtra los currículums y nos dice a quién llamar para entrevista, ¿hay algún problema con eso? | `art-6-ap-2`: no aparece |
| g-018 | coloquial | Queremos poner cámaras en la tienda que reconozcan a los clientes que ya nos han robado antes, ¿es legal? | `anx-III-p-1`: no aparece |
| g-020 | coloquial | Mi empresa da préstamos pequeños y una IA decide si se los damos a la gente o no, ¿qué tengo que cumplir? | `anx-III-p-5`: 18, `art-6-ap-2`: no aparece, `art-27-ap-1`: no aparece |
| g-021 | coloquial | ¿Puedo usar una app que mira la cara de mis empleados por la cámara para saber si están contentos o estresados? | `art-5-ap-1`: 9 |
| g-022 🅾 | coloquial | En la oficina usamos ChatGPT para todo, ¿eso nos obliga a algo a nosotros como empresa? | `art-4`: no aparece, `art-3-ap-4`: no aparece |
| g-025 | coloquial | Un cliente nos ha pedido un vídeo con la voz de su jefe diciendo cosas que no ha dicho para una campaña, ¿podemos hacerlo? | `art-3-ap-60`: no aparece |
| g-034 | caso_concreto | Somos una aseguradora y vamos a usar un sistema de IA que calcula el riesgo y fija el precio de los seguros de vida y de salud de nuestros clientes. ¿Qué criterios del Reglamento se nos aplican? | `anx-III-p-5`: 9, `art-6-ap-2`: no aparece, `art-27-ap-1`: no aparece |
| g-036 | caso_concreto | Una universidad privada quiere usar un sistema de IA para detectar comportamientos prohibidos de los estudiantes durante los exámenes online. ¿Es de alto riesgo y qué debe hacer la universidad? | `anx-III-p-3`: 6, `art-6-ap-2`: no aparece |
| g-037 | caso_concreto | Una empresa tecnológica europea ha entrenado su propio modelo de IA de uso general con una potencia de cálculo de 3·10^25 operaciones de coma flotante y quiere ofrecerlo a terceros en la UE. ¿Qué obligaciones tiene? | `art-53-ap-1`: 10, `art-55-ap-1`: 6 |

## Calibración del umbral

**Recomendado: 0.46** — el umbral más alto con como mucho 1 rechazo injusto. En ese punto: 0 rechazos injustos (ninguno) y 9 aceptaciones indebidas (g-030 (0.605), g-031 (0.537), g-028 (0.532), g-029 (0.531), g-027 (0.516), g-039 (0.504), g-040 (0.501), g-026 (0.501), g-033 (0.487)). Subir más el umbral rechazaría más preguntas legítimas; bajarlo solo deja pasar más preguntas sin respuesta (que la barrera 2, la verificación de citas, aún puede frenar).

Similitud máxima de las 29 preguntas con respuesta: mín. 0.464, máx. 0.806. De las 11 sin respuesta: mín. 0.257, máx. 0.605.

| umbral | rechazos injustos | aceptaciones |
|---|---|---|
| 0.40 | 0 | 10 |
| 0.41 | 0 | 10 |
| 0.42 | 0 | 10 |
| 0.43 | 0 | 10 |
| 0.44 | 0 | 10 |
| 0.45 | 0 | 10 |
| 0.46 ← recomendado | 0 | 9 |
| 0.47 | 1 | 9 |
| 0.48 | 1 | 9 |
| 0.49 | 4 | 8 |
| 0.50 | 5 | 8 |
| 0.51 | 7 | 5 |
| 0.52 | 8 | 4 |
| 0.53 | 8 | 4 |
| 0.54 | 8 | 1 |
| 0.55 | 8 | 1 |
| 0.56 | 8 | 1 |
| 0.57 | 8 | 1 |
| 0.58 | 8 | 1 |
| 0.59 | 10 | 1 |
| 0.60 | 10 | 1 |
| 0.61 | 10 | 0 |
| 0.62 | 11 | 0 |
| 0.63 | 12 | 0 |
| 0.64 | 13 | 0 |
| 0.65 | 15 | 0 |
| 0.66 | 16 | 0 |
| 0.67 | 17 | 0 |
| 0.68 | 20 | 0 |
| 0.69 | 21 | 0 |
| 0.70 | 22 | 0 |

### Similitud máxima por pregunta

| id | tipo | sim_max | debe abstenerse |
|---|---|---|---|
| g-032 | sin_respuesta | 0.257 | sí |
| g-038 | adversaria | 0.459 | sí |
| g-022 🅾 | coloquial | 0.464 | no |
| g-018 | coloquial | 0.480 | no |
| g-025 | coloquial | 0.483 | no |
| g-003 | directa | 0.487 | no |
| g-033 | sin_respuesta | 0.487 | sí |
| g-017 | coloquial | 0.490 | no |
| g-016 | coloquial | 0.500 | no |
| g-026 | sin_respuesta | 0.501 | sí |
| g-040 | adversaria | 0.501 | sí |
| g-039 | adversaria | 0.504 | sí |
| g-021 | coloquial | 0.509 | no |
| g-023 🅾 | coloquial | 0.515 | no |
| g-027 | sin_respuesta | 0.516 | sí |
| g-029 | sin_respuesta | 0.531 | sí |
| g-028 | sin_respuesta | 0.532 | sí |
| g-031 | sin_respuesta | 0.537 | sí |
| g-009 | directa | 0.585 | no |
| g-035 | caso_concreto | 0.587 | no |
| g-030 | sin_respuesta | 0.605 | sí |
| g-006 | directa | 0.610 | no |
| g-036 | caso_concreto | 0.626 | no |
| g-037 | caso_concreto | 0.637 | no |
| g-019 | coloquial | 0.641 | no |
| g-004 | directa | 0.643 | no |
| g-020 | coloquial | 0.659 | no |
| g-012 | directa | 0.667 | no |
| g-024 | coloquial | 0.672 | no |
| g-034 | caso_concreto | 0.674 | no |
| g-001 | directa | 0.678 | no |
| g-002 | directa | 0.681 | no |
| g-014 | directa | 0.692 | no |
| g-013 🅾 | directa | 0.703 | no |
| g-005 | directa | 0.714 | no |
| g-011 | directa | 0.732 | no |
| g-008 | directa | 0.766 | no |
| g-007 | directa | 0.780 | no |
| g-015 🅾 | directa | 0.806 | no |
| g-010 | directa | 0.806 | no |

## Comprobación del índice aproximado (HNSW)

El top 5 de la búsqueda con k=5 coincide con el prefijo de la de k=20 en 40 de 40 preguntas. Las métricas @5 usan la búsqueda con k=5; las posiciones de los fallos y el MRR, la de k=20.
