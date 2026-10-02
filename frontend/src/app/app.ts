import { DatePipe, DecimalPipe } from "@angular/common";
import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  inject,
  signal,
} from "@angular/core";
import {
  Chart,
  BarController,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  RadarController,
  RadialLinearScale,
  Tooltip,
} from "chart.js";
import { firstValueFrom } from "rxjs";

import {
  CatalogoService,
  CoberturaRespuesta,
  EstaNocheRespuesta,
  EvaluarRespuesta,
  JuegoDetalle,
  JuegoListado,
  PlanCompraRespuesta,
  Perfil,
  VentaImpactoRespuesta,
} from "./core/api/catalogo.service";

Chart.register(
  BarController,
  BarElement,
  CategoryScale,
  RadarController,
  RadialLinearScale,
  PointElement,
  LineElement,
  LinearScale,
  Filler,
  Tooltip,
  Legend,
);

@Component({
  selector: "app-root",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe],
  template: ` <main class="min-h-screen text-stone-900">
    <header class="wise-header px-4 py-3 text-[#f8f1e5]">
      <div class="mx-auto flex max-w-7xl items-center justify-between">
        <div class="flex items-center gap-2">
          <img class="h-10 w-10" src="/wise-dice.svg" alt="Dado sabio" />
          <div>
            <h1 class="font-serif text-2xl">Wise Dice</h1>
            <p class="text-xs text-amber-200">Tu asesor de ludoteca</p>
          </div>
        </div>
        <nav class="wise-nav">
          <button
            [class.active]="perfilActivo() === 'coleccionista'"
            (click)="cambiarPerfil('coleccionista')"
          >
            Mi ludoteca
          </button>
          <button
            [class.active]="perfilActivo() === 'cafe'"
            (click)="cambiarPerfil('cafe')"
          >
            Modo mesa
          </button>
        </nav>
        <nav class="wise-nav">
          <button
            [class.active]="vista() === 'ludoteca'"
            (click)="abrir('ludoteca')"
          >
            Ludoteca</button
          ><button
            [class.active]="vista() === 'cobertura'"
            (click)="abrir('cobertura')"
          >
            Cobertura</button
          ><button [class.active]="vista() === 'chat'" (click)="abrir('chat')">
            Chat
          </button>
        </nav>
      </div>
    </header>

    @if (error()) {
      <p class="mx-auto mt-4 max-w-7xl rounded bg-red-100 p-3 text-red-900">
        {{ error() }}
      </p>
    }

    @if (vista() === "ludoteca") {
      <section class="mx-auto max-w-7xl px-4 py-7">
        <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p class="eyebrow">
              {{ juegos().length }} juegos, {{ etiquetaPerfil() }}
            </p>
            <h2 class="font-serif text-4xl">{{ tituloLudoteca() }}</h2>
          </div>
          <div class="flex gap-2">
            <button
              class="chip"
              [class.active]="modo() === 'estantes'"
              (click)="modo.set('estantes')"
            >
              Estantes</button
            ><button
              class="chip"
              [class.active]="modo() === 'hoy'"
              (click)="modo.set('hoy')"
            >
              ¿Qué jugamos?
            </button>
          </div>
        </div>
        @if (modo() === "estantes") {
          <section class="panel">
            <div class="flex flex-wrap gap-3">
              <label class="grow"
                >Busca en el catálogo<input
                  #busqueda
                  class="input mt-1"
                  placeholder="Ejemplo: Wyrmspan"
                  (input)="buscar(busqueda.value)" /></label
              ><label
                >Agrupar por<select
                  #selector
                  class="input mt-1"
                  (change)="agrupacion.set(selector.value)"
                >
                  <option value="familia">Familia</option>
                  <option value="jugadores">Jugadores</option>
                  <option value="duracion">Duración</option>
                  <option value="peso">Peso</option>
                  <option value="interaccion">Interacción</option>
                </select></label
              >
            </div>
            @if (resultados().length) {
              <div class="mt-3 grid gap-2 sm:grid-cols-2">
                @for (juego of resultados(); track juego.id) {
                  <button class="result" (click)="verDetalle(juego.id)">
                    <img [src]="juego.miniatura_url" alt="" /><span
                      ><b>{{ juego.nombre }}</b
                      ><br /><small>{{
                        juego.anio ?? "Año no disponible"
                      }}</small></span
                    >
                  </button>
                }
              </div>
            }
          </section>
          <div class="bookcase mt-7">
            @for (grupo of grupos(); track grupo.nombre) {
              @for (fila of filasEstante(grupo.juegos); track $index) {
                <section class="case-shelf">
                  <h3 class="shelf-plaque">
                    {{ placa(grupo.nombre) }} · {{ grupo.juegos.length }}
                  </h3>
                  <div class="shelf-rail">
                    <div class="shelf-games">
                      @for (juego of fila; track juego.id) {
                        <button
                          class="game-card"
                          (click)="verDetalle(juego.id)"
                          (mouseenter)="mostrarTooltip($event, juego)"
                          (mouseleave)="tooltip.set(null)"
                        >
                          <span class="game-cover">
                            @if (juego.imagen_url) {
                              <img
                                [src]="juego.imagen_url"
                                [alt]="juego.nombre"
                              />
                            }</span
                          ><span class="game-card-info"
                            ><b>{{ juego.nombre }}</b
                            ><span>{{ rango(juego) }} jugadores</span></span
                          >
                        </button>
                      }
                    </div>
                  </div>
                </section>
              }
            }
          </div>
        } @else {
          <section class="panel">
            <h3 class="font-serif text-2xl">Una partida para esta noche</h3>
            <p class="mt-1 text-sm text-stone-600">
              Indica el grupo y el tiempo para iluminar los juegos que encajan.
            </p>
            <div class="mt-3 flex flex-wrap gap-3">
              <label
                >Jugadores<input
                  #jugadores
                  class="input mt-1"
                  type="number"
                  min="1"
                  placeholder="Ejemplo: 6" /></label
              ><label
                >Minutos<input
                  #minutos
                  class="input mt-1"
                  type="number"
                  min="1"
                  placeholder="Ejemplo: 45" /></label
              ><button
                class="primary self-end"
                (click)="cargarNoche(+jugadores.value, +minutos.value)"
              >
                Ver opciones
              </button>
            </div>
            @if (!noche()) {
              <p class="mt-4 text-sm text-stone-600">
                Aún no hay resultados. Busca una combinación para esta noche.
              </p>
            } @else {
              <p class="mt-4 text-sm font-semibold">
                {{ resumenNoche() }} Las portadas iluminadas pasan los filtros.
              </p>
            }
          </section>
          <div class="bookcase mt-7">
            @for (fila of filasEstante(juegos()); track $index) {
              <section class="case-shelf">
                <h3 class="shelf-plaque">{{ tituloEstante() }}</h3>
                <div class="shelf-rail">
                  <div class="shelf-games">
                    @for (juego of fila; track juego.id) {
                      <button
                        class="game-card"
                        [class.dimmed]="
                          noche() && !recomendadoEstaNoche(juego.id)
                        "
                        [class.highlighted]="recomendadoEstaNoche(juego.id)"
                        (click)="verDetalle(juego.id)"
                        (mouseenter)="mostrarTooltip($event, juego)"
                        (mouseleave)="tooltip.set(null)"
                      >
                        <span class="game-cover">
                          @if (juego.imagen_url) {
                            <img
                              [src]="juego.imagen_url"
                              [alt]="juego.nombre"
                            />
                          }</span
                        ><span class="game-card-info"
                          ><b>{{ juego.nombre }}</b>
                          @if (ajusteEstaNoche(juego.id); as ajuste) {
                            <span>{{ etiquetaAjuste(ajuste) }}</span>
                          }
                        </span>
                      </button>
                    }
                  </div>
                </div>
              </section>
            }
          </div>
        }
      </section>
    }

    @if (vista() === "cobertura") {
      <section class="mx-auto max-w-6xl px-4 py-7">
        <p class="eyebrow">Mapa de variedad · {{ etiquetaPerfil() }}</p>
        <h2 class="font-serif text-4xl">
          Cobertura
          {{ perfilActivo() === "cafe" ? "de la mesa" : "de la colección" }}
        </h2>
        <div class="mt-6 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          <section class="panel coverage-summary">
            <div class="coverage-radar coverage-radar-small">
              <canvas
                id="radar-cobertura"
                aria-label="Radar de cobertura"
              ></canvas>
            </div>
          </section>
          <section class="panel">
            <div class="mt-3 flex flex-wrap items-end gap-3">
              <label
                >Número de juegos<input
                  #planN
                  class="input mt-1"
                  type="number"
                  min="1"
                  max="20"
                  value="5"
              /></label>
              <label
                >Promedio mínimo<input
                  #promedio
                  class="input mt-1"
                  type="number"
                  min="0"
                  max="10"
                  step="0.1"
                  value="6.5"
              /></label>
              <label
                >Votos mínimos<input
                  #votos
                  class="input mt-1"
                  type="number"
                  min="0"
                  value="1000"
              /></label>
              <label
                >Ordenar por<select #orden class="input mt-1">
                  <option value="mejor_ajuste">Mejor ajuste</option>
                  <option value="mejor_valorados">Mejor valorados</option>
                </select></label
              >
              <button
                class="primary"
                (click)="
                  cargarPlan(
                    +planN.value,
                    +promedio.value,
                    +votos.value,
                    orden.value
                  )
                "
              >
                Crear plan
              </button>
            </div>
            <p class="guarantee">
              Cada alternativa usa cobertura pendiente por juego. B y C no
              repiten juegos de las opciones anteriores.
            </p>
            @if (cobertura()) {
              <div class="mt-4 grid gap-3 sm:grid-cols-2">
                @for (eje of ejes(); track eje.nombre) {
                  <article class="coverage">
                    <b>{{ eje.nombre }} · {{ eje.valor.porcentaje }}%</b>
                    <p>
                      <span class="missing">Faltan:</span>
                      {{ eje.valor.faltantes.join(", ") || "Nada" }}
                    </p>
                    <p>
                      <span class="weak">Débiles:</span>
                      {{ claves(eje.valor.debiles).join(", ") || "Nada" }}
                    </p>
                  </article>
                }
              </div>
            }
            @if (plan()) {
              <div class="mt-5 border-t pt-4">
                <div class="chip-legend">
                  ><span class="level-chip missing-chip">Nivel faltante</span
                  ><span class="level-chip weak-chip">Nivel débil</span>
                </div>
                <div class="mt-3 grid gap-3">
                  @for (opcion of plan()!.opciones; track opcion.etiqueta) {
                    <article class="recommendation">
                      <div class="plan-summary">
                        <b>Opción {{ opcion.etiqueta }}</b
                        ><span
                          >{{ opcion.juegos.length }} juegos · valor cubierto
                          {{ opcion.valor_cubierto | number: "1.2-2" }} ·
                          pendiente
                          {{ opcion.valor_pendiente | number: "1.2-2" }}</span
                        >
                      </div>
                      <p class="transiciones">
                        {{ transiciones(opcion.impacto) }}
                      </p>
                      <div class="mt-3 grid gap-3">
                        @for (juego of opcion.juegos; track juego.id) {
                          <article class="recommendation">
                            <div class="flex gap-3">
                              @if (juego.imagen_url) {
                                <img
                                  class="plan-cover"
                                  [src]="juego.imagen_url"
                                  [alt]="juego.nombre"
                                />
                              }
                              <div>
                                <b>{{ juego.nombre }}</b>
                                <p>
                                  @if (juego.precio_usd) {
                                    USD {{ juego.precio_usd }} EE. UU.
                                  } @else {
                                    Precio no disponible
                                  }
                                </p>
                                @if (juego.fecha_precio) {
                                  <small
                                    >Actualizado
                                    {{ juego.fecha_precio | date }}</small
                                  >
                                }
                                @if (juego.url_bgp) {
                                  <a
                                    class="ml-2 text-amber-800 underline"
                                    [href]="juego.url_bgp"
                                    target="_blank"
                                    rel="noopener"
                                    >BoardGamePrices</a
                                  >
                                }
                                <div class="mt-2 flex flex-wrap gap-1">
                                  @for (
                                    nivel of juego.niveles_que_cubre;
                                    track nivel.eje + nivel.nivel
                                  ) {
                                    <span
                                      class="level-chip"
                                      [class.missing-chip]="
                                        nivel.estado === 'faltante'
                                      "
                                      [class.weak-chip]="
                                        nivel.estado === 'debil'
                                      "
                                      >{{ nivel.eje }}: {{ nivel.nivel }}</span
                                    >
                                  }
                                </div>
                              </div>
                              <div class="impacto-lista">
                                @for (
                                  eje of impactoEjes(juego.impacto);
                                  track eje.nombre
                                ) {
                                  @if (eje.cambio) {
                                    <p class="impacto-texto">
                                      {{ eje.nombre }} {{ eje.antes }} →
                                      {{ eje.despues }} ({{
                                        eje.despues - eje.antes >= 0 ? "+" : ""
                                      }}{{ eje.despues - eje.antes }})
                                    </p>
                                  }
                                }
                                <p class="transiciones">
                                  {{ transiciones(juego.impacto) }}
                                </p>
                              </div>
                            </div>
                          </article>
                        }
                      </div>
                    </article>
                  }
                </div>
              </div>
            }
          </section>
        </div>
        <section class="panel mt-6">
          <h3 class="font-serif text-xl">Detalle por experiencia</h3>
          <div class="coverage-chart-grid mt-3">
            <div class="experience-chart">
              <canvas
                id="radar-mecanicas"
                aria-label="Familias mecánicas"
              ></canvas>
            </div>
            <div class="experience-chart">
              <canvas
                id="radar-tematica"
                aria-label="Familias temáticas"
              ></canvas>
            </div>
            <div class="experience-chart">
              <canvas
                id="radar-jugadores"
                aria-label="Cobertura de jugadores"
              ></canvas>
            </div>
            <div class="experience-chart">
              <canvas id="barras-peso" aria-label="Cobertura de peso"></canvas>
            </div>
            <div class="experience-chart">
              <canvas
                id="barras-duracion"
                aria-label="Cobertura de duración"
              ></canvas>
            </div>
            <div class="experience-chart">
              <canvas
                id="barras-interaccion"
                aria-label="Cobertura de interacción"
              ></canvas>
            </div>
          </div>
        </section>
      </section>
    }

    @if (vista() === "chat") {
      <section class="mx-auto max-w-3xl px-4 py-7">
        <p class="eyebrow">Vista previa del asistente</p>
        <h2 class="font-serif text-4xl">Pregunta a Wise Dice</h2>
        <article class="chat-card mt-6">
          <p class="bubble user">
            Tengo ganas de comprar Wyrmspan, ¿vale la pena?
          </p>
          @if (evaluacion()) {
            <div class="bubble answer">
              <p class="text-sm">
                <b>Candidato:</b> {{ evaluacion()!.juego.nombre }}
              </p>
              <p class="text-sm">
                <b>Más parecido:</b>
                {{
                  evaluacion()!.juego_mas_parecido?.nombre ?? "Sin comparación"
                }}
              </p>
              <div class="resultado-evaluacion">
                <b>{{ etiqueta(evaluacion()!.veredicto) }}</b>
                <p>{{ evaluacion()!.veredicto_razones.join(" ") }}</p>
                <p>
                  Similitud total:
                  {{ evaluacion()!.similitud?.total | number: "1.2-2" }}
                </p>
                @for (bloque of barras(evaluacion()!); track bloque.nombre) {
                  <div class="bar-label">
                    {{ bloque.nombre }}
                    <span>{{ bloque.valor | number: "1.0-0" }}%</span>
                  </div>
                  <div class="bar"><i [style.width.%]="bloque.valor"></i></div>
                }
              </div>
            </div>
          } @else {
            <p class="text-sm text-stone-600">
              Preparando la evaluación de Wyrmspan...
            </p>
          }
          <input
            class="input mt-4 w-full"
            disabled
            value="El chat conversacional estará disponible en la siguiente fase."
          />
        </article>
      </section>
    }

    @if (seleccionado()) {
      <div
        class="fixed inset-0 z-10 grid place-items-center bg-stone-950/60 p-4"
        (click)="seleccionado.set(null)"
      >
        <article
          class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-[#fffaf2] p-5"
          (click)="$event.stopPropagation()"
        >
          <button class="float-right text-2xl" (click)="seleccionado.set(null)">
            ×
          </button>
          <div class="grid gap-5 sm:grid-cols-[160px_1fr]">
            @if (seleccionado()!.imagen_url) {
              <img
                class="w-full rounded-lg"
                [src]="seleccionado()!.imagen_url"
                [alt]="seleccionado()!.nombre"
              />
            }
            <div>
              <p class="eyebrow">{{ seleccionado()!.anio }}</p>
              <h2 class="font-serif text-3xl">{{ seleccionado()!.nombre }}</h2>
              <p>
                {{ rango(seleccionado()!) }} jugadores ·
                {{ seleccionado()!.duracion_maxima ?? "n/d" }} min · peso
                {{ peso(seleccionado()!) }}
                @if (seleccionado()!.nivel_peso) {
                  ({{ seleccionado()!.nivel_peso }})
                }
              </p>
              <div class="mt-2 flex flex-wrap gap-1">
                @for (bandera of banderas(seleccionado()!); track bandera) {
                  <span class="level-chip">{{ bandera }}</span>
                }
              </div>
              <button class="primary mt-3" (click)="evaluarDetalle()">
                {{
                  enColeccion(seleccionado()!.id)
                    ? "Ver aporte en mi colección"
                    : "Evaluar compra"
                }}
              </button>
              @if (enColeccion(seleccionado()!.id)) {
                <button class="chip ml-2" (click)="simularVenta()">
                  Simular venta
                </button>
              }
              @if (evaluacionDetalle()) {
                <div class="resultado-evaluacion mt-4">
                  <b>{{ etiqueta(evaluacionDetalle()!.veredicto) }}</b>
                  <p>
                    Más parecido:
                    {{
                      evaluacionDetalle()!.juego_mas_parecido?.nombre ??
                        "sin comparación"
                    }}
                  </p>
                  <p>{{ evaluacionDetalle()!.veredicto_razones.join(" ") }}</p>
                  @if (evaluacionDetalle()!.niveles_que_cubre.length) {
                    <p>
                      También cubre:
                      {{
                        etiquetasNiveles(evaluacionDetalle()!.niveles_que_cubre)
                      }}
                    </p>
                  }
                  <div class="mt-3 impacto-lista">
                    @for (
                      eje of impactoEjes(evaluacionDetalle()!.impacto);
                      track eje.nombre
                    ) {
                      <div
                        class="impacto-fila"
                        [class.sin-cambio]="!eje.cambio"
                      >
                        <span>{{ eje.nombre }}</span
                        ><i></i><b>{{ eje.antes }} → {{ eje.despues }}</b>
                      </div>
                    }
                    <p class="transiciones">
                      {{ transiciones(evaluacionDetalle()!.impacto) }}
                    </p>
                  </div>
                  @if (evaluacionDetalle()!.similares.length) {
                    <p class="mt-3 text-sm font-semibold">
                      Los 3 más parecidos
                    </p>
                    <div class="mt-1 flex flex-wrap gap-1">
                      @for (
                        similar of evaluacionDetalle()!.similares;
                        track similar.juego.id
                      ) {
                        <span class="level-chip"
                          >{{ similar.juego.nombre }}
                          {{ similar.similitud.total | number: "1.2-2" }}</span
                        >
                      }
                    </div>
                  }
                </div>
              }
              @if (ventaDetalle()) {
                <div class="resultado-evaluacion mt-4">
                  <b>Impacto de venderlo</b>
                  <div class="mt-3 impacto-lista">
                    @for (
                      eje of impactoEjes(ventaDetalle()!.impacto);
                      track eje.nombre
                    ) {
                      <div
                        class="impacto-fila"
                        [class.sin-cambio]="!eje.cambio"
                      >
                        <span>{{ eje.nombre }}</span
                        ><i></i><b>{{ eje.antes }} → {{ eje.despues }}</b>
                      </div>
                    }
                    <p class="transiciones">
                      {{ transiciones(ventaDetalle()!.impacto) }}
                    </p>
                  </div>
                </div>
              }
              <p class="mt-4">
                @if (seleccionado()!.precio.precio_usd) {
                  USD {{ seleccionado()!.precio.precio_usd }} EE. UU.
                }
                @if (seleccionado()!.precio.precio_confiable) {
                  <span class="text-amber-800"
                    >Precio con ofertas suficientes</span
                  >
                } @else {
                  <span class="text-amber-800">Precio con pocas ofertas</span>
                }
                @if (seleccionado()!.precio.fecha_precio) {
                  · Actualizado {{ seleccionado()!.precio.fecha_precio | date }}
                }
              </p>
              @if (seleccionado()!.precio.url_bgp) {
                <a
                  class="text-amber-800 underline"
                  [href]="seleccionado()!.precio.url_bgp"
                  target="_blank"
                  rel="noopener"
                  >Ver en BoardGamePrices</a
                >
              }
              <div class="mt-4">
                <p class="mb-2 text-sm font-semibold">Perfil</p>
                <div class="flex flex-wrap gap-1">
                  @for (perfil of perfiles(seleccionado()!); track perfil) {
                    <span class="level-chip">{{ perfil }}</span>
                  }
                </div>
                @if (enColeccion(seleccionado()!.id)) {
                  <button class="chip" (click)="quitar(seleccionado()!.id)">
                    Quitar de colección
                  </button>
                } @else {
                  <button class="primary" (click)="agregar(seleccionado()!.id)">
                    Agregar a colección
                  </button>
                }
              </div>
            </div>
          </div>
        </article>
      </div>
    }
    @if (tooltip(); as dato) {
      <div
        class="game-tooltip"
        [style.left.px]="dato.x"
        [style.top.px]="dato.y"
      >
        <b>{{ dato.nombre }}</b
        ><span>{{ dato.rango }} jugadores</span>
      </div>
    }
  </main>`,
})
export class App {
  private readonly api = inject(CatalogoService);
  private grafica: Chart | null = null;
  private readonly graficas = new Map<string, Chart>();
  protected readonly vista = signal("ludoteca");
  protected readonly perfilActivo = signal("coleccionista");
  protected readonly perfilesDisponibles = signal<Perfil[]>([]);
  protected readonly modo = signal("estantes");
  protected readonly juegos = signal<JuegoDetalle[]>([]);
  protected readonly resultados = signal<JuegoListado[]>([]);
  protected readonly agrupacion = signal("familia");
  protected readonly seleccionado = signal<JuegoDetalle | null>(null);
  protected readonly error = signal("");
  protected readonly cobertura = signal<CoberturaRespuesta | null>(null);
  protected readonly plan = signal<PlanCompraRespuesta | null>(null);
  protected readonly noche = signal<EstaNocheRespuesta | null>(null);
  protected readonly evaluacion = signal<EvaluarRespuesta | null>(null);
  protected readonly evaluacionDetalle = signal<EvaluarRespuesta | null>(null);
  protected readonly ventaDetalle = signal<VentaImpactoRespuesta | null>(null);
  protected readonly tooltip = signal<{
    nombre: string;
    rango: string;
    x: number;
    y: number;
  } | null>(null);

  constructor() {
    void this.cargarPerfiles();
    void this.cargarColeccion();
    void this.cargarPreviewChat();
  }

  protected async cambiarPerfil(perfil: string): Promise<void> {
    if (perfil === this.perfilActivo()) return;
    this.perfilActivo.set(perfil);
    this.plan.set(null);
    this.noche.set(null);
    this.evaluacionDetalle.set(null);
    await this.cargarColeccion();
    if (this.vista() === "cobertura") await this.cargarCobertura();
  }

  protected async abrir(vista: string): Promise<void> {
    this.vista.set(vista);
    if (vista === "cobertura") await this.cargarCobertura();
  }

  protected async buscar(texto: string): Promise<void> {
    this.resultados.set(
      texto.trim().length > 1
        ? (await firstValueFrom(this.api.buscar(texto))).juegos
        : [],
    );
  }

  protected async verDetalle(id: string): Promise<void> {
    this.evaluacionDetalle.set(null);
    this.ventaDetalle.set(null);
    this.seleccionado.set(
      this.juegos().find((juego) => juego.id === id) ??
        (await firstValueFrom(this.api.detalle(id))),
    );
  }

  protected async agregar(id: string): Promise<void> {
    await firstValueFrom(this.api.agregar(id, this.perfilActivo()));
    await this.cargarColeccion();
  }

  protected async quitar(id: string): Promise<void> {
    await firstValueFrom(this.api.quitar(id, this.perfilActivo()));
    this.seleccionado.set(null);
    await this.cargarColeccion();
  }

  protected async cargarNoche(
    jugadores: number,
    minutos: number,
  ): Promise<void> {
    if (jugadores > 0 && minutos > 0)
      this.noche.set(
        await firstValueFrom(
          this.api.estaNoche({ jugadores, minutos }, this.perfilActivo()),
        ),
      );
  }

  protected async cargarPlan(
    n: number,
    average_min: number,
    users_rated_min: number,
    orden: string,
  ): Promise<void> {
    this.plan.set(
      await firstValueFrom(
        this.api.plan(
          {
            n,
            average_min,
            users_rated_min,
            orden,
          },
          this.perfilActivo(),
        ),
      ),
    );
  }

  protected async evaluarDetalle(): Promise<void> {
    if (this.seleccionado())
      this.evaluacionDetalle.set(
        await firstValueFrom(
          this.api.evaluar(this.seleccionado()!.id, this.perfilActivo()),
        ),
      );
  }

  protected async simularVenta(): Promise<void> {
    if (this.seleccionado())
      this.ventaDetalle.set(
        await firstValueFrom(
          this.api.impactoVenta(this.seleccionado()!.id, this.perfilActivo()),
        ),
      );
  }

  protected rango(juego: JuegoDetalle): string {
    return `${juego.jugadores_minimos ?? "n/d"} a ${juego.jugadores_maximos ?? "n/d"}`;
  }
  protected peso(juego: JuegoDetalle): string {
    return juego.peso === null ? "n/d" : juego.peso.toFixed(1);
  }
  protected enColeccion(id: string): boolean {
    return this.juegos().some((juego) => juego.id === id);
  }
  protected claves(valor: object): string[] {
    return Object.keys(valor);
  }
  protected recomendadoEstaNoche(id: string): boolean {
    return this.noche()?.juegos.some((juego) => juego.id === id) ?? false;
  }
  protected ajusteEstaNoche(id: string): string | null {
    return (
      this.noche()?.juegos.find((juego) => juego.id === id)?.nivel_ajuste ??
      null
    );
  }
  protected etiquetaAjuste(ajuste: string): string {
    return ajuste === "ideal"
      ? "Ideal para este grupo"
      : "Funciona para este grupo";
  }
  protected resumenNoche(): string {
    const juegos = this.noche()?.juegos ?? [];
    const ideales = juegos.filter(
      (juego) => juego.nivel_ajuste === "ideal",
    ).length;
    const funciona = juegos.length - ideales;
    return `${juegos.length} opciones: ${ideales} ideales y ${funciona} que funcionan.`;
  }
  protected ejes(): {
    nombre: string;
    valor: {
      porcentaje: number;
      faltantes: string[];
      debiles: object;
      conteo_por_nivel: Record<string, number>;
    };
  }[] {
    return Object.entries(this.cobertura()?.ejes ?? {}).map(
      ([nombre, valor]) => ({ nombre, valor }),
    );
  }
  protected etiqueta(veredicto: string): string {
    return (
      {
        redundante: "Redundante",
        parecido_pero_cubre_hueco: "Se parece, pero cubre un hueco",
        parecido: "Parecido",
        aporta: "Aporta variedad",
      }[veredicto] ?? veredicto
    );
  }
  protected barras(
    resultado: EvaluarRespuesta,
  ): { nombre: string; valor: number }[] {
    const similitud = resultado.similitud;
    return similitud
      ? [
          { nombre: "Mecánicas", valor: 100 * (similitud.mecanicas ?? 0) },
          { nombre: "Ocasión", valor: 100 * similitud.ocasion },
          { nombre: "Interacción", valor: 100 * similitud.interaccion },
          { nombre: "Temática", valor: 100 * (similitud.tematica ?? 0) },
        ]
      : [];
  }
  protected etiquetasNiveles(
    niveles: EvaluarRespuesta["niveles_que_cubre"],
  ): string {
    return niveles.map((nivel) => `${nivel.eje}: ${nivel.nivel}`).join(", ");
  }
  protected banderas(juego: JuegoDetalle): string[] {
    return [
      juego.peso_estimado ? "Peso estimado" : "",
      juego.peso_pocos_votos ? "Peso con pocos votos" : "",
      juego.duracion_estimada ? "Duración estimada" : "",
      juego.jugadores_estimados ? "Jugadores estimados" : "",
    ].filter(Boolean);
  }
  protected perfiles(juego: JuegoDetalle): string[] {
    return [
      ...((juego.familias_mecanicas ?? []) as string[]),
      ...((juego.familias_tematicas ?? []) as string[]),
      juego.nivel_interaccion,
    ].filter((valor): valor is string => Boolean(valor));
  }
  protected placa(valor: string): string {
    return valor.replace(/\b\p{L}/gu, (letra) => letra.toUpperCase());
  }
  protected etiquetaPerfil(): string {
    return this.perfilActivo() === "cafe" ? "Café demo" : "colección personal";
  }
  protected tituloLudoteca(): string {
    return this.perfilActivo() === "cafe"
      ? "Disponibilidad para tu mesa"
      : "Tu librero de experiencias";
  }
  protected tituloEstante(): string {
    return this.perfilActivo() === "cafe"
      ? "Mesa de Café demo"
      : "Tu colección";
  }
  protected mostrarTooltip(evento: MouseEvent, juego: JuegoDetalle): void {
    this.tooltip.set({
      nombre: juego.nombre,
      rango: this.rango(juego),
      x: Math.min(evento.clientX, window.innerWidth - 220),
      y: Math.max(8, evento.clientY - 82),
    });
  }
  protected impactoEjes(impacto: {
    ejes: Record<
      string,
      { antes: Record<string, number>; despues: Record<string, number> }
    >;
  }): { nombre: string; antes: number; despues: number; cambio: boolean }[] {
    return Object.entries(impacto.ejes).map(([nombre, eje]) => ({
      nombre,
      antes: eje.antes["solidos"],
      despues: eje.despues["solidos"],
      cambio: eje.antes["solidos"] !== eje.despues["solidos"],
    }));
  }
  protected transiciones(impacto: {
    cambios_nivel: {
      eje: string;
      nivel: string;
      antes: number;
      despues: number;
    }[];
  }): string {
    const cambios = impacto.cambios_nivel
      .slice(0, 3)
      .map(
        (cambio) =>
          `${cambio.eje}: ${cambio.nivel} ${cambio.antes} → ${cambio.despues}`,
      );
    return cambios.length ? cambios.join(" · ") : "No cambia la cobertura.";
  }
  protected grupos(): { nombre: string; juegos: JuegoDetalle[] }[] {
    const salida = new Map<string, JuegoDetalle[]>();
    for (const juego of this.juegos()) {
      const valores =
        this.agrupacion() === "familia"
          ? juego.familias_mecanicas
          : this.agrupacion() === "jugadores"
            ? [this.rango(juego)]
            : this.agrupacion() === "duracion"
              ? [juego.nivel_duracion]
              : this.agrupacion() === "peso"
                ? [juego.nivel_peso]
                : [juego.nivel_interaccion];
      for (const valor of valores ?? ["Sin clasificar"]) {
        const clave = String(valor ?? "Sin clasificar");
        salida.set(clave, [...(salida.get(clave) ?? []), juego]);
      }
    }
    return [...salida].map(([nombre, juegos]) => ({ nombre, juegos }));
  }

  protected filasEstante(juegos: JuegoDetalle[]): JuegoDetalle[][] {
    const ancho = window.innerWidth;
    const maximo = ancho < 640 ? 3 : ancho < 1024 ? 5 : 7;
    return Array.from(
      { length: Math.ceil(juegos.length / maximo) },
      (_, indice) => juegos.slice(indice * maximo, (indice + 1) * maximo),
    );
  }

  @HostListener("window:resize")
  protected actualizarEstantes(): void {
    // Fuerza una detección para recalcular filas al cambiar el ancho disponible.
    this.juegos.update((juegos) => [...juegos]);
  }

  private async cargarColeccion(): Promise<void> {
    try {
      const coleccion = await firstValueFrom(
        this.api.coleccion(this.perfilActivo()),
      );
      this.juegos.set(
        await Promise.all(
          coleccion.juegos.map((juego) =>
            firstValueFrom(this.api.detalle(juego.id)),
          ),
        ),
      );
    } catch {
      this.error.set("No fue posible cargar la colección demo.");
    }
  }
  private async cargarPreviewChat(): Promise<void> {
    try {
      const juegos = (await firstValueFrom(this.api.buscar("Wyrmspan"))).juegos;
      if (juegos[0])
        this.evaluacion.set(
          await firstValueFrom(
            this.api.evaluar(juegos[0].id, this.perfilActivo()),
          ),
        );
    } catch {
      /* La vista previa queda pendiente si la API no esta disponible. */
    }
  }
  private async cargarCobertura(): Promise<void> {
    this.cobertura.set(
      await firstValueFrom(this.api.cobertura(this.perfilActivo())),
    );
    setTimeout(() => {
      this.dibujarRadar();
      this.dibujarGraficasCobertura();
    });
  }
  private dibujarRadar(): void {
    const canvas = document.getElementById(
      "radar-cobertura",
    ) as HTMLCanvasElement | null;
    if (!canvas || !this.cobertura()) return;
    this.grafica?.destroy();
    const ejes = this.ejes();
    this.grafica = new Chart(canvas, {
      type: "radar",
      data: {
        labels: ejes.map((eje) => eje.nombre),
        datasets: [
          {
            data: ejes.map((eje) => eje.valor.porcentaje),
            backgroundColor: "rgba(178,112,35,.25)",
            borderColor: "#8d5221",
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        scales: { r: { min: 0, max: 100, ticks: { display: false } } },
        plugins: { legend: { display: false } },
      },
    });
  }

  private dibujarGraficasCobertura(): void {
    this.graficas.forEach((grafica) => grafica.destroy());
    this.graficas.clear();
    const ejes = this.cobertura()?.ejes;
    if (!ejes) return;
    this.dibujarConteosRadar("radar-mecanicas", "Mecánicas", ejes["Mecánicas"]);
    this.dibujarConteosRadar("radar-tematica", "Temática", ejes["Temática"]);
    this.dibujarConteosRadar("radar-jugadores", "Jugadores", ejes["Jugadores"]);
    this.dibujarConteosBarras("barras-peso", "Peso", ejes["Peso"]);
    this.dibujarConteosBarras("barras-duracion", "Duración", ejes["Duración"]);
    this.dibujarConteosBarras(
      "barras-interaccion",
      "Interacción",
      ejes["Interacción"],
    );
    const resumen = document.getElementById(
      "barras-resumen",
    ) as HTMLCanvasElement | null;
    if (resumen) {
      this.graficas.set(
        "barras-resumen",
        new Chart(resumen, {
          type: "bar",
          data: {
            labels: Object.keys(ejes),
            datasets: [
              {
                label: "Sólidos",
                data: Object.values(ejes).map(
                  (eje) =>
                    Object.values(eje.conteo_por_nivel).filter(
                      (conteo) => conteo >= 2,
                    ).length,
                ),
                backgroundColor: "#8d5221",
              },
              {
                label: "Débiles",
                data: Object.values(ejes).map(
                  (eje) => Object.keys(eje.debiles).length,
                ),
                backgroundColor: "#b27023",
              },
              {
                label: "Faltantes",
                data: Object.values(ejes).map((eje) => eje.faltantes.length),
                backgroundColor: "#9b3429",
              },
            ],
          },
          options: {
            indexAxis: "y",
            maintainAspectRatio: false,
            scales: {
              x: { stacked: true, ticks: { precision: 0 } },
              y: { stacked: true },
            },
            plugins: { legend: { position: "bottom" } },
          },
        }),
      );
    }
  }

  private dibujarConteosRadar(
    id: string,
    titulo: string,
    eje: CoberturaRespuesta["ejes"][string] | undefined,
  ): void {
    const canvas = document.getElementById(id) as HTMLCanvasElement | null;
    if (!canvas || !eje) return;
    const conteos = eje.conteo_por_nivel;
    this.graficas.set(
      id,
      new Chart(canvas, {
        type: "radar",
        data: {
          labels: Object.keys(conteos),
          datasets: [
            {
              label: titulo,
              data: Object.values(conteos),
              borderColor: "#8d5221",
              backgroundColor: "rgba(178,112,35,.18)",
              pointBackgroundColor: Object.values(conteos).map(
                this.colorConteo,
              ),
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { r: { beginAtZero: true, ticks: { display: false } } },
        },
      }),
    );
  }

  private dibujarConteosBarras(
    id: string,
    titulo: string,
    eje: CoberturaRespuesta["ejes"][string] | undefined,
  ): void {
    const canvas = document.getElementById(id) as HTMLCanvasElement | null;
    if (!canvas || !eje) return;
    const conteos = eje.conteo_por_nivel;
    this.graficas.set(
      id,
      new Chart(canvas, {
        type: "bar",
        data: {
          labels: Object.keys(conteos),
          datasets: [
            {
              label: titulo,
              data: Object.values(conteos),
              backgroundColor: Object.values(conteos).map(this.colorConteo),
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          indexAxis: "y",
          plugins: { legend: { display: false } },
          scales: {
            x: {
              beginAtZero: true,
              max: Math.max(...Object.values(conteos)) + 1,
              ticks: { stepSize: 1, precision: 0 },
            },
          },
        },
      }),
    );
  }

  private colorConteo(conteo: number): string {
    return conteo === 0 ? "#9b3429" : conteo === 1 ? "#b27023" : "#8d5221";
  }

  private async cargarPerfiles(): Promise<void> {
    try {
      this.perfilesDisponibles.set(
        (await firstValueFrom(this.api.perfiles())).perfiles,
      );
    } catch {
      this.error.set("No fue posible cargar los perfiles de ludoteca.");
    }
  }
}
