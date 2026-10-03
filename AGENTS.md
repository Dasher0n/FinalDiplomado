# Sommelier de juegos de mesa

Documento vivo del proyecto. Se actualiza al cerrar cada fase.

## Comandos verificados

| Comando | Resultado |
| --- | --- |
| `uv run --no-project python scripts/verificar_fase_0.py` | Verifica dependencias y artefactos locales de la Fase 0. |
| `uv run --env-file .env python scripts/verificar_fase_0.py --web-search` | Ejecuta la unica llamada real autorizada de `web_search` para la Fase 0. Lo ejecuta Miguel para cargar la clave sin que el agente lea `.env`. |

## Stack verificado

- Python `3.14.7`.
- `scikit-learn==1.9.0`, `scipy==1.18.0`, `numpy==2.5.2` y `pandas==3.0.5` instalan y cargan correctamente en Python 3.14.
- `openai==3.13.0` y `pydantic-settings==2.15.0` se instalaron para la verificacion de Fase 0, siguiendo las versiones del repositorio de referencia.

## Artefactos verificados

- `catalogo.csv` tiene 30,146 filas y 60 columnas.
- Las columnas de precio autorizadas son `precio_usd`, `n_ofertas_us_stock`, `precio_confiable`, `fecha_precio` y `bgp_url`.
- Las columnas de precio con sufijos `_x` y `_y` existen y son residuos de merges. No se siembran ni se usan.
- `image_url` usa `__itemrep` y `Thumbnail` usa `__micro`. La UI debe usar `image_url`.
- 8,503 filas de `bgp_url` contienen el marcador codificado `site_https%3A%2F%2Fgithub.com%2FTU_USUARIO%2FFinalDiplomado` dentro de `utm_source`.
- Al servir un `bgp_url`, se debe decodificar el valor de `utm_source`, sustituir su valor completo por `BGP_SITENAME` y reconstruir la URL. No hacer un reemplazo de texto sobre la URL codificada.
- `preproceso.pkl` carga como diccionario con vectorizadores, escalador, limites, pesos, umbrales, reglas de interaccion, familias, temas y niveles de jugadores.
- Los bloques son `X_mecanicas=(30146, 193)`, `X_tematica=(30146, 83)`, `X_ocasion=(30146, 5)` y `X_interaccion=(30146, 2)`.
- Los vocabularios son 193 mecanicas y 83 categorias.
- Pesos: mecanicas `0.40`, ocasion `0.10`, interaccion `0.15`, tematica `0.35`.
- Umbrales exactos: parecido `0.4165141436034246`, redundante `0.7729157377558937`, ofertas de precio `2`.
- `players_hi` se limita a 10 en el vector. El nivel de cobertura `7 o mas` conserva el rango 7 a 999.
- Las filas de las cuatro matrices coinciden con el orden de `catalogo.csv`.

## Preproceso verificado

- `mlb_mecanicas` y `mlb_tematica`: `sklearn.preprocessing._label.MultiLabelBinarizer`.
- `tfidf_mecanicas` y `tfidf_tematica`: `sklearn.feature_extraction.text.TfidfTransformer`.
- `escalador_ocasion`: `sklearn.preprocessing._data.MinMaxScaler`, ajustado y utilizable para transformar los cinco campos de ocasion.
- `cols_ocasion`: `list`; `limites_ocasion`, `pesos`, `familias`, `respaldo_cat`, `temas` y `niveles_jugadores`: `dict`.
- `umbral_redundante` y `umbral_parecido`: `float`; `umbral_ofertas_precio`: `int`; `sin_tema`: `str`.
- `mec_directa`, `mec_indirecta`, `mec_combate`, `cat_combate`, `cat_directa` y `mec_traicion`: `set`.
- No contiene un `sklearn.impute.KNNImputer`, otro imputador de peso ni los datos ajustados necesarios para un KNN. No es posible imputar el peso de un juego nuevo sin entrenar o recibir un artefacto adicional. La vectorizacion web de Fase 5 queda bloqueada en ese caso, como exige el requerimiento.
- Miguel agregara `artefactos/imputador_ocasion.pkl` como artefacto aparte. La vectorizacion web de Fase 5 depende de ese archivo y no se debe inventar ni reentrenar un imputador en la aplicacion.

## Decisiones verificadas

- La marca visible de la aplicacion es `Wise Dice`, con el subtitulo "Tu asesor de ludoteca". Los nombres internos del repositorio y servicios no cambian.
- La cascada de BGG fuera del ranking esta omitida por decision de producto. La aplicacion no hara peticiones a BoardGameGeek.
- La unica llamada real de la Fase 0 fue ejecutada por Miguel con `web_search` y `tool_choice: "required"`. El modelo resuelto fue `gpt-5.1-2025-11-13` y devolvio cinco citas para Metropoli de Ideotas Juegos. Esto verifica que `gpt-5.1` admite la herramienta hospedada `web_search`.
- La clave de OpenAI se carga en la aplicacion con `pydantic-settings` desde el entorno y `env_file=".env"`; se modela como `SecretStr`, nunca se imprime ni persiste.
- Excepcion aprobada para Fase 0: no se ejecuta `make lint` porque el Makefile pertenece al andamiaje de Fase 1 y aun no existe.
- La busqueda automatica de secretos debe excluir `artefactos/` y las URLs de imagen de `cf.geekdo-images.com`, o exigir el patron completo de una clave con `sk-` seguido de al menos 20 caracteres sin guiones intermedios de URL. Se confirmo un falso positivo dentro de una URL de imagen del catalogo.
- Decisiones de entrega: Bloque 1 ajusta cobertura y plan; Bloque 2 incorpora perfiles B2B y Cafe demo; Bloque 3 implementa la Fase 4; Bloque 4 considera Fase 5 solo si hay tiempo. Cada bloque se cierra y reporta por separado.
- Cambio de alcance del plan: la interfaz y las tools del chat solo exponen planes por numero de juegos con tres opciones disjuntas. El modo precio se conserva en backend y pruebas, pero no se expone. Los precios de BoardGamePrices quedan como referencia en el detalle.

## Fase 1

- El backend usa FastAPI, SQLAlchemy async y SQLite con `foreign_keys=ON`, WAL y fechas UTC.
- El esquema incluye catalogo, colecciones, precios de usuario, vectores extra, alias, chat, trazas agenticas y cache de busqueda web.
- `make seed` es idempotente: importa 30,146 juegos, crea el usuario demo y siembra sus 12 juegos. Una segunda ejecucion no inserta filas nuevas.
- El frontend es Angular 22 standalone con Tailwind v4 y TypeScript 6.0.x. `npm install --force` es necesario por el peer de `openapi-typescript`.
- `make contracts` genera `frontend/src/app/core/api/schema.d.ts` desde OpenAPI.
- La Fase 1b aprobada se implementara despues de aprobar el cierre de esta fase. Incluira la vitrina y los endpoints de solo lectura del catalogo y la coleccion.

## Fase 1b

- Los endpoints de solo lectura son `GET /collection`, `GET /games?q=` y `GET /games/{id}` bajo `/api/v1`.
- La Ludoteca consume solo estos endpoints y muestra la coleccion sembrada en estantes agrupables, buscador de catalogo y detalle basico con precio y enlace a BoardGamePrices.
- `bgp_url` sustituye `utm_source` de forma estructurada y usa `BGP_SITENAME` sin reemplazos de texto sobre la URL codificada.
- `docker compose down && docker compose up --build -d` inicia backend saludable en `http://localhost:8000` y frontend en `http://localhost:8080`. El volumen recreado se siembra con 30,146 juegos y la coleccion demo.
- La imagen backend no incluye `curl`. El healthcheck se define solo en `docker-compose.yml` y usa `python` con `urllib.request` contra `127.0.0.1`, con timeout de 3 segundos.

## Fase 2

- FastAPI carga en memoria los cuatro bloques de vectores al arrancar; se indexan con `fila_vector`.
- Las nueve pruebas doradas usan IDs de BGG fijos y pasan con tolerancia de 0.01. El par `7 Wonders` (`68448`) y `7 Wonders Duel` (`173346`) dio mecanicas `0.6479`, ocasion `0.9379`, interaccion `0.8750`, tematica `1.0000` y total `0.8342`.
- El motor implementa similitud por bloques con renormalizacion, redundancia, cobertura de seis ejes, compra greedy en modos juego y precio, disponibilidad y resolucion local ambigua.
- El plan por precio con presupuesto USD 60, `n=5`, `users_rated_min=1000`, `average_min=0` y sin ejes ignorados reproduce el anexo: Cosmic Wimpout, The Werewolves of Miller's Hollow, Kingdom Legacy, Flip 7 y Trek 12. Costo USD `51.765`; valor pendiente `0.183333...`.
- `Wingspan` y `Wyrmspan` comparten `product_line` y reimplementacion en el catalogo. La regla exacta los considera relacionados; frente a una coleccion con Wingspan, Wyrmspan cubre huecos y el veredicto es `parecido_pero_cubre_hueco`.
- Decision de producto: frente a la coleccion demo, Wyrmspan es `redundante` por regla exacta, porque reimplementa Wingspan y comparte su linea de producto, aunque su similitud es 0.70. Esta decision prevalece sobre el punto 1 del guion de demo de la seccion 11.

## Fase 3 y 3b

- La API expone coleccion editable y los cuatro endpoints del motor bajo `/api/v1`.
- Los contratos TypeScript se regeneran desde OpenAPI con `make contracts`.
- Cobertura, plan de compra, detalle evaluable, disponibilidad y la vista previa de Chat consumen datos reales del motor.
- Chart.js se usa directamente para el radar de cobertura.

## Bloque 2

- Cafe demo usa 40 juegos populares ligeros o medios y el perfil Cafe define metas versionadas por nivel. La meta 0 no participa en cobertura, faltantes, debilidades ni valor del plan.
- Cafe excluye la mecanica exacta `Legacy Game` y los titulos cuyo nombre inicia exactamente con `EXIT: The Game`. La segunda es una regla explicita de serie porque el catalogo no tiene una etiqueta especifica para EXIT.
- No se excluyen `Game: Escape (Queen Games)`, `Game: Lost Legacy` ni `Game: Flash Point Legacy of Flame`.

## Bloque 3

- La Fase 4 implementa planner con degradacion determinista, plan persistido antes de tools, ejecucion secuencial, narrador por plantillas y critic determinista. El chat usa el perfil activo como contexto y no expone modo precio.

## Fase 4

- El narrator LLM usa `LLM_MODEL`, redacta en espanol solo a partir de resultados de tools y conserva plantillas para falta de clave, fallo o intents fijos.
- El critic mantiene sus reglas deterministas y agrega revision estructurada con `LLM_MODEL_FAST` para cifras, juegos y atributos sin respaldo y recomendaciones no sustentadas.
- Los rechazos regeneran la respuesta con hallazgos como feedback hasta `CRITIC_MAX_RETRIES`; al agotarse los intentos se usa la plantilla. Narrator, critic, intentos y hallazgos quedan en `agent_steps`.
- El planner determinista extrae el titulo de una pregunta de compra, identifica plan de compra, que falta, que sacar hoy y fuera de dominio. La resolucion prioriza una coincidencia exacta normalizada como `Catan` (`13`) y solo devuelve ambiguo sin coincidencia exacta.
- El narrator solo usa hechos de tools. El critic exige el motivo de una regla exacta, los valores A, B y C en planes, faltantes y debiles en cobertura, y niveles de peso, interaccion o duracion presentes en los resultados.
- El planner incluye ejemplos de formulaciones naturales por intent y valida el plan contra el catalogo: un juego encontrado fuerza `evaluar_compra` si no esta en la coleccion o `detalle_juego` si ya esta. La resolucion acepta el titulo antes de `:` cuando es unico, como `SETI`.
- El narrator no ofrece funciones fuera del manifiesto ni nombres internos entre comillas invertidas. El critic rechaza ambos casos y pide al LLM detectar respuestas que no contestan la pregunta.
- La validacion posterior solo fuerza un intent de juego para una coincidencia exacta normalizada o el titulo unico antes de `:`. Una coincidencia difusa no puede convertir una consulta general de cobertura en `evaluar_compra`.
- `¿Y SETI?` se interpreta como consulta de compra y `Catan` conserva la coincidencia exacta con el ID `13`.
- La resolucion combina coincidencias exactas normalizadas y titulos unicos antes de `:`. Con varios candidatos, resuelve solo si el primero por `Users rated` tiene al menos cinco veces los votos del segundo; en otro caso devuelve ambiguedad ordenada por votos.
- `SETI` resuelve a `SETI: Search for Extraterrestrial Intelligence` (`418059`, 21,902 votos) frente a `Seti` (`17785`, 47 votos).
- Se probaron las seis preguntas del guion sin LLM. Los casos reales saneados quedan en `backend/tests/fixtures/chat_casos_reales_saneados.json`; la resolucion ambigua real de Catan esta en `backend/tests/fixtures/chat_catan_ambiguo_saneado.json`. Los fixtures no guardan cabeceras.
- Verificacion de cierre: `make test` con 83 pruebas backend y 1 frontend; `make lint` limpio; `docker compose up --build -d` con backend saludable.

## Fase 6

- La interfaz usa una sola barra de navegacion: Ludoteca, Modo mesa, Cobertura y Chat. Ludoteca y Modo mesa cambian el perfil activo y conservan las pantallas existentes.
- Ludoteca, Modo mesa y Cobertura incluyen una explicacion breve y un bloque desplegable de tres lineas sobre su funcionamiento.
- Cada grupo de la Ludoteca se presenta como un librero independiente en una cuadricula de dos o tres columnas en escritorio. Las colecciones de mas de 24 juegos empiezan en vista compacta y permiten alternar la vista.
- En Modo mesa, solo los resultados con ajuste `ideal` usan resplandor dorado; los que funcionan conservan su color y los que no cumplen permanecen oscurecidos. La leyenda lo explica.
- Chat inicia como conversacion con bienvenida de Wise Dice, tres preguntas aleatorias de un banco local de casos probados y burbujas diferenciadas. Los chips, tarjetas y candidatos de cada respuesta permanecen dentro de su burbuja.
- El chat renderiza markdown con un transformador local que escapa la entrada antes de aplicar formato. Las burbujas permiten cortes en URLs y palabras largas.
- La sesión conserva el último juego resuelto como foco; el planner recibe tres turnos resumidos y las continuaciones sin título reutilizan ese foco.
- Si el nombre en español no resuelve localmente y hay clave, el modelo rápido propone hasta tres títulos originales estructurados. El resultado registra `interpretado_como`; sin clave se omite este paso.
- Una consulta de compra para un juego ya poseído no lo evalúa como compra: devuelve el impacto determinista de venderlo.
- El librero agrupa Familia por familias mecánicas y cada grupo se renderiza en un solo mueble. Las filas se dibujan con un fondo repetido y los grupos con más de 6 juegos ocupan todo el ancho disponible.
- El perfil activo se conserva en el navegador y se incluye como parámetro en las llamadas de colección, motor y chat. Las colecciones reales verificadas tienen 12 juegos para `coleccionista` y 40 para `cafe`.
- Ludoteca integra el filtro de mesa sobre el librero: el resultado `ideal` ilumina la portada, `funciona` conserva su color y el resto se oscurece. La vista compacta solo modifica la altura de portada mediante `--cover-h`.
- El markdown del chat escapa todo contenido antes de permitir encabezados, párrafos, listas, negrita, cursiva y enlaces HTTP(S) con `rel="noopener"`.
- El foco de chat solo se reutiliza cuando no se extrae un título nuevo del mensaje. Las traducciones guardan nombre buscado, título resuelto y sugerencias del modelo en la traza; las sugerencias no resueltas se convierten en candidatos locales por similitud y votos.
- Las coincidencias aproximadas no resuelven un juego: solo producen candidatos ambiguos tras comparar cadenas completas y limitar la diferencia de longitud. La continuación "El nombre en inglés es" conserva la intención pendiente de la sesión.
- La resolución de nombres del chat usa una sola puerta: solo coincide de forma exacta, por el prefijo antes de `:` o por una traducción exacta. Una traducción exacta queda como candidato ambiguo y requiere confirmación de la persona. La sugerencia final `💡` la añade el backend desde la intención, no el narrator.
- La traducción de títulos guarda en el resultado persistido de la tool si se llamó al LLM, los títulos devueltos y cualquier error acotado. Así una excepción no se confunde con una respuesta sin sugerencias.
- `gpt-5.1-mini` no está disponible para la clave del entorno y devuelve `404 model_not_found`. Los valores por defecto de `LLM_MODEL` y `LLM_MODEL_FAST` son `gpt-5.1`, modelo verificado; no hay normalización implícita de nombres.
- La traza de traducción también se conserva cuando una sugerencia resuelve un juego, no solo cuando queda sin resolver.
- Planner, traducción, narrator y critic registran en `agent_steps` el modelo utilizado y cualquier excepción acotada. Al arrancar, la aplicación lista los modelos disponibles y `/capabilities` expone la validación separada de `LLM_MODEL` y `LLM_MODEL_FAST`.
- El narrator recibe una copia formateada de los resultados: peso con un decimal, similitudes con dos, precios `USD 67.50` y fechas `24 sep 2026`. Las cifras crudas siguen en los resultados deterministas para tarjetas y critic.
- El backend antepone el emoji de resultado y sanea negritas markdown desbalanceadas por línea. El prompt del narrator prohíbe emojis.
- Plan, ficha y evaluación usan los mismos formateadores de precio y fecha en Angular; no se muestran timestamps ISO en tarjetas.
- La resolución local rechaza consultas normalizadas de menos de dos caracteres y descarta títulos con clave normalizada vacía. La normalización conserva letras Unicode, incluidos alfabetos no latinos, tras quitar acentos.
- Mejora futura: imponer una procedencia explícita de resolución antes de ejecutar tools, permitiendo solo coincidencia exacta o prefijo del texto de usuario, candidato confirmado o foco de sesión.

## Bloque 2

- Se agregaron perfiles versionados de colección. `coleccionista` conserva meta 2 en todos los niveles y reproduce las pruebas doradas y el anexo existentes.
- `cafe` usa los 40 IDs entregados, con metas por nivel para operación B2B. Los niveles con meta 0 no participan en cobertura, faltantes, debilidades ni en el valor del plan.
- La valoración de un nivel faltante es `1 / niveles relevantes del eje`; una cobertura parcial reparte la mitad restante entre las posiciones de la meta 2 a la meta configurada.
- La API acepta `perfil` como contexto para colección y motor, expone `GET /profiles` y `GET /profiles/context`, y la interfaz ofrece el selector `Modo mesa` para Café demo.
- La inicialización SQLite añade `profile_id` a una colección ya creada y asigna sus filas existentes a `coleccionista`, sin borrar datos.
- Con la siembra real, Café demo tiene 40 juegos. Con `n=5`, `average_min=6.5` y `users_rated_min=1000`, el plan por precio USD 60 propone EXIT: The Game - The Forbidden Castle, Kingdom Legacy: Feudal Kingdom, The Werewolves of Miller's Hollow y Level 10, por USD 47.82 y valor pendiente 0.025.

## Estado por fases

| Fase | Estado | Contenido |
| --- | --- | --- |
| 0 | Completada | Dependencias, artefactos, web_search y decisiones de BGG verificados. |
| 1 | Completada | Monorepo, Makefile, Docker, backend FastAPI, frontend Angular, SQLite, esquema y seed. |
| 1b | Completada | Vitrina de Ludoteca, catalogo y coleccion de solo lectura. |
| 2 | Completada | Motor determinista, matrices, cobertura, compra, disponibilidad y pruebas doradas. |
| 3 | Completada | API REST de coleccion y motor, con pruebas de API. |
| 3b | Completada | Pantallas de Cobertura, detalle, disponibilidad y vista previa de Chat. |
| 4 | Completada | Planner determinista corregido, narracion y critic LLM, regeneracion trazada, fixtures reales y pruebas del guion. |
| 6 | Completada | Interfaz de ludoteca, modo mesa, cobertura y chat pulida para escritorio y movil. |
