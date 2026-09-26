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

## Decisiones verificadas

- La cascada de BGG fuera del ranking esta omitida por decision de producto. La aplicacion no hara peticiones a BoardGameGeek.
- La unica llamada real de la Fase 0 fue ejecutada por Miguel con `web_search` y `tool_choice: "required"`. El modelo resuelto fue `gpt-5.1-2025-11-13` y devolvio cinco citas para Metropoli de Ideotas Juegos. Esto verifica que `gpt-5.1` admite la herramienta hospedada `web_search`.
- La clave de OpenAI se carga en la aplicacion con `pydantic-settings` desde el entorno y `env_file=".env"`; se modela como `SecretStr`, nunca se imprime ni persiste.
- Excepcion aprobada para Fase 0: no se ejecuta `make lint` porque el Makefile pertenece al andamiaje de Fase 1 y aun no existe.

## Estado por fases

| Fase | Estado | Contenido |
| --- | --- | --- |
| 0 | Completada | Dependencias, artefactos, web_search y decisiones de BGG verificados. |
| 1 | Pendiente de aprobacion | No iniciar sin aprobacion de Miguel. |
