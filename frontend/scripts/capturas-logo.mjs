// Captura la cabecera con cada acción del logo congelada a la mitad (parámetro ?logo=...&mitad=1).
import { createServer } from "node:http";
import { mkdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { chromium } from "playwright";

const SALIDA = resolve(process.env.SALIDA_DIR ?? "capturas/logo");
const DIST = resolve("dist/sommelier-frontend/browser");
const API = process.env.API_URL ?? "http://localhost:8000";
const TIPOS = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};
mkdirSync(SALIDA, { recursive: true });
let base = process.env.BASE_URL ?? "http://localhost:8080";
let servidor = null;
if (process.env.SERVIR_DIST) {
  servidor = createServer((req, res) => {
    const ruta = join(DIST, decodeURIComponent(req.url.split("?")[0]));
    const archivo =
      existsSync(ruta) && statSync(ruta).isFile()
        ? ruta
        : join(DIST, "index.html");
    res.writeHead(200, {
      "content-type": TIPOS[extname(archivo)] ?? "application/octet-stream",
    });
    res.end(readFileSync(archivo));
  }).listen(4302);
  base = "http://localhost:4302";
}
const navegador = await chromium.launch();
const acciones = [
  "reposo",
  "parpadeo",
  "mirar",
  "barba",
  "hechizo",
  "galleta",
  "bostezo",
];
try {
  for (const accion of acciones) {
    const pagina = await navegador.newPage({
      viewport: { width: 1440, height: 300 },
      deviceScaleFactor: 10,
    });
    if (process.env.SERVIR_DIST) {
      await pagina.route("**/api/**", (ruta) =>
        ruta.continue({ url: API + new URL(ruta.request().url()).pathname }),
      );
    }
    await pagina.goto(
      `${base}/?${accion === "reposo" ? "" : `logo=${accion}&mitad=1`}`,
    );
    await pagina.waitForLoadState("networkidle");
    await pagina.waitForTimeout(1500);
    // Se captura solo el personaje, muy ampliado, para revisar cada acción a mitad de animación.
    await pagina
      .locator("app-logo.logo-cabecera")
      .screenshot({ path: join(SALIDA, `logo-${accion}.png`) });
    console.log(`capturas/logo/logo-${accion}.png`);
    await pagina.close();
  }
} finally {
  await navegador.close();
  servidor?.close();
}
