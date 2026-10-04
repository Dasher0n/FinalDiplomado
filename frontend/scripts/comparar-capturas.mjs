// Compara dos carpetas de capturas píxel a píxel y reporta el porcentaje de píxeles distintos.
// Uso: node scripts/comparar-capturas.mjs capturas/antes capturas/despues
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";

const { PNG } = createRequire(import.meta.url)(
  "playwright-core/lib/utilsBundle",
);
const [antes, despues] = process.argv.slice(2);
let distintas = 0;
for (const archivo of readdirSync(antes).filter((nombre) =>
  nombre.endsWith(".png"),
)) {
  const a = PNG.sync.read(readFileSync(join(antes, archivo)));
  const b = PNG.sync.read(readFileSync(join(despues, archivo)));
  if (a.width !== b.width || a.height !== b.height) {
    console.log(
      `${archivo}: tamaño distinto (${a.width}x${a.height} contra ${b.width}x${b.height})`,
    );
    distintas++;
    continue;
  }
  let cambios = 0;
  for (let i = 0; i < a.data.length; i += 4) {
    const delta =
      Math.abs(a.data[i] - b.data[i]) +
      Math.abs(a.data[i + 1] - b.data[i + 1]) +
      Math.abs(a.data[i + 2] - b.data[i + 2]);
    if (delta > 12) cambios++;
  }
  const porcentaje = (100 * cambios) / (a.width * a.height);
  if (porcentaje > 0) distintas++;
  console.log(`${archivo}: ${porcentaje.toFixed(4)}% de píxeles distintos`);
}
console.log(
  distintas === 0
    ? "Sin cambios visibles."
    : `${distintas} captura(s) con diferencias.`,
);
