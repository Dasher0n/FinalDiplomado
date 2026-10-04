import { ChangeDetectionStrategy, Component, input } from "@angular/core";

export type EstadoNivel = "hueco" | "refuerzo" | "previo";

export interface AporteEje {
  eje: string;
  niveles: { texto: string; clase: string }[];
}

export interface Aporte {
  conCambio: AporteEje[];
  sinCambio: string[];
}

const ORDEN_EJES = [
  "Jugadores",
  "Duración",
  "Peso",
  "Interacción",
  "Mecánicas",
  "Temática",
];
const CLASES: Record<EstadoNivel, string> = {
  hueco: "nivel-hueco",
  refuerzo: "nivel-refuerzo",
  previo: "nivel-previo",
};

interface NivelClasificado {
  eje: string;
  texto: string;
  clase: string;
  cambia: boolean;
}

/** Agrupa por eje: primero los ejes con cambios (los de la clase prioritaria antes) y el resto aparte. */
function agrupar(
  niveles: NivelClasificado[],
  clasePrioritaria: string,
): Aporte {
  const ejes = new Map<string, NivelClasificado[]>();
  for (const nivel of niveles) {
    ejes.set(nivel.eje, [...(ejes.get(nivel.eje) ?? []), nivel]);
  }
  const ordenados = [...ejes.entries()].sort(
    ([a], [b]) => ORDEN_EJES.indexOf(a) - ORDEN_EJES.indexOf(b),
  );
  const conCambio = ordenados
    .filter(([, fichas]) => fichas.some((ficha) => ficha.cambia))
    .sort(
      ([, a], [, b]) =>
        Number(!a.some((f) => f.clase === clasePrioritaria)) -
        Number(!b.some((f) => f.clase === clasePrioritaria)),
    )
    .map(([eje, fichas]) => ({
      eje,
      niveles: fichas.map(({ texto, clase }) => ({ texto, clase })),
    }));
  const sinCambio = ordenados
    .filter(([, fichas]) => !fichas.some((ficha) => ficha.cambia))
    .map(([eje]) => eje);
  return { conCambio, sinCambio };
}

/**
 * Agrupa los niveles de un juego por eje: primero los ejes con algo nuevo (huecos antes que
 * refuerzos) y el resto resumido en "Sin cambios en".
 */
export function construirAporte(
  niveles: { eje: string; texto: string; estado: EstadoNivel }[],
): Aporte {
  return agrupar(
    niveles.map((nivel) => ({
      eje: nivel.eje,
      texto: nivel.texto,
      clase: CLASES[nivel.estado],
      cambia: nivel.estado !== "previo",
    })),
    "nivel-hueco",
  );
}

export type EstadoVenta = "perdida" | "debil" | "cubierto";

export interface BloqueVenta {
  aporte: Aporte;
  perdidas: number;
  debilitados: number;
  conclusion: string;
  sello: "venta-ok" | "venta-perdida";
}

const CLASES_VENTA: Record<EstadoVenta, string> = {
  perdida: "nivel-perdida",
  debil: "nivel-debil",
  cubierto: "nivel-previo",
};

/**
 * Qué pasaría si se vende el juego, nivel por nivel. Usa los conteos antes y después de la
 * simulación y la meta del perfil: sin juegos queda un hueco, por debajo de la meta queda
 * débil y, si no, sigue cubierto (con cuántos juegos lo cubren). Los niveles sin meta no cuentan.
 */
export function construirVenta(
  ejes: [string, string[]][],
  cambios: { eje: string; nivel: string; antes: number; despues: number }[],
  metas: Record<string, Record<string, number>>,
): BloqueVenta {
  const porNivel = new Map(
    cambios.map((cambio) => [`${cambio.eje}|${cambio.nivel}`, cambio]),
  );
  const niveles: NivelClasificado[] = [];
  let perdidas = 0;
  let debilitados = 0;
  for (const [eje, nombres] of ejes) {
    for (const nombre of nombres) {
      const cambio = porNivel.get(`${eje}|${nombre}`);
      const meta = metas[eje]?.[nombre];
      if (!cambio || !meta) continue;
      const estado: EstadoVenta =
        cambio.despues === 0
          ? "perdida"
          : cambio.despues < meta
            ? "debil"
            : "cubierto";
      if (estado === "perdida") perdidas++;
      if (estado === "debil" && cambio.antes >= meta) debilitados++;
      const texto =
        estado === "cubierto"
          ? `${nombre} · ${cambio.despues} ${cambio.despues === 1 ? "juego" : "juegos"}`
          : nombre;
      niveles.push({
        eje,
        texto,
        clase: CLASES_VENTA[estado],
        cambia: estado !== "cubierto",
      });
    }
  }
  const sinPerdidas = perdidas === 0 && debilitados === 0;
  return {
    aporte: agrupar(niveles, "nivel-perdida"),
    perdidas,
    debilitados,
    sello: sinPerdidas ? "venta-ok" : "venta-perdida",
    conclusion: sinPerdidas
      ? "Puedes venderlo sin dejar huecos: lo que aporta lo cubren otros juegos."
      : `Venderlo dejaría ${perdidas} ${perdidas === 1 ? "hueco" : "huecos"} y debilitaría ${debilitados} ${debilitados === 1 ? "nivel" : "niveles"}.`,
  };
}

/** Sello de lacre del veredicto con su texto. */
@Component({
  selector: "app-sello-veredicto",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="veredicto"
    ><span
      class="sello"
      aria-hidden="true"
      [attr.data-veredicto]="veredicto()"
    ></span
    ><b class="veredicto-texto">{{ texto() }}</b></span
  >`,
})
export class SelloVeredictoComponent {
  readonly veredicto = input.required<string>();
  readonly texto = input.required<string>();
}

export interface ItemLeyenda {
  clase: string;
  texto: string;
}

export const LEYENDA_APORTE: ItemLeyenda[] = [
  { clase: "nivel-hueco", texto: "Cubre un hueco" },
  { clase: "nivel-refuerzo", texto: "Refuerza un nivel débil" },
  { clase: "nivel-previo", texto: "Ya lo tenías" },
];
export const LEYENDA_VENTA: ItemLeyenda[] = [
  { clase: "nivel-perdida", texto: "Dejaría un hueco" },
  { clase: "nivel-debil", texto: "Quedaría débil" },
  { clase: "nivel-previo", texto: "Sigue cubierto" },
];

/** Bloque de niveles por eje con tres estados, leyenda corta y "Sin cambios en". */
@Component({
  selector: "app-aporte-coleccion",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<h4 class="aporte-titulo">{{ titulo() }}</h4>
    <ul class="aporte-leyenda" aria-label="Leyenda">
      @for (item of leyenda(); track item.clase) {
        <li class="nivel-chip" [class]="item.clase">{{ item.texto }}</li>
      }
    </ul>
    @for (eje of aporte().conCambio; track eje.eje) {
      <div class="aporte-eje">
        <span class="aporte-eje-nombre">{{ eje.eje }}</span>
        <span class="aporte-eje-fichas">
          @for (nivel of eje.niveles; track nivel.texto) {
            <span class="nivel-chip" [class]="nivel.clase">{{
              nivel.texto
            }}</span>
          }
        </span>
      </div>
    }
    @if (aporte().sinCambio.length) {
      <p class="aporte-sin-cambio">
        Sin cambios en: {{ aporte().sinCambio.join(", ") }}
      </p>
    }`,
})
export class AporteColeccionComponent {
  readonly aporte = input.required<Aporte>();
  readonly titulo = input("Qué aporta a tu colección");
  readonly leyenda = input<ItemLeyenda[]>(LEYENDA_APORTE);
}
