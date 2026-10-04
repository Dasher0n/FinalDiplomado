# Wise Dice (Sommelier de juegos de mesa)

Optimizador de ludotecas para cafés de juegos de mesa. Backend FastAPI con SQLite, frontend Angular y un chat con planner, narrador y crítico.

## Desarrollo local

```bash
make seed      # importa el catálogo y las colecciones demo
make test      # pruebas del backend y del frontend
make lint
docker compose up --build -d   # backend en :8000 y frontend en :8080
```

Las variables van en `.env` (copia `.env.example` y llena los valores). El backend no arranca sin `JWT_SECRET`.

## Despliegue

### Arquitectura

```
Navegador ──► Vercel (frontend Angular estático)
                 │  vercel.json: /api/:path* se reescribe a
                 ▼
         https://habitable-factoid-levitate.ngrok-free.dev/api/...
                 │  ngrok (dominio fijo) ──► puerto 8000 de la máquina
                 ▼
         Docker local: backend FastAPI + SQLite en un volumen
```

El frontend usa rutas relativas (`/api/v1/...`). Vercel las reenvía al dominio de ngrok con una reescritura del lado del servidor, así el navegador siempre habla con un solo origen y no hay CORS. El interceptor HTTP agrega `ngrok-skip-browser-warning: 1` a las llamadas al API para que ngrok no responda con su página de aviso. El chat responde con JSON normal (no usa SSE ni respuestas por fragmentos).

### Valores para Vercel

| Campo | Valor |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Other |
| Install Command | `npm install --force` (ya está en `frontend/vercel.json`) |
| Build Command | `npm run build` |
| Output Directory | `dist/sommelier-frontend/browser` |
| Node.js Version | 24.x (Angular 22 exige Node 22.22.3 o superior, o 24.15 o superior) |

`frontend/vercel.json` reescribe primero `/api/:path*` hacia ngrok y después todo lo demás a `/index.html`, para que las rutas de Angular (`/login`) funcionen al recargar.

### Variables de `.env` para el despliegue

- `ENVIRONMENT=prod`: cierra `/docs`, `/redoc` y `/openapi.json`.
- `JWT_SECRET`, `JWT_HORAS`, `CLAVE_USUARIO_CAFE` y `CLAVE_USUARIO_COLECCIONISTA`: sesión y cuentas.
- `OPENAI_API_KEY` y el resto de las variables del modelo.
- `CORS_ORIGINS` es opcional: con la reescritura de Vercel el navegador no llama al backend directamente.

El compose arranca uvicorn con `--proxy-headers` y confía en esos encabezados solo desde `127.0.0.1` y `172.16.0.0/12` (la red privada de Docker por donde llega ngrok).

### Cómo arrancar el día de la demo

```bash
docker compose up -d
ngrok http 8000 --url https://habitable-factoid-levitate.ngrok-free.dev
```

Comprueba `https://habitable-factoid-levitate.ngrok-free.dev/api/v1/health` y abre la URL de Vercel.

### Limitaciones

- La máquina con Docker y ngrok debe estar encendida y con conexión mientras dure la demo.
- El plan gratuito de ngrok tiene límites: 20 mil peticiones y 1 GB de transferencia al mes.
- La base SQLite vive en un volumen local de Docker.
- Alternativa más estable: un servicio de alojamiento con disco persistente para el backend (por ejemplo Render o Fly.io con un volumen), apuntando la reescritura de Vercel a su dominio.
