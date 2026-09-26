# Conocimiento del cuaderno de ingeniería de datos

Optimizador de colecciones de juegos de mesa. Este documento reúne lo que solo se supo al construir el cuaderno: cómo se obtuvieron los datos, qué tienen realmente, qué se decidió y con qué cifras, cómo usar los artefactos y qué limitaciones quedan. Es la base para escribir el requerimiento de la app.

Cifras de la corrida con el catálogo completo (30,146 juegos). Si se re-ejecuta el cuaderno tras completar la descarga, las cifras pueden moverse ligeramente.

---

## 1. Fuentes de datos y acceso

### Lo que funciona

| Fuente | Acceso | Qué trae |
|---|---|---|
| Ranking beefsack | `https://raw.githubusercontent.com/beefsack/bgg-ranking-historicals/master/2026-08-08.csv` | ID, Name, Year, Rank, Average, Bayes average, Users rated, URL, Thumbnail |
| Ficha BGG | `https://boardgamegeek.com/api/geekitems?objectid=<ID>&objecttype=boardgame` | Mecánicas, categorías, familias, reimplementaciones, subdominios, diseñadores, jugadores, duración, edad, imagen |
| Estadísticas BGG | `https://api.geekdo.com/api/dynamicinfo?objectid=<ID>&objecttype=thing` | Peso (`stats.avgweight`, `stats.numweights`), rating, encuestas (`polls.userplayers`, `polls.playerage`) |
| Precios | `https://boardgameprices.com/api/info?eid=<IDs BGG separados por coma>&currency=USD&destination=US&sort=CHEAP1&sitename=<url del proyecto>` | Ofertas por producto: precio, envío, stock, país |

### Lo que no funciona (no volver a intentar)

- **API oficial XML de BGG**: requiere token de aplicación desde octubre de 2025; la solicitud fue rechazada.
- **`boardgamegeek.com/api/dynamicinfo`** (mismo endpoint en el dominio principal): 403 con cuerpo vacío. Solo funciona en `api.geekdo.com`.
- **Fichas HTML de BGG** (`/boardgame/<ID>`): protegidas por el challenge de Cloudflare; en headless no pasa y en modo visible no se resolvió. No se insistió: sería evadir una protección deliberada.
- **Kaggle**: inaccesible desde el entorno del proyecto. Existe un espejo en GitHub de un dataset de feb 2021 con peso (`jalwz17/Board-Game-Data-Analysis`, `bgg_dataset.csv`, separador `;`, decimal `,`), descartado porque casi no cubre juegos posteriores a 2020 (18% en 2021, 0.6% de 2023 en adelante).
- **Campos comerciales de `geekitems`** (`bggstore_product`, `walmart_id`, `targetco_url`, `promoted_ad`): no traen el precio del juego. `promoted_ad` trae el precio de un **accesorio** anunciado (9% de cobertura).

### Detalles técnicos de la descarga

- `geekitems` y `dynamicinfo` requieren un **user agent de navegador**; con el de Chromium headless por defecto la respuesta no es JSON. Se usó Playwright con user agent `Chrome/122`.
- Leer el cuerpo con `resp.text()`, no con `document.body.innerText`.
- En Jupyter sobre Windows: la API sync de Playwright falla dentro del event loop, y la async falla con `NotImplementedError` porque ipykernel usa `SelectorEventLoop`. Solución: correr en un hilo con `asyncio.ProactorEventLoop()`, o correr el script como `.py` en terminal (recomendado).
- Velocidad medida: **2.5 s por juego** (dos peticiones más pausas); 10,000 juegos, unas 7 horas.
- Formato de descarga: JSONL con el JSON crudo por ID (`{"ID", "item", "stats", "polls"}`), reanudable, con errores en archivo aparte. BoardGamePrices: lotes de 20 IDs por llamada (cada ID devuelve decenas de productos).
- BoardGamePrices exige poner un link a su sitio donde se muestre el precio y cachear al menos una hora.

---

## 2. Qué tienen realmente los datos

### Cobertura

- Catálogo: **30,153** juegos descargados, **30,146** tras excluir 7 sistemas genéricos. Sin duplicados.
- **83** juegos descargados no están en el snapshot de ranking (sin Rank ni Average).
- **1,111** juegos del ranking no se descargaron (3.6%); relanzar el script los reintenta.
- El CSV de beefsack trae **167 IDs repetidos** y el orden por Rank no es monótono (1,967 intercambios locales). Siempre usar `drop_duplicates("ID").nsmallest(N, "Rank")`, nunca `head(N)` (el scraper original metió 23 IDs repetidos por eso).
- En el CSV, `Year` pierde el signo en juegos antiguos (Go = 2200, Backgammon = 3000: son fechas antes de Cristo) y hay año 0 en juegos tradicionales. `Thumbnail` es de 64x64; `geekitems.imageurl` es de mayor tamaño.

### Estructura de campos

- Todos los numéricos de los endpoints llegan como **texto**: forzar con `pd.to_numeric`.
- **En BGG el 0 significa "no capturado"**: 1,290 `max_playtime`, 1,736 `min_age` y 576 pesos en 0.
- `polls.userplayers` trae `best` y `recommended` como **listas de rangos**, que pueden ser discontinuas: Eclipse es mejor a 4 o a 6, no a 5. Se expanden a conjuntos de números.
- `polls.playerage` viene como texto ("10+").
- Hay mecánicas con coma en el nombre: **"I Cut, You Choose"** y **"Worker Placement, Different Worker Types"**. Guardar listas como listas o JSON, nunca como texto separado por coma.
- Familias (`boardgamefamily`): solo el prefijo **`Game:`** identifica la línea de producto ("Game: Catan", "Game: Monopoly (Official)"). `Series:` es ruido ("World's Smallest" aparece en Catan y en Monopoly).
- Las reimplementaciones (`reimplements`, `reimplementation`) y `product_line` se complementan: Dune: Imperium y Uprising solo se conectan por `product_line`.
- En BoardGamePrices, `versions` a veces es diccionario y a veces lista.
- El scraper original leía `stats` de `geekitems`, que no existe: su columna `weight` estaba 100% vacía y `Average` / `Users rated` venían del CSV base.

### Faltantes en el catálogo completo

| Variable | Juegos con faltante |
|---|---|
| Mecánicas | 1,706 sin ninguna (5.7%) |
| Categorías | 201 |
| Encuesta de jugadores | 3,424 (11.4%), usan la caja como respaldo |
| Edad de la comunidad | 7,327 (24.3%) |
| Duración | 1,011 |
| Peso | 576 |
| Jugadores (caja y encuesta) | 33 |

- La mediana de votos de peso es **8**; el **31%** de los juegos tiene menos de 5 votos. Los picos del histograma de peso en 1.0 y 2.0 son juegos con uno o dos votos.
- Duraciones extremas: The Campaign for North Africa, 60,000 min. Jugadores declarados de 99 y 999 ("ilimitado").
- 13 juegos tienen `min_playtime > max_playtime` (cotas capturadas al revés): se intercambian.

### Distribuciones del catálogo completo

- Peso: mediana 1.93; 51.4% ligero, 35.8% medio, 12.8% pesado.
- Duración (`max_playtime`): mediana 45 min; 41.4% hasta 30 min, 11.5% más de 2 horas.
- Jugadores recomendados: 2 y 3 a 4 los cubre más del 70% de los juegos; 7 o más solo el 9%.
- 196 mecánicas distintas; la más común es Dice Rolling (27.4%), ninguna es omnipresente.
- El catálogo completo es más ligero y corto que el top 3,640 (en el top, peso mediano 2.33 y 12.8% hasta 30 min más largo).

---

## 3. Decisiones y cifras que las justifican

| Tema | Decisión | Evidencia |
|---|---|---|
| Alcance | Catálogo completo; la calidad filtra solo recomendaciones | Cualquier juego de una colección debe poder evaluarse |
| Sistemas genéricos | Excluir "Game System" sin mecánicas | 7 casos: Traditional Card Games, Decktet, Piecepack, The Everdeck, The Badger Deck, Neue Spiele im alten Rom, Green Box of Games |
| Ceros | Convertir a nulo; si solo existe una cota, usarla para ambas | Aeon Trespass: 90 y 0 |
| Jugadores | Rango recomendado por la comunidad; caja como respaldo; mediana si no hay nada | Wingspan: 1 a 5 en caja, 1 a 4 recomendado, mejor a 3. Sleeping Gods: caja 4, recomendado hasta 3 |
| Extremos | Duración en log10 recortada a percentiles 1 y 99 (mínimo 5 a 360 min, máximo 10 a 720); jugadores con tope de 10 | Solo en el vector; los filtros usan valores reales |
| Imputación | KNN conjunto de peso y duración, k = 60 | ρ peso/duración 0.64 y 0.70, jugadores \|ρ\| ≤ 0.23; error del peso 0.647 → 0.432; duración 0.291 → 0.214 (log10) |
| Peso con pocos votos | Se conserva y se marca | Ruidoso pero no sesgado; no hay dispersión de votos para fijar un umbral objetivo |
| Edad | `community_age` con `min_age` de respaldo; sin ninguna, no se filtra | No entra al vector |
| Interacción | Diccionario de mecánicas en tres niveles más cooperativo aparte | Validada con juegos conocidos (sección 5) |
| Tipos de experiencia | Cobertura por dimensión, no clusters de juegos | Sección 4 |
| Vector | 4 bloques; similitud = promedio ponderado por bloque | Explicable; bloques sin datos se omiten |
| Pesos | Mecánicas 0.40, ocasión 0.10, interacción 0.15, temática 0.35 | AUC 0.964 con 7,196 pares positivos |
| Redundancia | Regla exacta o similitud ≥ 0.773; no redundante si cubre un hueco | 9.5% de falsa alarma frente a 50 juegos |
| Precio | Mediana en EE. UU. con stock; confiable con ≥ 2 ofertas con stock; sin imputar | Con 1 oferta, máximo $999.99; con 2, $275.00 |

---

## 4. Lo que se aprendió del clustering (resultados negativos útiles)

- **KMeans sobre el vector combinado** (K de 8 a 40, silueta en muestra de 10,000): silueta de **0.066 a 0.097** y **1 a 3 clusters negativos en todos los K**. En el top 3,640 la silueta fue 0.048 a 0.061 y la inercia no mostró codo. Al mezclar dimensiones, el catálogo es un continuo.
- **SVD truncado** (30 y 60 componentes, 49% y 65% de varianza) no mejoró la separación.
- **KMeans solo por mecánicas**: con 30 mil juegos no hay clusters negativos, pero la silueta no pasa de **0.131** y probablemente está inflada por los 1,706 juegos sin mecánicas (vectores idénticos en cero). En el top 3,640 había un cluster negativo en todos los K de 6 a 20.
- **Un juego combina varios estilos** (Wingspan: colección, mano y dados; 2.2 familias por juego en promedio), algo que un cluster único no representa.
- **Clustering jerárquico de mecánicas por co-ocurrencia** (Jaccard, enlace promedio): las mecánicas co-ocurren poco (casi todas las uniones con distancia mayor a 0.7). El corte automático en 15 grupos da una familia gigante de 114 de 185 mecánicas. Solo hay familias coherentes donde la co-ocurrencia es fuerte: económico, deducción social, lápiz y papel, negociación.
- **Con pocos tipos, la cobertura binaria se satura**: una colección variada de 12 juegos ya cubre el 100% de jugadores, peso e interacción. Por eso se reportan también niveles **débiles** (un solo juego).

---

## 5. Variables derivadas: reglas exactas

### Interacción (0 ninguna, 1 indirecta, 2 directa) y cooperativo

- **Directa**: afectas, atacas, negocias o pujas contra otro. Take That, Area Majority, Player Elimination, Trading, Negotiation, Alliances, Bribery, Voting, Hidden Roles, Traitor, Semi-Cooperative, Betting and Bluffing, Tug of War, Trick-taking, Ladder Climbing, Hot Potato, todas las subastas, entre otras. Categorías Negotiation y Bluffing.
- **Indirecta**: recursos o espacios compartidos, o carrera. Worker Placement (y variantes), Closed Drafting, Action Drafting, Market, Race, Turn Order: Claim Action, Network and Route Building, Follow, Stock Holding, Deduction, **Team-Based Game**.
- **Combate** (Card Play Conflict Resolution, Combat Results Table, categorías Fighting y Wargame) cuenta como directa **solo si el juego no es cooperativo**.
- **Cooperativo puro** (Cooperative Game sin Traitor ni Semi-Cooperative): interacción competitiva 0, `cooperativo = 1`.
- **Open Drafting no es interacción**: ponía a Wingspan y Cascadia en indirecta.
- **Team-Based es indirecta**, no directa: en Codenames los equipos compiten en carrera. Earth queda en indirecta además por Follow.
- Distribución (`nivel_interaccion`): directa 46.7%, ninguna 34.5%, cooperativo 9.5%, indirecta 9.3%. "Ninguna" está inflada por juegos de la cola con pocas mecánicas etiquetadas.
- Se guardan las mecánicas que activan el nivel (`interaccion_motivos`) para que el agente explique.

### Familias de mecánicas (20)

Draft · Colección y contratos · Selección de acciones · Motor y progresión · Construcción de mazo · Gestión de mano · Cartas clásicas y bazas · Aventura y narrativa · Táctica y guerra · Control de área · Económico y mercado · Subastas · Negociación y diplomacia · Deducción y engaño · Party y comunicación · Losetas y patrones · Dados y riesgo · Lápiz y papel · Movimiento y carreras · Destreza y velocidad.

Aprendizajes de la validación:

- **Estructurales, no se asignan**: Variable Player Powers, Variable Set-up, Modular Board, End Game Bonuses, Solo, Action Points, **Hexagon Grid y Square Grid** (ponían a Catan y Cascadia como tácticos), **Race** (condición de victoria; ponía a Codenames como carrera), **Communication Limits** (restricción de cooperativos; ponía a Gloomhaven como party). Cooperative, Take That y Player Elimination ya están en interacción.
- **Sí son experiencia**: Point to Point Movement (movimiento), Simultaneous Action Selection (selección de acciones), Ordering (party: Timeline, Hitster), Rock-Paper-Scissors (deducción), Hot Potato (party).
- **Team-Based Game no es familia**: ponía a Earth como party.
- En **cooperativos puros** se quita "Negociación y diplomacia" (Pandemic tiene Trading entre compañeros).
- **Respaldo por categoría**, solo si el juego no tiene ninguna familia: Party Game, Trivia y Word Game van a Party; Deduction y Puzzle a Deducción. Rescata escape rooms EXIT, Timeline y juegos de palabras cooperativos.
- **1,927 juegos** quedan sin familia (6.4%), casi todos sin mecánicas etiquetadas. Cosmic Encounter (solo Variable Player Powers) y Netrunner (solo Action Points) están mal etiquetados en BGG.
- **Line of Sight** pone a Cascadia en "Táctica y guerra" (etiquetado de origen; no se hace excepción por un juego).

### Familias temáticas (11 + "Abstracto o sin tema")

Fantasía y mitología · Ciencia ficción y espacio · Horror · Historia antigua y medieval · Historia moderna y guerra · Naturaleza y animales · Economía, industria y ciudades · Exploración y aventura · Intriga y misterio · Cultura pop y humor · Deportes y carreras.

- Fuera del eje: formatos (Card Game, Dice, Miniatures, Party Game, Puzzle, Abstract Strategy, Print & Play...) y categorías que ya cubren otras dimensiones (Fighting, Wargame, Negotiation, Bluffing, Deduction, Territory Building, Real-time, Memory, Trivia).
- **Civilization se excluye**: marca un género, no un periodo (ponía a Terraforming Mars en historia antigua).
- Medical y Mature / Adult fuera (subtema sin grupo y tono).
- "Abstracto o sin tema" es el 26.3% del catálogo: abstractos reales más juegos de la cola etiquetados solo por formato.
- Casos aceptados de etiquetado de origen: Azul en historia (Renaissance), Pandemic en exploración (Travel).

### Niveles de ocasión

- Jugadores: 1, 2, 3 a 4, 5 a 6, 7 o más. Un juego cubre todos los niveles de su rango recomendado.
- Duración: hasta 30, 31 a 60, 61 a 120, más de 120 min.
- Peso: ligero (< 2), medio (2 a 3), pesado (≥ 3).
- Interacción: ninguna, indirecta, directa, cooperativo.

---

## 6. Vector y similitud

### Bloques

| Bloque | Contenido | Columnas |
|---|---|---|
| Mecánicas | TF-IDF binario, mínimo 2 juegos por término, norma 1 | 193 |
| Temática | TF-IDF binario de categorías, mínimo 2 juegos, norma 1 | 83 |
| Ocasión | `weight`, `min_playtime_log`, `max_playtime_log`, `players_lo`, `players_hi` en [0, 1], multiplicado por √(2/5) | 5 |
| Interacción | `interaccion / 2`, `cooperativo` | 2 |

- Se usa `MultiLabelBinarizer` + `TfidfTransformer`, no `TfidfVectorizer` con tokenizador propio, para que el pickle cargue en FastAPI sin depender de funciones del cuaderno.
- Juegos sin mecánicas o categorías: bloque en cero y bandera `tiene_mecanicas` / `tiene_categorias`. **No usar un token común**: con 1,706 juegos sin mecánicas los haría artificialmente idénticos entre sí.

### Fórmula

Similitud por bloque:

- Mecánicas y temática: coseno (producto punto de filas de norma 1).
- Ocasión e interacción: 1 − ‖a − b‖² / 2.

Similitud total: promedio ponderado **sobre los bloques disponibles del par** (si alguno de los dos juegos no tiene mecánicas o categorías, ese bloque se omite y los pesos se renormalizan):

```
sim = Σ w_b · s_b / Σ w_b    (solo bloques con dato en ambos juegos)
```

Pesos finales: mecánicas 0.40, ocasión 0.10, interacción 0.15, temática 0.35.

El vector concatenado (bloques multiplicados por √w_b) sirve para vecinos por distancia euclidiana, pero **no aplica la renormalización**; para decisiones de redundancia usar la fórmula por bloques.

### Cómo se calibraron los pesos

- Pares positivos: juegos de la misma `product_line` (máximo 20 por línea) y reimplementaciones, **7,196 pares de 1,087 líneas**. Negativos: 5,000 pares aleatorios de líneas distintas.
- Similitud media por bloque (aleatorios → redundantes): mecánicas 0.06 → 0.59, temática 0.07 → 0.67, interacción 0.68 → 0.90, ocasión 0.93 → 0.98.
- Rejilla de 969 combinaciones (paso 0.05). AUC con pesos iniciales (0.40 / 0.25 / 0.20 / 0.15) 0.937; máximo 0.968; elegido 0.964.
- Criterio: dentro de la meseta (AUC a menos de 0.005 del máximo), influencia efectiva de mecánicas ≥ temática y máxima influencia de interacción. **Las restricciones van sobre la influencia efectiva (peso × desviación estándar de la similitud del bloque), no sobre el peso nominal**: con pesos nominales iguales, la temática influía más porque su similitud varía más.
- Influencia efectiva final: mecánicas 44.3%, temática 41.3%, interacción 12.8%, ocasión 1.6%.
- La validación mide detección de ediciones, donde la interacción aporta poco; su peso se fijó por criterio dentro de la meseta.
- Que ocasión casi no influya es coherente: las diferencias de jugadores y duración las resuelve la **regla de cobertura**, no la similitud.

---

## 7. Reglas de negocio listas para el requerimiento

### Pregunta 1: ¿es redundante?

Un candidato es **redundante** con la colección si se cumple (a) **o** (b), **y además** (c):

- (a) Regla exacta: comparte `product_line` con algún juego de la colección, o hay relación `reimplements` / `reimplemented_by`.
- (b) Similitud máxima contra la colección ≥ **0.773**.
- (c) **No cubre ningún nivel faltante o débil** de la colección. Si cubre uno, se reporta como "se parece a X, pero es tu primer juego para Y" (caso 7 Wonders / Duel).

Umbral **"parecido"** ≥ **0.417**: solo para ordenar y explicar ("tu juego más parecido es X, por mecánicas y temática"), **nunca como alerta**: daría 96.9% de falsa alarma con 50 juegos.

Cifras del umbral redundante: detecta 42.3% de los pares de una misma línea (el resto los atrapa la regla exacta), 0.20% de falsos positivos por par, 9.5% de probabilidad de falsa alarma contra 50 juegos (1 − (1 − p)⁵⁰). La cifra real será algo peor: una colección se parece más al candidato que un juego al azar.

### Pregunta 2: ¿qué me falta?

- Por cada eje (jugadores, duración, peso, interacción, familias de mecánicas, familias temáticas): niveles cubiertos, **faltantes** (0 juegos) y **débiles** (1 juego, con su nombre).
- Estrella: porcentaje de niveles cubiertos por eje.
- 48 tipos en 6 ejes (`tipos_experiencia.csv`). Los más escasos: Motor y progresión (2.8%), Negociación (3.5%), Cartas clásicas (3.7%), Horror (3.8%), 7 o más jugadores (9.0%). Los más comunes: 3 a 4 jugadores (73.7%) y 2 jugadores (71.0%).

### Pregunta 3: ¿qué compro?

- Valor de cada nivel: faltante = 1 / (niveles del eje); débil = la mitad. Así cada eje vale lo mismo en total.
- Greedy: puntaje = valor de huecos pendientes que cubre / costo; elegir el mejor, marcar sus niveles cubiertos, repetir. Garantía de al menos 63% (1 − 1/e) del óptimo con costo por juego.
- Costo: **1 por juego** por defecto; **por precio** solo entre candidatos con precio (del usuario o confiable). No mezclar en una misma corrida.
- Filtros: excluir redundantes que no cubran huecos; `Users rated` ≥ 1,000 (parámetro); calidad (`Average`) solo desempata.
- **Parámetros para el usuario**: número de juegos, modo (juego o precio), ejes o niveles que no le importan (por ejemplo, si nunca juega con 7), y **Average mínimo** (sin él, el modo precio favorece juegos baratos de calidad baja: Cosmic Wimpout, 6.03).

### Pregunta 4: ¿qué saco hoy? (filtros duros)

- Jugadores: n en `rec_players`; sin encuesta, entre `min_players` y `max_players`. Priorizar los que tienen n en `best_players`.
- Tiempo: `max_playtime` ≤ tiempo disponible; si la duración no se conoce, incluir con aviso (`duracion_imputada`).
- Edad: `community_age` (o `min_age`) ≤ edad del más joven; sin dato, no excluir.
- Ordenar por `Average`.

### Transparencia para el agente

Banderas en el catálogo: `weight_imputado`, `weight_pocos_votos` (menos de 5 votos), `duracion_imputada`, `jugadores_imputados`, `precio_confiable`, `tiene_mecanicas`, `tiene_categorias`. El agente debe decir "estimado" cuando aplique.

---

## 8. Precio

- Cada ID de BGG devuelve todas sus ediciones y traducciones (Catan: 32 productos). Las ofertas de EE. UU. se concentran en la edición principal en inglés.
- Producto representativo: el de más ofertas en EE. UU. con stock (empate: más ofertas totales). Excluye ediciones especiales (Catan Anniversary Wood Edition, $120).
- Precio: mediana de `product` (sin envío), porque `shipping_known` es falso en la mayoría de ofertas y `price` suma el envío solo cuando se conoce.
- Confiable: al menos 2 ofertas con stock. **3,209 juegos** (58.1% del top 1,000, 25.0% del top 10,000). Con 1 oferta aparecen precios de revendedor (Mega Civilization $999.99, Discworld: Ankh-Morpork $389.99).
- **No se imputa**: faltan justo los juegos agotados, cuyo precio depende de la reventa.
- El precio que capture el usuario siempre tiene prioridad.
- Referencias: Catan $50.00, Monopoly $24.99, Wingspan $55.00.

---

## 9. Casos de prueba conocidos

### Pares (similitud con los pesos finales)

| Par | Mecánicas | Ocasión | Interacción | Temática | Total | Etiqueta |
|---|---|---|---|---|---|---|
| Brass: Birmingham / Lancashire | 0.98 | 1.00 | 1.00 | 0.84 | 0.94 | redundante |
| Gloomhaven / Frosthaven | 0.70 | 0.99 | 1.00 | 1.00 | 0.88 | redundante |
| 7 Wonders / 7 Wonders Duel | 0.65 | 0.94 | 0.88 | 1.00 | 0.83 | redundante por similitud, pero Duel cubre 2 jugadores |
| Pandemic / Pandemic Legacy S1 | 0.63 | 1.00 | 1.00 | 0.61 | 0.71 | parecido (redundante por regla exacta) |
| Wingspan / Wyrmspan | 0.78 | 0.99 | 1.00 | 0.41 | 0.70 | parecido |
| Wingspan / Earth | 0.19 | 1.00 | 0.88 | 0.81 | 0.59 | parecido |
| Twilight Imperium 4 / Codenames | 0.10 | 0.64 | 0.88 | 0.00 | 0.24 | distinto |
| Spirit Island / Twilight Struggle | 0.28 | 0.98 | 0.00 | 0.00 | 0.21 | distinto |
| Gloomhaven / Dixit | 0.10 | 0.86 | 0.00 | 0.00 | 0.13 | distinto |

Catan / Catan: Portable Edition salió en 0.71 en la revisión inicial, detrás de Lords of Vegas: BGG etiqueta distinto cada edición. Por eso la regla exacta es imprescindible.

### Clasificaciones de referencia

- Interacción: Wingspan y Cascadia ninguna; Azul, Brass, Earth y Codenames indirecta; Root, Catan, Twilight Struggle y 7 Wonders Duel directa; Pandemic y Spirit Island cooperativos.
- Jugadores: Wingspan recomendado 1 a 4 (caja 1 a 5); Cartographers recomendado 1 a 8 (caja 100).

### Colección de demostración

Wingspan, Brass: Birmingham, Gloomhaven, Codenames, Catan, Azul, Terraforming Mars, Pandemic, 7 Wonders Duel, Cascadia, Spirit Island, Root.

- Faltan: más de 120 min; Subastas, Lápiz y papel, Destreza; Horror, Cultura pop, Deportes, Abstracto.
- Débiles: 5 a 6 y 7 o más jugadores (solo Codenames: Catan y Root no se recomiendan a 5).
- Recomendación por juego: Dune, Boggle, Shadows of Brimstone: Swamps of Death, Blood Bowl: Second Season Edition (cubren todo, unos $305).
- Recomendación por precio: Cosmic Wimpout, The Werewolves of Miller's Hollow, Kingdom Legacy: Feudal Kingdom, Flip 7, Trek 12: Himalaya (unos $52; quedan 0.183 de valor sin cubrir).

---

## 10. Artefactos

| Archivo | Contenido |
|---|---|
| `catalogo.csv` | 30,146 juegos; listas como JSON; `nivel_duracion` y `nivel_peso` como texto |
| `X_mecanicas.npz`, `X_tematica.npz` | Matrices dispersas por bloque (scipy `save_npz`) |
| `X_ocasion.npy`, `X_interaccion.npy` | Matrices densas por bloque |
| `preproceso.pkl` | Vectorizadores, escalador, columnas y límites de ocasión, pesos, umbrales, diccionarios de interacción, familias, respaldo por categoría, temas, niveles de jugadores, umbral de ofertas de precio |
| `tipos_experiencia.csv` | 48 tipos: eje, nivel, definición, proporción del catálogo |

- **Las filas de las matrices coinciden con el orden de `catalogo.csv`**. Al cargar a la base, guardar esa posición (por ejemplo, una columna `fila_vector`).
- Para vectorizar un juego nuevo: aplicar las mismas correcciones de ceros, `limites_ocasion` (log10 y recorte), tope de 10 jugadores, `escalador`, `mlb_*` + `tfidf_*` y las reglas de interacción y familias guardadas en el pickle.
- Entorno: pandas 3.0.5 y pyarrow 25.0.1 dieron `ArrowKeyError` al escribir parquet en ese kernel (en un entorno limpio la misma combinación funciona). Por eso el catálogo se exporta como CSV.

---

## 11. Limitaciones y pendientes

- **1,111 juegos** del ranking sin descargar.
- **"Motor y progresión"** detecta motores de recursos y etiquetas (Brass, Terraforming Mars), no motores de combo de cartas (Wingspan): BGG no tiene mecánica de engine building.
- Un cambio de tema con el mismo motor queda como **parecido**, no redundante (Wingspan / Wyrmspan: 0.70).
- La validación mide **detección de ediciones**; no captura directamente el criterio de solitario multijugador frente a conflicto directo.
- El peso de la cola del ranking es poco confiable (mediana de 8 votos).
- La cola del ranking está pobremente etiquetada: 6.4% sin familia de mecánicas, 26.3% sin tema.
- El precio solo cubre EE. UU. en USD; México no está soportado por la API.
- La falsa alarma de redundancia se midió con pares aleatorios; con colecciones reales será algo mayor.
