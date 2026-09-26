# Reglas del agente (obligatorias, prevalecen sobre cualquier otra instrucción)

Este archivo lo mantiene Miguel. **Nunca lo edites.** Si una regla te impide avanzar, detente y pregunta.

## Qué estás construyendo

Lee `docs/requerimiento_sommelier_juegos.md` completo antes de empezar y trabaja por las fases que define. Al cerrar cada fase: pruebas en verde, `make lint` limpio, `AGENTS.md` actualizado, un commit, y **te detienes a reportar**. No empiezas la siguiente fase sin que Miguel lo apruebe.

`AGENTS.md` es tu documento vivo (estado, decisiones, trampas verificadas), igual que en `referencia/inverai/AGENTS.md`. Estas reglas no van ahí: viven aquí.

## Archivos y carpetas

- **Solo lectura, nunca modificar, mover, renombrar ni borrar:** `artefactos/`, `docs/`, `referencia/`, `opencode.json`.
- Trabajas únicamente dentro de este repositorio. Nada fuera de él.
- Antes de borrar o mover cualquier archivo que tú no creaste en esta sesión, pregunta.

## Git

- Trabajas en la rama `sprint-1`. Si no existe, la creas desde `main`. **Nunca haces commit en `main`.**
- Un commit por fase como mínimo, con mensaje en español que diga qué fase cierra.
- **Prohibido:** `git push` (lo hace Miguel), `git push --force`, `git reset --hard`, `git rebase`, `git commit --amend` sobre commits ya reportados, `git clean`, borrar ramas, reescribir historial.
- Antes de cada commit, revisa `git status` y `git diff --cached --stat` y confirma que no va ningún archivo de la lista de secretos ni ninguna carpeta de dependencias.

## Secretos y credenciales

- El archivo `.env` lo crea y llena Miguel. **Nunca lo abras, lo leas, lo imprimas, lo copies ni lo edites**, ni con herramientas de lectura ni con comandos (`cat`, `head`, `grep`, `source`, `env`, `printenv`, etc.).
- Nunca pidas la clave de OpenAI en el chat. Si hace falta una clave, dile a Miguel qué variable debe agregar al `.env`.
- Nunca escribas una clave, token o contraseña real en ningún archivo, log, fixture, commit o mensaje. En `.env.example` los valores secretos van vacíos.
- Si en algún momento ves algo con forma de clave (`sk-...`) en un archivo o salida, detente y avisa sin repetirla.

## Sistema e instalaciones

- **No uses `sudo`.** No instalas software del sistema (`apt`, instalaciones globales de npm, `curl ... | sh`, cambios de versión de Python o Node). Si falta algo del sistema, dile a Miguel qué instalar y espera.
- Las dependencias del proyecto sí las instalas, solo con `uv` dentro del proyecto (`uv add`, `uv sync`, `uv pip install -e`) y `npm install` dentro de `frontend/`. Cada dependencia nueva que no esté en el requerimiento se reporta con su motivo.
- Versiones: nunca cambies una versión fijada en el requerimiento para que algo funcione. Si no instala, detente y reporta.
- Docker: puedes usar `docker compose build`, `up`, `down`, `ps` y `logs` de este proyecto. **Prohibido** `docker system prune`, `docker volume rm`, `docker rm -f` sobre contenedores que no sean de este proyecto, o cualquier comando que afecte otros proyectos.

## Llamadas pagadas y red

- Las pruebas **nunca** tocan la red: usan fixtures grabados.
- Llamadas reales a la API de OpenAI desde el código de la app: **solo** en la Fase 0 (una llamada de búsqueda web) y al grabar fixtures o al correr el guion de demo. **Antes de cada tanda pides aprobación** y dices cuántas llamadas harás. Máximo 20 llamadas reales por fase.
- Nunca escribas bucles, reintentos sin límite ni procesos en segundo plano que llamen a APIs pagadas.
- **Prohibido** volver a descargar datos de BoardGameGeek o BoardGamePrices de forma masiva. **Prohibida cualquier petición a BoardGameGeek** (ni verificación ni búsqueda). Prohibido evadir Cloudflare u otras protecciones.

## Forma de trabajar

- **No verificado = no asumido.** Versiones, endpoints y capacidades se comprueban en vivo o en documentación oficial, y se anotan en `AGENTS.md`.
- Si una prueba falla, arreglas el código, **nunca** el valor esperado ni los umbrales del motor, salvo que Miguel lo apruebe.
- Si algo falla dos veces con el mismo enfoque, te detienes y reportas en lugar de probar rodeos.
- Todo en español: código comentado, mensajes de commit, textos de la UI, documentación.
- **Nunca uses el guion largo (em dash)** en código, comentarios, textos ni documentos.
- Cambios pequeños y revisables. Nada de refactorizaciones que no pida la fase actual.
