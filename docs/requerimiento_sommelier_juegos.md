# Requerimiento: Sommelier de juegos de mesa (sprint 1)

Documento de instrucciones para el agente de código. Reemplaza por completo cualquier PRD anterior: si recuerdas otro requerimiento de este proyecto, ignóralo.

**Antes de este documento rigen las reglas de `docs/reglas_agente.md`.** Si algo de aquí choca con esas reglas, ganan las reglas y te detienes a preguntar.

Anexos obligatorios (léelos antes de escribir código):

- `docs/conocimiento_notebook_juegos.md`: todas las decisiones, fórmulas, umbrales y cifras del núcleo analítico. **Es la fuente de verdad del motor.** Si este requerimiento y el anexo difieren en una fórmula o cifra, gana el anexo y lo reportas.
- Repositorio de referencia del profesor, ya clonado en `referencia/inverai/` (solo lectura, ignorado por git). Léelo, en especial `AGENTS.md`, `Makefile`, `backend/app/services/agents/` y `docker-compose.yml`. **Este proyecto sigue su arquitectura, stack y nivel de rigor.** Se copian patrones y piezas transversales; nunca se modifica esa carpeta.

Estado actual del repositorio: un commit con `artefactos/` en la raíz y un `.gitignore`. Todo lo demás lo creas tú.

---

## 1. Qué es

Aplicación web que ayuda a un coleccionista de juegos de mesa a **cubrir la mayor variedad de experiencias con el menor gasto, evitando juegos redundantes**.

El sistema responde cuatro preguntas (cada una es una tool del agente):

1. **¿Este juego que quiero comprar es redundante con lo que ya tengo, y con cuál?**
2. **¿Qué tipos de experiencia le faltan a mi colección?**
3. **¿Qué me conviene comprar para cubrir esos huecos?** (por número de juegos o por precio)
4. **De lo que ya tengo, ¿qué saco hoy para este grupo y este tiempo?**

Además, cuando el usuario pregunta por un juego que no está en el catálogo (por ejemplo, un lanzamiento local reciente que BGG aún no tiene), el sistema **lo busca en la web, extrae sus atributos con evidencia, lo vectoriza con el mismo preproceso y lo evalúa**. Si de verdad no encuentra nada, responde "no encontrado".

Objetivo de este sprint: **demo local completa con `docker compose up --build`**. El despliegue en línea es del siguiente sprint; no lo implementes, pero no lo impidas (nada de rutas absolutas ni secretos en código).

---

## 2. Principios no negociables (mismo rigor que el repo del profesor)

| # | Principio | Consecuencia |
|---|---|---|
| P1 | **El LLM nunca calcula un número.** | Similitudes, veredictos, coberturas, puntajes y precios salen del motor en Python. Las tarjetas de la UI se construyen con los resultados de las tools, nunca con texto del LLM. |
| P2 | **El plan de tool calls se produce y persiste antes de ejecutar.** | Igual que el D3 del profesor: planner, plan guardado, ejecución por niveles, narrator, critic. |
| P3 | **Cumplimiento determinista, no solo por LLM.** | El critic tiene reglas por código (sección 6.4) además de la revisión LLM. |
| P4 | **El vectorizador es fijo; el catálogo no.** | Juegos nuevos se vectorizan con `transform` del pickle. **Nunca `fit` en la app.** |
| P5 | **Todo dato extraído de la web lleva evidencia y origen.** | Sin fragmento de texto que lo respalde, el atributo se descarta. |
| P6 | **Degradación sin clave de OpenAI.** | Planner por palabras clave, narrator por plantillas, búsqueda web desactivada con aviso. El motor funciona completo. |
| P7 | **Las tools del chat son de solo lectura.** | Agregar o quitar juegos de la colección se hace por la UI y la API REST, nunca desde el chat. |
| P8 | **No verificado = no asumido.** | Versiones, endpoints y capacidades se verifican en vivo o en documentación oficial y se anotan en `AGENTS.md`. |

---

## 3. Stack (el mismo del profesor)

Copia del repo del profesor la infraestructura y las piezas transversales; reescribe el dominio.

**Backend**: Python 3.14, uv, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 async, **SQLite con aiosqlite y WAL**, Alembic, httpx, SDK `openai`, pytest, pytest-asyncio, respx, ruff, mypy. Toma las versiones de su `pyproject.toml` como punto de partida.

Dependencias adicionales de este proyecto:

- `scikit-learn`, `scipy`, `numpy`, `pandas`: **fijadas exactamente a las versiones del entorno del cuaderno**, porque `preproceso.pkl` se generó con ellas. Versiones: `scikit-learn==<LLENAR>`, `scipy==<LLENAR>`, `numpy==<LLENAR>`, `pandas==3.0.5`. Si alguna no instala en Python 3.14, **detente y reporta**; no cambies la versión por tu cuenta.
- `rapidfuzz` para búsqueda aproximada por nombre.

**Frontend**: Angular 22 standalone, signals, Tailwind v4, servido por nginx, tipos de API generados con `openapi-typescript` (`make contracts`). Gráficas con **Chart.js usado directamente** (sin wrapper de Angular, para no heredar conflictos de peers con TypeScript 6). Drag and drop (sprint 2) con `@angular/cdk`.

**Infra**: `docker-compose.yml` con dos servicios (backend y frontend con nginx) y un volumen para la base, igual que el del profesor. `Makefile` con `setup`, `dev`, `seed`, `test`, `lint`, `format`, `contracts`, `up`, `down`.

**Trampas heredadas**: lee la sección 4 del `AGENTS.md` del profesor. Aplican directamente al menos: TypeScript fijado a 6.0.x, `npm install --force`, `passlib` roto en 3.13+, `NoDecode` para listas en settings, `SafeExtraLogger`, `AsyncSession` no concurrente, PRAGMAs de SQLite, `UTCDateTime`, guardas de Angular que devuelven `UrlTree`.

---

## 4. Datos y artefactos

Están en `artefactos/` en la raíz del repositorio y **son de solo lectura: no los muevas, renombres, reescribas ni regeneres**. El backend los lee desde la ruta de la variable `ARTEFACTOS_DIR`. En `docker-compose.yml` se montan como volumen de solo lectura (`./artefactos:/srv/artefactos:ro`); no se copian a la imagen.

| Archivo | Uso |
|---|---|
| `catalogo.csv` | 30,146 juegos. Listas guardadas como JSON. Se carga a SQLite en `make seed`. |
| `X_mecanicas.npz`, `X_tematica.npz` | Matrices dispersas (`scipy.sparse.load_npz`). |
| `X_ocasion.npy`, `X_interaccion.npy` | Matrices densas. |
| `preproceso.pkl` | Vectorizadores (`MultiLabelBinarizer` + `TfidfTransformer`), escalador, límites de ocasión, pesos, umbrales, diccionarios de interacción, familias, respaldo por categoría, temas, niveles de jugadores, umbral de ofertas de precio. |
| `tipos_experiencia.csv` | 48 tipos en 6 ejes: eje, nivel, definición, proporción del catálogo. |

Reglas:

- **Las filas de las matrices coinciden con el orden de `catalogo.csv`.** Al sembrar, guarda esa posición en la columna `fila_vector`.
- Las matrices se cargan **en memoria al arrancar** FastAPI (pesan unos 3 MB). La base guarda catálogo, colecciones y trazas. No uses extensiones vectoriales.
- Antes de escribir el esquema, **inspecciona las columnas reales** de `catalogo.csv` y el contenido de `preproceso.pkl` y documéntalos en `AGENTS.md`. Hechos ya observados que debes confirmar:
  - Hay dos URLs de imagen por juego: una de 246x300 (`__itemrep`) y la miniatura de 64x64 (`__micro`). La UI usa la grande.
  - **Columnas de precio válidas: solo las que no llevan sufijo**: `precio_usd`, `n_ofertas_us_stock`, `precio_confiable`, `fecha_precio`, `bgp_url`. Las copias con sufijo `_x` y `_y` son residuos de merges repetidos en el cuaderno, con valores desactualizados: **no se siembran en la base ni se usan en ninguna parte**. No modifiques el CSV; el seed simplemente las ignora. Documéntalo en `AGENTS.md` como trampa verificada.
  - Las URLs de BoardGamePrices traen `utm_source=site_https://github.com/TU_USUARIO/FinalDiplomado` (un marcador sin reemplazar). No modifiques el CSV: al servir el link, sustituye ese valor por el de la variable `BGP_SITENAME`.
- Nunca separes listas por coma: hay mecánicas con coma en el nombre ("I Cut, You Choose").

---

## 5. Modelo de datos (SQLite)

Todas las tablas de usuario llevan `user_id`, aunque en este sprint solo existe el usuario demo.

- `users`: id, email, nombre. Se siembra un usuario demo. **Sin pantalla de login en este sprint**; el backend resuelve siempre al usuario demo mediante una dependencia `get_current_user` que en el sprint 2 se reemplaza por JWT como en el repo del profesor.
- `games`: catálogo. Todas las columnas de `catalogo.csv` más `fila_vector`, `origen` (`bgg_ranking`, `bgg_sin_rank`, `web`), `confianza` (`alta`, `media`, `baja`), `fuentes` (JSON con URLs), `evidencia` (JSON: atributo, fragmento, URL), `creado_en`.
- `game_vectors_extra`: vectores por bloque de los juegos agregados en tiempo de ejecución (`game_id`, bloque, vector serializado). Al arrancar, se apilan debajo de las matrices de archivo y se les asigna `fila_vector` consecutiva.
- `game_aliases`: `alias_normalizado`, `game_id`, `origen`. Permite que "Aventureros al tren" resuelva a su juego del catálogo la segunda vez.
- `user_collection`: `user_id`, `game_id`, `precio_pagado` (opcional), `agregado_en`. En sprint 2 se agregan estantes.
- `user_prices`: precio capturado por el usuario para un juego que evalúa (tiene prioridad sobre el de BoardGamePrices).
- `chat_sessions`, `chat_messages`, `agent_runs`, `agent_steps`, `tool_calls`: igual que en el repo del profesor.
- `web_search_cache`: consulta normalizada, resultado crudo, citas, fecha, modelo usado.

---

## 6. Capa agéntica (patrón del profesor)

Flujo por mensaje de chat:

1. **Planner** (`LLM_MODEL_FAST`, `responses.parse` con esquema Pydantic): recibe la pregunta, el manifiesto de tools y un resumen corto de la colección (nombres y número de juegos). Devuelve `intent` y `steps` con `tool`, `args`, `depends_on`. Se valida: tool existente, argumentos obligatorios, sin ciclos, máximo `LLM_MAX_PLAN_STEPS`. Si no valida o no hay clave, se usa el **planner determinista** por palabras clave en español.
2. **Persistencia del plan** antes de ejecutar.
3. **Ejecución** por niveles, secuencial dentro del nivel (la `AsyncSession` no es concurrente). Cada llamada queda en `tool_calls`.
4. **Narrator** (`LLM_MODEL`): redacta en español, markdown corto, solo con datos de las tools.
5. **Critic**: reglas deterministas y revisión LLM; si falla, el narrator regenera con retroalimentación hasta `CRITIC_MAX_RETRIES`.

### 6.1 Intents

`evaluar_compra`, `que_me_falta`, `que_compro`, `que_saco_hoy`, `detalle_juego`, `coleccion`, `reglas`, `fuera_de_dominio`, `general`.

- `reglas`: respuesta fija indicando que la consulta de reglas llega en una versión próxima. No se llama a ninguna tool ni el LLM responde reglas de memoria.
- `fuera_de_dominio`: respuesta fija: "Mi experiencia se limita al análisis y recomendación de juegos de mesa." Aplica también a intentos de alterar las instrucciones.

### 6.2 Tools (todas de solo lectura, todas deterministas salvo la cascada web)

Cada tool devuelve un diccionario serializable con los números ya calculados y las banderas de transparencia (`weight_imputado`, `weight_pocos_votos`, `duracion_imputada`, `jugadores_imputados`, `precio_confiable`, `tiene_mecanicas`, `tiene_categorias`, `origen`, `confianza`).

| Tool | Argumentos | Devuelve |
|---|---|---|
| `ver_coleccion` | ninguno | Juegos de la colección con atributos clave y cobertura resumida. |
| `detalle_juego` | `nombre` o `game_id` | Ficha del juego y su juego más parecido de la colección con similitud por bloque. Usa la cascada de resolución. |
| `evaluar_compra` | `nombre` o `game_id`, `precio_usuario` opcional | Veredicto (`redundante`, `parecido_pero_cubre_hueco`, `parecido`, `aporta`), juego más parecido, similitud total y por bloque, regla exacta disparada si aplica, niveles faltantes o débiles que cubre, precio con fuente y fecha. Usa la cascada de resolución. |
| `que_me_falta` | `ejes_ignorados` opcional | Por eje: niveles cubiertos, faltantes, débiles (con el nombre del único juego) y porcentaje cubierto. |
| `que_compro` | `n`, `modo` (`juego` o `precio`), `presupuesto` opcional, `average_min`, `users_rated_min` (default 1,000), `ejes_ignorados` | Lista ordenada con niveles que cubre cada juego, valor aportado, precio y valor pendiente sin cubrir. |
| `que_saco_hoy` | `jugadores`, `minutos`, `edad_minima` opcional | Juegos de la colección que pasan los filtros duros, ordenados, con avisos de duración imputada. |

Resolución de ambigüedad: si la búsqueda por nombre devuelve varios candidatos cercanos (por ejemplo "Catan" y "Catan: Portable Edition"), la tool devuelve `estado: "ambiguo"` con los candidatos. El narrator pide elegir y la UI muestra los candidatos como botones que reenvían el mensaje con `game_id` (igual que el `ticker` de pista del profesor, el `ChatRequest` acepta `game_id` opcional).

### 6.3 Cascada de resolución de juegos

Vive **dentro del servicio**, no en el plan: el planner solo escribe `evaluar_compra("Metropoli")` y el servicio resuelve. Así el plan fijo no necesita saber de antemano si el juego existe.

1. **Local**: nombre normalizado (minúsculas, sin acentos, sin puntuación) contra `games.nombre` y `game_aliases` con `rapidfuzz`. Por encima del umbral alto, match directo; entre umbrales, `ambiguo`; por debajo, siguiente nivel. Umbrales configurables y documentados.
2. **BGG fuera del ranking** (condicional): el catálogo solo tiene juegos rankeados. `geekitems` y `api.geekdo.com/api/dynamicinfo` funcionan por ID para cualquier juego, pero **no está verificado** cómo obtener el ID a partir del nombre sin la API oficial. Ver Fase 0. Si no hay una vía que funcione con una petición HTTP normal, **este nivel se omite**. Prohibido evadir Cloudflare o cualquier protección.
3. **Web** (`WEB_SEARCH_ENABLED=true` y clave presente):
   - **Paso A, búsqueda**: API de Responses con la herramienta hospedada `web_search` (no `web_search_preview`) y `tool_choice: "required"`. Modelo `LLM_MODEL_WEB`. No usar razonamiento `minimal` ni `none`. Se pide identificar el juego y describir sus datos de juego. Se guardan el texto y las citas `url_citation` en `web_search_cache`.
   - **Paso A2, re-resolución**: si la respuesta identifica el juego como uno que ya está en el catálogo con otro nombre (traducción, edición), se vuelve al nivel 1 con ese nombre, se registra el alias y se usan los datos del catálogo (`confianza: alta`).
   - **Paso B, extracción**: `responses.parse` sobre el texto del paso A con un esquema Pydantic **restringido al vocabulario del pickle**: mecánicas como `Literal` de las 193 del vectorizador, categorías de las 83, jugadores, duración mínima y máxima, edad, diseñador, editorial, año. Cada atributo trae `evidencia`: fragmento textual y URL.
   - **Validación determinista**: se descarta todo atributo cuyo fragmento no aparezca literalmente en el texto del paso A o cuya URL no esté entre las citas. Si tras validar no quedan mecánicas ni categorías, el resultado es "no encontrado con datos suficientes".
   - **Vectorización**: mismas correcciones de ceros, límites de ocasión, tope de 10 jugadores, escalador, `mlb_*` y `tfidf_*` con `transform`, y mismas reglas de interacción y familias del pickle. El peso casi nunca aparece en la web: se imputa con el mismo criterio del cuaderno y se marca `weight_imputado`. Si el pickle no incluye el imputador, **detente y reporta** en lugar de inventar uno.
   - **Persistencia**: se inserta en `games` con `origen: web`, confianza calculada por reglas (documentadas en `AGENTS.md`) y evidencia; vectores en `game_vectors_extra`; alias registrado. La siguiente consulta resuelve en el nivel 1.
4. **Nada encontrado**: `estado: "no_encontrado"`. Nunca se evalúa un juego sin datos.

La búsqueda web es la única parte donde un LLM produce datos. Por eso la respuesta al usuario **siempre** dice que la evaluación se basa en datos extraídos de la web y muestra las fuentes; la UI muestra los atributos extraídos con su evidencia.

### 6.4 Critic: reglas deterministas

Implementa estas verificaciones por código sobre la respuesta del narrator y los resultados de las tools:

1. La palabra "redundante" solo puede aparecer si alguna tool devolvió `veredicto: "redundante"`.
2. Si un juego mencionado tiene alguna bandera de imputación, la respuesta debe contener "estimad".
3. Si algún juego usado tiene `origen: web`, la respuesta debe decirlo y citar al menos una fuente.
4. Todo precio mencionado debe ir con su fuente (BoardGamePrices con fecha, o "precio que capturaste").
5. Todo número en la respuesta debe existir en los resultados de las tools (con tolerancia de redondeo y conversión a porcentaje documentadas).
6. Si una tool devolvió `ambiguo` o `no_encontrado`, la respuesta no puede presentar una evaluación.

La revisión LLM del critic se limita a: cifras sin fuente, mecánicas o atributos que no estén en los resultados, y afirmaciones de calidad no sustentadas.

### 6.5 Narrator

- Español, markdown breve. Explica el porqué con los bloques de similitud ("se parecen por mecánicas y temática").
- Nunca presenta la similitud como "afinidad" o "match".
- Degradación: plantillas por intent que usan los mismos resultados.

---

## 7. Motor (Python puro, sin LLM)

Implementa exactamente lo del anexo, secciones 5 a 8. Resumen para orientarte:

- **Similitud por bloques**: coseno para mecánicas y temática; `1 - ||a - b||² / 2` para ocasión e interacción; promedio ponderado **solo sobre los bloques disponibles del par**, renormalizando pesos. Pesos: mecánicas 0.40, ocasión 0.10, interacción 0.15, temática 0.35. Para decisiones de redundancia usa esta fórmula, no el vector concatenado.
- **Redundancia**: (regla exacta por `product_line` o `reimplements`/`reimplemented_by`, **o** similitud máxima contra la colección ≥ 0.773) **y** no cubre ningún nivel faltante o débil. Si cubre alguno: `parecido_pero_cubre_hueco`. Umbral 0.417 solo para ordenar y explicar, nunca como alerta.
- **Cobertura**: 6 ejes, 48 niveles de `tipos_experiencia.csv`; faltante = 0 juegos, débil = 1 juego.
- **Qué compro**: valor de nivel faltante = 1 / niveles del eje; débil = la mitad. Greedy por valor pendiente cubierto / costo.
  - Modo `juego`: costo 1 por juego, se detiene en `n`.
  - Modo `precio`: solo candidatos con precio confiable o capturado; se detiene cuando ningún candidato cabe en el `presupuesto`. **Además**, compara el resultado del greedy contra el mejor juego individual que quepa en el presupuesto y devuelve el de mayor valor cubierto. Esta comparación es la que da garantía de aproximación con costos distintos; el greedy solo por cociente no la tiene.
  - Nunca mezcles modos en una misma corrida. `Average` solo desempata. Excluye redundantes que no cubran huecos.
- **Qué saco hoy**: filtros duros de jugadores (`rec_players`, respaldo caja), tiempo (`max_playtime`, incluir con aviso si está imputada), edad (sin dato no excluye); prioriza `best_players`; ordena por `Average`.

---

## 8. Precio

- En el catálogo: mediana en EE. UU. con stock, confiable con al menos 2 ofertas. Sin imputar.
- La UI muestra el precio en USD con la leyenda "EE. UU.", la fecha y **un link a BoardGamePrices** junto al precio (condición de uso de su API).
- En este sprint no se consulta BoardGamePrices en vivo. Si en el sprint 2 se hace, cachear al menos una hora.
- El precio capturado por el usuario siempre tiene prioridad.

---

## 9. API REST (prefijo `/api/v1`)

Mínimo:

- `GET /health`, `GET /capabilities` (indica si hay LLM y búsqueda web activos).
- `GET /games?q=&limit=`: búsqueda en catálogo para agregar juegos.
- `GET /games/{id}`: ficha con evidencia y fuentes si es de origen web.
- `GET /collection`, `POST /collection` (`game_id`, `precio_pagado` opcional), `DELETE /collection/{game_id}`.
- `POST /engine/evaluate`, `GET /engine/coverage`, `POST /engine/buy-plan`, `POST /engine/tonight`: el motor expuesto sin chat, para la UI y para pruebas.
- `POST /chat`, `GET /chat/runs/{id}`, `GET /chat/runs`.

Errores de dominio con el formato del profesor: `{"error": {"code", "message", "details"}}`.

`ChatResponse`: `run_id`, `session_id`, `intent`, `plan` (pasos con estado), `answer` (markdown), `tarjetas` (construidas **desde los resultados de las tools**: juego, portada, veredicto, similitud por bloque, niveles que cubre, precio, banderas, origen, fuentes), `candidatos` (si hubo ambigüedad), `critic_passed`, `llm_used`.

---

## 10. Frontend

Estética de ludoteca: portadas grandes, fondo cálido, estantes visuales. Priorizar que se vea bien en la demo, con usabilidad sobre fidelidad realista. Español.

Páginas:

1. **Ludoteca** (inicio): la colección como **estantes visuales con portadas**. Selector "Agrupar estantes por": familia de mecánica, jugadores, duración, peso o interacción. Cada estante es un nivel del eje elegido (los juegos multifamilia aparecen en cada estante que les corresponde). Buscador para agregar juegos del catálogo.
2. **Cobertura**: gráfica de radar con el porcentaje cubierto por eje; lista de niveles faltantes y débiles; botón que abre el plan de compra.
3. **Chat**: panel con el plan como chips de estado (como el del profesor), respuesta en markdown seguro, tarjetas de juego renderizadas desde `tarjetas`, botones de candidatos cuando hay ambigüedad. Historial por `session_id`.
4. **Detalle de juego** (modal): portada, atributos, barras de similitud por bloque contra su juego más parecido de la colección, banderas en lenguaje simple ("peso estimado"), precio con link y fecha, y para origen web: atributos con su evidencia y fuentes.

En móvil, la vista pasa a pestañas.

---

## 11. Pruebas y aceptación

Como en el repo del profesor: **las pruebas nunca tocan la red**. Las respuestas de OpenAI (planner, narrator, web search, extracción) se graban como fixtures y se reproducen.

Pruebas doradas del motor (tolerancia ±0.01 sobre los valores del anexo, sección 9):

| Par | Total esperado | Etiqueta esperada |
|---|---|---|
| Brass: Birmingham / Lancashire | 0.94 | redundante |
| Gloomhaven / Frosthaven | 0.88 | redundante |
| 7 Wonders / 7 Wonders Duel | 0.83 | redundante por similitud; `parecido_pero_cubre_hueco` si la colección no cubre 2 jugadores |
| Pandemic / Pandemic Legacy S1 | 0.71 | redundante por regla exacta |
| Wingspan / Wyrmspan | 0.70 | parecido |
| Wingspan / Earth | 0.59 | parecido |
| Twilight Imperium 4 / Codenames | 0.24 | distinto |
| Spirit Island / Twilight Struggle | 0.21 | distinto |
| Gloomhaven / Dixit | 0.13 | distinto |

También: clasificaciones de interacción de referencia (anexo, sección 9) y la colección demo.

**Colección demo** (se siembra al usuario demo): Wingspan, Brass: Birmingham, Gloomhaven, Codenames, Catan, Azul, Terraforming Mars, Pandemic, 7 Wonders Duel, Cascadia, Spirit Island, Root. La prueba verifica los faltantes y débiles documentados en el anexo. Las recomendaciones de compra del anexo dependen de parámetros no documentados; si no se reproducen, **reporta los parámetros que usaste y la diferencia**, no ajustes el motor para forzarlas.

**Guion de demo** (debe funcionar de punta a punta):

1. "Tengo ganas de comprar Wyrmspan, ¿vale la pena?" → parecido a Wingspan, con bloques.
2. "¿Qué le falta a mi colección?" → faltantes y débiles.
3. "Tengo 60 dólares, ¿qué compro para cubrir huecos?" → plan por precio.
4. "Somos 6 y tenemos 45 minutos, ¿qué saco?" → filtros sobre la colección.
5. "¿Qué tal Metropoli de Ideotas Juegos para mi colección?" → cascada web con fuentes y atributos con evidencia, o "no encontrado" si no hay datos suficientes.
6. "Catan" → ambigüedad con candidatos.
7. Sin `OPENAI_API_KEY`: los casos 1 a 4 responden con planner determinista y plantillas; el 5 avisa que la búsqueda web no está disponible.

---

## 12. Configuración (`.env.example`)

Además de las variables base del profesor que apliquen (aplicación, BD, CORS):

```
DATABASE_URL=sqlite+aiosqlite:///./data/sommelier.db
OPENAI_API_KEY=
LLM_ENABLED=true
LLM_MODEL=gpt-5.1
LLM_MODEL_FAST=gpt-5.1-mini
LLM_MODEL_WEB=gpt-5.1
LLM_TEMPERATURE=0.2
LLM_MAX_PLAN_STEPS=8
CRITIC_MAX_RETRIES=1
WEB_SEARCH_ENABLED=true
FUZZY_UMBRAL_DIRECTO=
FUZZY_UMBRAL_AMBIGUO=
USERS_RATED_MIN=1000
ARTEFACTOS_DIR=../artefactos
BGP_SITENAME=
DEMO_USER_EMAIL=demo@sommelier.local
```

El `.env` real lo crea Miguel. Tú solo creas y mantienes `.env.example`, siempre con los valores secretos vacíos.

Los modelos por defecto son los del repo del profesor; verifica en Fase 0 que existen en la cuenta y que `LLM_MODEL_WEB` admite `web_search`.

---

## 13. Fases de trabajo

Al cerrar cada fase: pruebas en verde, `make lint` limpio, `AGENTS.md` actualizado (estado, decisiones, trampas verificadas) y **te detienes a reportar** antes de seguir.

- **Fase 0: verificaciones.** Todo en un script desechable fuera del código de la app. Versiones del cuaderno instalan en Python 3.14; carga de `preproceso.pkl` y matrices; columnas reales del catálogo (confirma que existen las cinco columnas de precio sin sufijo); una única llamada real a `web_search` con `tool_choice: "required"` que devuelva citas (pide aprobación antes de ejecutarla); si existe una vía por nombre hacia un ID de BGG sin token ni evasión de protecciones (como máximo 3 peticiones). Reporta resultados antes de construir.
- **Fase 1: andamiaje.** Primero el `.gitignore` completo (sección 15). Luego monorepo, Makefile, Docker, settings, logging, errores, sesión SQLite, esquema, seed del catálogo, del usuario demo y de su colección.
- **Fase 2: motor.** Carga de matrices en memoria, similitud, redundancia, cobertura, plan de compra, filtros de hoy, resolución local con ambigüedad. Pruebas doradas.
- **Fase 3: API REST** del catálogo, colección y motor.
- **Fase 4: capa agéntica.** Registro de tools, planner LLM y determinista, orquestador con plan persistido, narrator, critic con reglas deterministas. Fixtures grabados.
- **Fase 5: cascada web.** Búsqueda, re-resolución, extracción con vocabulario cerrado, validación de evidencia, vectorización, persistencia, caché.
- **Fase 6: frontend.** Ludoteca con estantes, cobertura, chat, detalle.
- **Fase 7: cierre.** `docker compose up --build` desde cero, guion de demo completo, README en español con instrucciones de arranque.

---

## 14. Fuera de alcance del sprint 1

Consulta de reglas (sprint 2: RAG sobre el PDF del reglamento con cita de página), login real con JWT, estantes personalizados con drag and drop, venta de juegos, precios en vivo, despliegue en línea, precios en México.

---

## 15. Seguridad y secretos en el código de la app

Además de `docs/reglas_agente.md`:

- `.gitignore` debe incluir como mínimo: `.env`, `.env.*` (excepto `!.env.example`), `*.db`, `*.db-wal`, `*.db-shm`, `referencia/`, `.venv/`, `node_modules/`, `dist/`, `.angular/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.ipynb`.
- La clave de OpenAI solo se lee de la variable de entorno mediante `pydantic-settings`, como `SecretStr`. Nunca se registra en logs, nunca se incluye en respuestas de la API ni en `/capabilities` (que solo dice si hay clave, no cuál).
- **Fixtures grabados**: antes de guardar una respuesta de OpenAI como fixture, se eliminan cabeceras (`Authorization`, `OpenAI-Organization`, `OpenAI-Project`, cookies) e identificadores de organización. Un test verifica que ningún archivo de `tests/fixtures/` contiene `sk-` seguido de 20 o más caracteres ni la palabra `Bearer`.
- Los logs del backend nunca imprimen el contenido completo de prompts con datos de configuración.
