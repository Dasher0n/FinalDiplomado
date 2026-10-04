// Capturas de la interfaz para revisar el diseño. No llama al LLM: el chat usa una respuesta guardada.
// Uso: node scripts/capturas.mjs            (contra http://localhost:8080)
//      SERVIR_DIST=1 node scripts/capturas.mjs   (sirve dist/ local y enruta /api al backend en :8000)
import { createServer } from "node:http";
import { mkdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { chromium } from "playwright";

const SALIDA = resolve(process.env.SALIDA_DIR ?? "capturas");
const DIST = resolve("dist/sommelier-frontend/browser");
const API = process.env.API_URL ?? "http://localhost:8000";
const TIPOS = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".json": "application/json",
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
  }).listen(4300);
  base = "http://localhost:4300";
}

const respuestaChat = JSON.parse(
  readFileSync("scripts/chat-guardado.json", "utf8"),
);

async function abrirPagina(navegador, ancho, usuario) {
  const contexto = await navegador.newContext({
    viewport: { width: ancho, height: ancho > 800 ? 900 : 844 },
    deviceScaleFactor: 1,
  });
  const pagina = await contexto.newPage();
  // Las preguntas sugeridas del chat son aleatorias: se fija la semilla para capturas comparables.
  await pagina.addInitScript(() => {
    let semilla = 20240;
    Math.random = () => (semilla = (semilla * 16807) % 2147483647) / 2147483647;
  });
  if (process.env.SERVIR_DIST) {
    await pagina.route("**/api/**", async (ruta) => {
      const url = new URL(ruta.request().url());
      await ruta.continue({ url: API + url.pathname + url.search });
    });
  }
  await pagina.route("**/api/v1/chat**", async (ruta) => {
    if (ruta.request().method() !== "POST") return ruta.fallback();
    await ruta.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(respuestaChat),
    });
  });
  // Preguntas sugeridas fijas: el backend las elige al azar en cada carga.
  await pagina.route("**/api/v1/chat/suggestions**", async (ruta) => {
    await ruta.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        preguntas: [
          "¿Qué tal entraría SETI en la colección?",
          "¿Qué le falta a mi colección?",
          "Somos 6 y tenemos 45 minutos, ¿qué saco?",
        ],
      }),
    });
  });
  // Inicia sesión por la pantalla de login con las claves de CAPTURAS_CLAVE_CAFE y
  // CAPTURAS_CLAVE_COLECCIONISTA (el script nunca lee el archivo .env).
  const clave =
    process.env[
      usuario === "cafe"
        ? "CAPTURAS_CLAVE_CAFE"
        : "CAPTURAS_CLAVE_COLECCIONISTA"
    ];
  if (!clave)
    throw new Error(
      `Falta la clave de ${usuario} en el entorno de las capturas`,
    );
  await pagina.goto(base + "/login");
  await pagina.fill('input[name="usuario"]', usuario);
  await pagina.fill('input[name="clave"]', clave);
  await pagina.getByRole("button", { name: "Entrar" }).click();
  await pagina.waitForSelector(".wise-header");
  await pagina.waitForLoadState("networkidle");
  await pagina.waitForTimeout(700);
  return { contexto, pagina };
}
// Página completa: se ocultan solo en la captura los elementos fijos (barra inferior móvil y
// campo del chat), que si no aparecen a mitad de la imagen. `ventana` toma la ventana visible.
async function foto(pagina, nombre, ventana = false) {
  await pagina.waitForTimeout(500);
  const opciones = { path: join(SALIDA, nombre + ".png"), fullPage: !ventana };
  let estilo = null;
  if (!ventana) {
    estilo = await pagina.addStyleTag({
      content:
        "@media (max-width:640px){.wise-nav{display:none !important}} .chat-input{display:none !important}",
    });
  }
  // ALTO_MAX recorta la captura para revisarla más rápido sin recorrer toda la página.
  if (process.env.ALTO_MAX && !ventana) {
    const ancho = pagina.viewportSize().width;
    opciones.clip = {
      x: 0,
      y: 0,
      width: ancho,
      height: Number(process.env.ALTO_MAX),
    };
  }
  await pagina.screenshot(opciones);
  await estilo?.evaluate((nodo) => nodo.remove());
  console.log("capturas/" + nombre + ".png");
}
const nav = (pagina, texto) =>
  pagina.locator(".wise-nav button", { hasText: texto }).click();

const navegador = await chromium.launch();
try {
  // Pantalla de inicio de sesión, sin sesión previa
  for (const ancho of [1440, 390]) {
    const contexto = await navegador.newContext({
      viewport: { width: ancho, height: ancho > 800 ? 900 : 844 },
    });
    const pagina = await contexto.newPage();
    await pagina.goto(base + "/login");
    await pagina.waitForSelector(".login-hoja");
    await pagina.waitForTimeout(700);
    await foto(pagina, `login-${ancho}`, true);
    await contexto.close();
  }
  // Ludoteca, perfil cafe y perfil personal
  for (const [perfil, etiqueta] of [
    ["cafe", "cafe"],
    ["coleccionista", "personal"],
  ]) {
    const { contexto, pagina } = await abrirPagina(navegador, 1440, perfil);
    await foto(pagina, `ludoteca-${etiqueta}-1440`);
    if (perfil === "cafe") {
      // Ficha de SETI abierta desde el buscador, con la evaluación de compra
      await pagina.fill('input[placeholder="Ejemplo: Wyrmspan"]', "SETI");
      await pagina.waitForSelector(".result");
      await pagina.locator(".result", { hasText: "SETI" }).first().click();
      await pagina.waitForSelector(".ficha-modal");
      await pagina.waitForTimeout(400);
      const evaluar = pagina.locator(".ficha-modal button", {
        hasText: /Evaluar compra|Ver aporte/,
      });
      if (await evaluar.count()) {
        await evaluar.first().click();
        await pagina.waitForSelector(".resultado-evaluacion");
      }
      await foto(pagina, "ficha-seti-1440");
      await pagina.keyboard.press("Escape");
      await pagina
        .locator(".ficha-modal > button")
        .click()
        .catch(() => {});
      // Ficha de Wavelength con la simulación de venta abierta (está en la colección de cafe)
      await pagina.fill('input[placeholder="Ejemplo: Wyrmspan"]', "Wavelength");
      await pagina.waitForSelector(".result");
      await pagina
        .locator(".result", { hasText: /Wavelength\s*2019/ })
        .first()
        .click();
      await pagina.waitForSelector(".ficha-modal");
      await pagina
        .locator(".ficha-modal button", { hasText: "Simular venta" })
        .click();
      await pagina.waitForSelector(".venta-conclusion");
      await foto(pagina, "ficha-wavelength-venta-1440");
      await pagina.keyboard.press("Escape");
      await pagina
        .locator(".ficha-modal > button")
        .click()
        .catch(() => {});
      // Cobertura con plan
      await nav(pagina, "Cobertura");
      await pagina.waitForSelector("#radar-cobertura");
      await pagina.getByRole("button", { name: /Crear plan/i }).click();
      await pagina
        .waitForSelector(".bento-plan", { timeout: 15000 })
        .catch(() => {});
      await pagina.waitForTimeout(1500);
      await foto(pagina, "cobertura-1440");
      // Chat con una conversación guardada
      await nav(pagina, "Chat");
      await pagina.fill("#chat-input", "¿Vale la pena SETI?");
      await pagina.keyboard.press("Enter");
      await pagina
        .waitForSelector(".bubble.answer .sello, .game-summary-card", {
          timeout: 10000,
        })
        .catch(() => {});
      await foto(pagina, "chat-1440");
      await foto(pagina, "chat-1440-ventana", true);
    }
    await contexto.close();
  }
  // Móvil, 390 px
  {
    const { contexto, pagina } = await abrirPagina(navegador, 390, "cafe");
    await foto(pagina, "ludoteca-cafe-390");
    await foto(pagina, "ludoteca-cafe-390-ventana", true);
    await nav(pagina, "Chat");
    await pagina.fill("#chat-input", "¿Vale la pena SETI?");
    await pagina.keyboard.press("Enter");
    await pagina
      .waitForSelector(".game-summary-card", { timeout: 10000 })
      .catch(() => {});
    await foto(pagina, "chat-390");
    await foto(pagina, "chat-390-ventana", true);
    await contexto.close();
  }
} finally {
  await navegador.close();
  servidor?.close();
}
