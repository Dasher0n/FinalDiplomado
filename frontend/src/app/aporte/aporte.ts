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

/**
 * Agrupa los niveles de un juego por eje: primero los ejes con algo nuevo (huecos antes que
 * refuerzos) y el resto resumido en "Sin cambios en".
 */
export function construirAporte(
  niveles: { eje: string; texto: string; estado: EstadoNivel }[],
): Aporte {
  const ejes = new Map<string, AporteEje & { estados: Set<EstadoNivel> }>();
  for (const nivel of niveles) {
    const actual = ejes.get(nivel.eje) ?? {
      eje: nivel.eje,
      niveles: [],
      estados: new Set<EstadoNivel>(),
    };
    actual.niveles.push({ texto: nivel.texto, clase: CLASES[nivel.estado] });
    actual.estados.add(nivel.estado);
    ejes.set(nivel.eje, actual);
  }
  const ordenados = [...ejes.values()].sort(
    (a, b) => ORDEN_EJES.indexOf(a.eje) - ORDEN_EJES.indexOf(b.eje),
  );
  const conCambio = ordenados
    .filter((eje) => eje.estados.has("hueco") || eje.estados.has("refuerzo"))
    .sort(
      (a, b) =>
        Number(!a.estados.has("hueco")) - Number(!b.estados.has("hueco")),
    )
    .map(({ eje, niveles: fichas }) => ({ eje, niveles: fichas }));
  const sinCambio = ordenados
    .filter((eje) => !eje.estados.has("hueco") && !eje.estados.has("refuerzo"))
    .map((eje) => eje.eje);
  return { conCambio, sinCambio };
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

/** Bloque "Qué aporta a tu colección": píldoras por eje con tres estados y leyenda corta. */
@Component({
  selector: "app-aporte-coleccion",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<h4 class="aporte-titulo">Qué aporta a tu colección</h4>
    <ul class="aporte-leyenda" aria-label="Leyenda">
      <li class="nivel-chip nivel-hueco">Cubre un hueco</li>
      <li class="nivel-chip nivel-refuerzo">Refuerza un nivel débil</li>
      <li class="nivel-chip nivel-previo">Ya lo tenías</li>
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
}
