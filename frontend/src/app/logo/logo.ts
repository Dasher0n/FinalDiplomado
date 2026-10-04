import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  input,
  signal,
} from "@angular/core";

type Accion =
  | "parpadeo"
  | "mirar"
  | "barba"
  | "hechizo"
  | "galleta"
  | "bostezo";

/** Duración y peso relativo de cada acción. Cada una dura de 0,5 a 2 segundos. */
const ACCIONES: { nombre: Accion; peso: number; ms: number }[] = [
  { nombre: "parpadeo", peso: 40, ms: 600 },
  { nombre: "mirar", peso: 20, ms: 1600 },
  { nombre: "barba", peso: 12, ms: 1800 },
  { nombre: "hechizo", peso: 12, ms: 1800 },
  { nombre: "galleta", peso: 8, ms: 2000 },
  { nombre: "bostezo", peso: 8, ms: 1600 },
];
const PROBABILIDAD_DE_HACER_ALGO = 0.7;

/**
 * Dado sabio de la cabecera (animado de vez en cuando) y del avatar del chat (solo parpadea).
 * El SVG está en línea y separado en grupos: sombrero, cejas, ojos, barba, boca, varita y galleta.
 */
@Component({
  selector: "app-logo",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    "(mouseenter)": "alPasarElMouse()",
    "[class.avatar]": "variante() === 'avatar'",
  },
  template: `@if (variante() === "cabecera") {
      <svg
        viewBox="0 0 128 128"
        role="img"
        aria-label="Dado sabio de Wise Dice"
        [attr.data-accion]="accion()"
        [attr.data-congelado]="congelado ? '1' : null"
        [style.--dur]="duracion() + 's'"
      >
        <defs>
          <linearGradient id="marfilc" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#fffaf0" />
            <stop offset=".55" stop-color="#efe0b9" />
            <stop offset="1" stop-color="#cdb67e" />
          </linearGradient>
          <linearGradient id="marfilSombrac" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#d9c68f" />
            <stop offset="1" stop-color="#a98f55" />
          </linearGradient>
          <linearGradient id="barbac" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#ffffff" />
            <stop offset="1" stop-color="#ddd5c0" />
          </linearGradient>
          <linearGradient id="sombreroc" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#2f6b62" />
            <stop offset="1" stop-color="#143a35" />
          </linearGradient>
          <linearGradient id="latonc" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#f6e1a0" />
            <stop offset=".5" stop-color="#d9b457" />
            <stop offset="1" stop-color="#9a7626" />
          </linearGradient>
        </defs>
        <g
          class="cubo"
          stroke="#2a1c13"
          stroke-width="2.6"
          stroke-linejoin="round"
          stroke-linecap="round"
        >
          <polygon
            points="64,34 100,52 100,96 64,114"
            fill="url(#marfilSombrac)"
          />
          <polygon points="28,52 64,70 64,114 28,96" fill="url(#marfilc)" />
          <polygon points="64,34 100,52 64,70 28,52" fill="#f7edd0" />
          <g stroke="none" fill="#2a1c13" fill-opacity=".85">
            <ellipse
              cx="73"
              cy="73"
              rx="3.6"
              ry="4.6"
              transform="rotate(-24 73 73)"
            />
            <ellipse
              cx="82"
              cy="78"
              rx="3.6"
              ry="4.6"
              transform="rotate(-24 82 78)"
            />
            <ellipse
              cx="91"
              cy="83"
              rx="3.6"
              ry="4.6"
              transform="rotate(-24 91 83)"
            />
          </g>
        </g>
        <g
          class="barba"
          stroke="#2a1c13"
          stroke-width="2.6"
          stroke-linejoin="round"
          stroke-linecap="round"
        >
          <path
            d="M 28.0 77.0 L 64.0 95.0 L 64.0 116.0 C 58.0 127.0 40.0 120.0 31.0 107.5 C 28.0 100.0 28.0 92.0 28.0 77.0 Z"
            fill="url(#barbac)"
          />
          <path
            d="M 38.0 97.0 Q 40.0 108.0 44.0 115.0 M 50.0 101.0 Q 52.0 112.0 50.0 119.0"
            fill="none"
            stroke="#a39b88"
            stroke-width="1.3"
          />
          <path
            class="bigote"
            d="M 46.0 88.0 C 41.0 81.5 32.0 78.0 29.0 81.5 C 35.0 86.5 41.0 89.5 46.0 90.0 C 51.0 94.5 58.0 98.0 63.0 98.5 C 60.0 92.0 51.0 86.5 46.0 88.0 Z"
            fill="#fff"
          />
        </g>
        <g class="boca">
          <ellipse
            cx="46.0"
            cy="95.0"
            rx="5"
            ry="3.6"
            fill="#3a1d14"
            stroke="#2a1c13"
            stroke-width="1.6"
          />
        </g>
        <g class="ojos" stroke="none">
          <g class="ojo">
            <circle cx="39.0" cy="71.5" r="4.8" fill="#2a1c13" />
            <circle cx="37.6" cy="70.0" r="1.4" fill="#fff" />
          </g>
          <g class="ojo">
            <circle cx="54.0" cy="79.0" r="4.8" fill="#2a1c13" />
            <circle cx="52.6" cy="77.5" r="1.4" fill="#fff" />
          </g>
        </g>
        <g
          class="cejas"
          fill="#fff"
          stroke="#2a1c13"
          stroke-width="2.2"
          stroke-linejoin="round"
        >
          <path
            d="M 32.0 63.0 Q 38.0 58.0 46.0 68.0 Q 39.0 63.5 36.0 67.0 Z M 49.0 69.5 Q 56.0 67.0 62.0 78.0 Q 58.0 73.0 52.0 75.0 Z"
          />
        </g>
        <g
          class="sombrero"
          stroke="#2a1c13"
          stroke-width="2.6"
          stroke-linejoin="round"
          stroke-linecap="round"
        >
          <path
            d="M66 7 C76 10 84 26 94 44 L36 47 C50 32 58 16 66 7Z"
            fill="url(#sombreroc)"
          />
          <ellipse cx="64" cy="47" rx="38" ry="12" fill="url(#sombreroc)" />
          <path
            d="M33 44 Q64 56 95 44 L97 49 Q64 62 31 49Z"
            fill="url(#latonc)"
          />
          <polygon
            points="64.0,18.0 65.5,22.0 69.7,22.1 66.4,24.8 67.5,28.9 64.0,26.5 60.5,28.9 61.6,24.8 58.3,22.1 62.5,22.0"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <polygon
            points="74.0,32.0 75.0,34.6 77.8,34.8 75.6,36.5 76.4,39.2 74.0,37.7 71.6,39.2 72.4,36.5 70.2,34.8 73.0,34.6"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <polygon
            points="55.0,29.6 55.8,31.8 58.2,31.9 56.4,33.4 57.0,35.8 55.0,34.4 53.0,35.8 53.6,33.4 51.8,31.9 54.2,31.8"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
        </g>
        <g class="chispas">
          <polygon
            points="66.0,4.8 66.8,6.9 69.0,7.0 67.3,8.4 67.9,10.6 66.0,9.3 64.1,10.6 64.7,8.4 63.0,7.0 65.2,6.9"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <polygon
            points="60.0,7.4 60.6,9.1 62.5,9.2 61.0,10.3 61.5,12.1 60.0,11.1 58.5,12.1 59.0,10.3 57.5,9.2 59.4,9.1"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <polygon
            points="72.0,9.4 72.6,11.1 74.5,11.2 73.0,12.3 73.5,14.1 72.0,13.1 70.5,14.1 71.0,12.3 69.5,11.2 71.4,11.1"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <polygon
            points="66.0,1.8 66.5,3.3 68.1,3.3 66.9,4.3 67.3,5.8 66.0,4.9 64.7,5.8 65.1,4.3 63.9,3.3 65.5,3.3"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <polygon
            points="78.0,3.8 78.5,5.3 80.1,5.3 78.9,6.3 79.3,7.8 78.0,6.9 76.7,7.8 77.1,6.3 75.9,5.3 77.5,5.3"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
        </g>
        <g class="galleta" stroke="#2a1c13" stroke-width="1.8">
          <circle cx="0" cy="0" r="6" fill="#d6a45f" />
          <circle cx="-2" cy="-1.6" r="1.1" fill="#4a2b1e" stroke="none" />
          <circle cx="2.2" cy="0.8" r="1.1" fill="#4a2b1e" stroke="none" />
          <circle cx="-0.4" cy="3" r="1" fill="#4a2b1e" stroke="none" />
        </g>
        <g
          class="varita"
          stroke="#2a1c13"
          stroke-width="2.2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <line x1="104" y1="97" x2="119" y2="70" stroke-width="3.2" />
          <polygon
            points="120.0,61.8 121.3,65.2 124.9,65.4 122.1,67.7 123.1,71.2 120.0,69.2 116.9,71.2 117.9,67.7 115.1,65.4 118.7,65.2"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
          <circle cx="104" cy="99" r="5.6" fill="url(#marfilc)" />
        </g>
      </svg>
    } @else {
      <svg viewBox="0 0 128 128" role="img" aria-label="Wise Dice">
        <defs>
          <linearGradient id="marfils" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#fffaf0" />
            <stop offset=".55" stop-color="#efe0b9" />
            <stop offset="1" stop-color="#cdb67e" />
          </linearGradient>
          <linearGradient id="marfilSombras" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#d9c68f" />
            <stop offset="1" stop-color="#a98f55" />
          </linearGradient>
          <linearGradient id="barbas" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#ffffff" />
            <stop offset="1" stop-color="#ddd5c0" />
          </linearGradient>
          <linearGradient id="sombreros" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#2f6b62" />
            <stop offset="1" stop-color="#143a35" />
          </linearGradient>
          <linearGradient id="latons" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#f6e1a0" />
            <stop offset=".5" stop-color="#d9b457" />
            <stop offset="1" stop-color="#9a7626" />
          </linearGradient>
        </defs>
        <g
          stroke="#2a1c13"
          stroke-width="4"
          stroke-linejoin="round"
          stroke-linecap="round"
        >
          <polygon points="64,36 102,54 102,98 64,116" fill="#cdb67e" />
          <polygon points="26,54 64,72 64,116 26,98" fill="#f4e8c6" />
          <polygon points="64,36 102,54 64,72 26,54" fill="#f7edd0" />
          <g stroke="none" fill="#2a1c13" fill-opacity=".85">
            <ellipse
              cx="74"
              cy="76"
              rx="4"
              ry="5"
              transform="rotate(-24 74 76)"
            />
            <ellipse
              cx="90"
              cy="84"
              rx="4"
              ry="5"
              transform="rotate(-24 90 84)"
            />
          </g>
          <path
            d="M 26.0 78.0 L 64.0 96.0 L 64.0 118.0 C 58.0 131.2 38.0 123.7 29.0 110.4 C 26.0 102.0 26.0 94.0 26.0 78.0 Z"
            fill="#fff"
          />
          <path
            d="M66 5 C77 10 86 28 98 46 L32 49 C48 33 57 16 66 5Z"
            fill="#245c55"
          />
          <ellipse cx="64" cy="48" rx="41" ry="11" fill="#245c55" />
          <polygon
            points="63.0,19.0 64.7,23.6 69.7,23.8 65.8,26.9 67.1,31.7 63.0,28.9 58.9,31.7 60.2,26.9 56.3,23.8 61.3,23.6"
            fill="url(#laton{p})"
            stroke="#2a1c13"
            stroke-width="1"
            stroke-linejoin="round"
          />
        </g>
        <g class="ojos" stroke="none" fill="#2a1c13">
          <circle class="ojo" cx="37.0" cy="73.2" r="5.6" />
          <circle class="ojo" cx="53.0" cy="80.8" r="5.6" />
        </g>
      </svg>
    }`,
  styles: [
    `
      :host {
        display: block;
      }
      svg {
        display: block;
        width: 100%;
        height: 100%;
        overflow: visible;
      }
      .ojo,
      .boca ellipse,
      .galleta {
        transform-box: fill-box;
        transform-origin: center;
      }
      .boca ellipse {
        transform: scale(0);
      }
      .chispas,
      .galleta {
        opacity: 0;
      }
      .chispas polygon {
        transform-box: fill-box;
        transform-origin: center;
      }
      .barba {
        transform-origin: 46px 82px;
      }
      .varita {
        transform-origin: 104px 99px;
      }
      svg[data-accion] * {
        animation-duration: var(--dur);
        animation-fill-mode: both;
        animation-timing-function: ease-in-out;
      }
      /* Parpadeo */
      svg[data-accion="parpadeo"] .ojo {
        animation-name: parpadeo;
      }
      /* Mirar a los lados */
      svg[data-accion="mirar"] .ojos {
        animation-name: mirar;
      }
      svg[data-accion="mirar"] .cejas {
        animation-name: cejas-mirar;
      }
      /* Mover la barba */
      svg[data-accion="barba"] .barba {
        animation-name: barba;
      }
      /* Hechizo: la varita sube y salen chispas desde el sombrero */
      svg[data-accion="hechizo"] .varita {
        animation-name: varita;
      }
      svg[data-accion="hechizo"] .chispas {
        animation-name: aparece;
      }
      svg[data-accion="hechizo"] .chispas polygon {
        animation-name: chispa;
      }
      svg[data-accion="hechizo"] .chispas polygon:nth-child(2) {
        --dx: -16px;
        --dy: -12px;
        animation-delay: 0.1s;
      }
      svg[data-accion="hechizo"] .chispas polygon:nth-child(3) {
        --dx: 16px;
        --dy: -14px;
        animation-delay: 0.15s;
      }
      svg[data-accion="hechizo"] .chispas polygon:nth-child(1) {
        --dx: 2px;
        --dy: -20px;
      }
      svg[data-accion="hechizo"] .chispas polygon:nth-child(4) {
        --dx: -6px;
        --dy: -26px;
        animation-delay: 0.2s;
      }
      svg[data-accion="hechizo"] .chispas polygon:nth-child(5) {
        --dx: 20px;
        --dy: -22px;
        animation-delay: 0.25s;
      }
      /* Comer una galleta con tres mordidas */
      svg[data-accion="galleta"] .galleta {
        animation-name: galleta;
      }
      svg[data-accion="galleta"] .boca ellipse {
        animation-name: masticar;
      }
      /* Bostezo */
      svg[data-accion="bostezo"] .boca ellipse {
        animation-name: bostezo-boca;
      }
      svg[data-accion="bostezo"] .ojo {
        animation-name: bostezo-ojos;
      }
      svg[data-accion="bostezo"] .cejas {
        animation-name: bostezo-cejas;
      }
      /* Congelado a mitad de la acción, para capturas de revisión */
      svg[data-congelado] * {
        animation-play-state: paused !important;
        animation-delay: calc(var(--dur) * -0.5) !important;
      }
      @keyframes parpadeo {
        0%,
        100% {
          transform: scaleY(1);
        }
        45% {
          transform: scaleY(0.08);
        }
      }
      @keyframes mirar {
        0%,
        100% {
          transform: translateX(0);
        }
        25%,
        40% {
          transform: translateX(-2.6px);
        }
        65%,
        80% {
          transform: translateX(2.6px);
        }
      }
      @keyframes cejas-mirar {
        0%,
        100% {
          transform: translateY(0);
        }
        50% {
          transform: translateY(-1px);
        }
      }
      @keyframes barba {
        0%,
        100% {
          transform: rotate(0);
        }
        20% {
          transform: rotate(3.4deg);
        }
        45% {
          transform: rotate(-3.4deg);
        }
        70% {
          transform: rotate(2deg);
        }
      }
      @keyframes varita {
        0%,
        100% {
          transform: rotate(0);
        }
        30%,
        60% {
          transform: rotate(-28deg);
        }
      }
      @keyframes aparece {
        0%,
        20% {
          opacity: 0;
        }
        35%,
        80% {
          opacity: 1;
        }
        100% {
          opacity: 0;
        }
      }
      @keyframes chispa {
        0% {
          transform: translate(0, 0) scale(0.3);
        }
        100% {
          transform: translate(var(--dx), var(--dy)) scale(1.4) rotate(120deg);
        }
      }
      @keyframes galleta {
        0% {
          opacity: 0;
          transform: translate(108px, 106px) scale(1);
        }
        10% {
          opacity: 1;
          transform: translate(104px, 104px) scale(1);
        }
        40% {
          opacity: 1;
          transform: translate(50px, 96px) scale(1);
        }
        55% {
          transform: translate(48px, 95px) scale(0.72);
        }
        70% {
          transform: translate(48px, 95px) scale(0.45);
        }
        85% {
          transform: translate(48px, 95px) scale(0.2);
        }
        100% {
          opacity: 0;
          transform: translate(48px, 95px) scale(0);
        }
      }
      @keyframes masticar {
        0%,
        35% {
          transform: scale(0);
        }
        42%,
        62%,
        80% {
          transform: scale(1, 1);
        }
        52%,
        72%,
        90% {
          transform: scale(1, 0.3);
        }
        100% {
          transform: scale(0);
        }
      }
      @keyframes bostezo-boca {
        0%,
        100% {
          transform: scale(0);
        }
        30%,
        70% {
          transform: scale(1.15, 1.5);
        }
      }
      @keyframes bostezo-ojos {
        0%,
        100% {
          transform: scaleY(1);
        }
        30%,
        70% {
          transform: scaleY(0.15);
        }
      }
      @keyframes bostezo-cejas {
        0%,
        100% {
          transform: translateY(0);
        }
        30%,
        70% {
          transform: translateY(-2.5px);
        }
      }
      /* El avatar solo parpadea de vez en cuando */
      @media (prefers-reduced-motion: no-preference) {
        :host(.avatar) .ojo {
          transform-box: fill-box;
          transform-origin: center;
          animation: parpadeo-avatar 8s ease-in-out infinite;
        }
      }
      @keyframes parpadeo-avatar {
        0%,
        93%,
        100% {
          transform: scaleY(1);
        }
        96% {
          transform: scaleY(0.08);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        svg * {
          animation: none !important;
        }
      }
    `,
  ],
})
export class LogoComponent implements OnInit, OnDestroy {
  readonly variante = input<"cabecera" | "avatar">("cabecera");
  protected readonly accion = signal<Accion | null>(null);
  protected readonly duracion = signal(1);
  protected congelado = false;
  private temporizador: number | undefined;
  private fin: number | undefined;
  private readonly alCambiarVisibilidad = () => {
    if (document.hidden) {
      window.clearTimeout(this.temporizador);
    } else {
      this.programar();
    }
  };

  ngOnInit(): void {
    if (this.variante() !== "cabecera") return;
    // Parámetro de desarrollo: ?logo=hechizo fuerza una acción; &mitad=1 la congela a la mitad.
    const parametros = new URLSearchParams(window.location.search);
    const forzada = ACCIONES.find((a) => a.nombre === parametros.get("logo"));
    if (forzada) {
      this.congelado = parametros.get("mitad") === "1";
      window.setTimeout(
        () => this.ejecutar(forzada.nombre, forzada.ms, true),
        600,
      );
    }
    document.addEventListener("visibilitychange", this.alCambiarVisibilidad);
    this.programar();
  }

  ngOnDestroy(): void {
    window.clearTimeout(this.temporizador);
    window.clearTimeout(this.fin);
    document.removeEventListener("visibilitychange", this.alCambiarVisibilidad);
  }

  protected alPasarElMouse(): void {
    if (this.variante() === "cabecera") this.ejecutar("hechizo", 1800);
  }

  private reducido(): boolean {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /** Cada 20 a 40 segundos decide al azar si hace algo y qué. Pausado con la pestaña oculta. */
  private programar(): void {
    window.clearTimeout(this.temporizador);
    if (document.hidden) return;
    const espera = 20000 + Math.random() * 20000;
    this.temporizador = window.setTimeout(() => {
      this.decidir();
      this.programar();
    }, espera);
  }

  private decidir(): void {
    if (document.hidden || this.reducido()) return;
    if (Math.random() > PROBABILIDAD_DE_HACER_ALGO) return;
    const total = ACCIONES.reduce((suma, a) => suma + a.peso, 0);
    let punto = Math.random() * total;
    for (const accion of ACCIONES) {
      punto -= accion.peso;
      if (punto <= 0) {
        this.ejecutar(accion.nombre, accion.ms);
        return;
      }
    }
  }

  /** Una acción nunca se encima con otra. */
  private ejecutar(nombre: Accion, ms: number, forzada = false): void {
    if (this.accion() || (!forzada && this.reducido())) return;
    this.duracion.set(ms / 1000);
    this.accion.set(nombre);
    if (this.congelado) return;
    this.fin = window.setTimeout(() => this.accion.set(null), ms);
  }
}
