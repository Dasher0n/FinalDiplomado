import { DecimalPipe } from "@angular/common";
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
  ChatRespuesta,
} from "./core/api/catalogo.service";
import { primeraMayuscula } from "./core/etiquetas";
import { renderMarkdown } from "./core/markdown";

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
Chart.defaults.font.family = '"Source Serif 4", Georgia, serif';
Chart.defaults.color = "#4d3727";

@Component({
  selector: "app-root",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe],
  template: ` <main class="min-h-screen">
    <header class="wise-header text-[#f8f1e5]">
      <div class="mx-auto flex max-w-7xl items-center justify-between">
        <div class="brand-plate">
          <img class="h-10 w-10" src="/wise-dice.svg" alt="Dado sabio" />
          <div>
            <h1 class="brand-name">Wise Dice</h1>
            <p class="brand-tag">Tu asesor de ludoteca</p>
          </div>
        </div>
        <div class="header-actions">
          <label class="profile-selector"
            >Perfil<select
              #perfilSelector
              [value]="perfilActivo()"
              (change)="cambiarPerfil(perfilSelector.value)"
            >
              <option value="cafe">Café demo</option>
              <option value="coleccionista">Colección personal</option>
            </select></label
          >
          <nav class="wise-nav" aria-label="Secciones">
            <button
              [class.active]="vista() === 'ludoteca'"
              [attr.aria-current]="vista() === 'ludoteca' ? 'page' : null"
              (click)="abrir('ludoteca')"
            >
              Ludoteca</button
            ><button
              [class.active]="vista() === 'cobertura'"
              [attr.aria-current]="vista() === 'cobertura' ? 'page' : null"
              (click)="abrir('cobertura')"
            >
              Cobertura</button
            ><button
              [class.active]="vista() === 'chat'"
              [attr.aria-current]="vista() === 'chat' ? 'page' : null"
              (click)="abrir('chat')"
            >
              Chat
            </button>
          </nav>
        </div>
      </div>
    </header>

    @if (error()) {
      <p class="alerta mx-auto mt-4 max-w-7xl rounded p-3">
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
            <p class="screen-intro">{{ explicacionLudoteca() }}</p>
            <details class="how-it-works">
              <summary>¿Cómo funciona?</summary>
              <p>
                Explora las portadas y abre cualquier juego para ver su ficha.
              </p>
              <p>Elige una agrupación para encontrar experiencias similares.</p>
              <p>Busca en el catálogo para añadir juegos a esta ludoteca.</p>
            </details>
          </div>
        </div>
        <section class="panel rollo table-filter">
          <h3 class="font-serif text-2xl">¿Qué jugamos?</h3>
          <div class="mt-3 flex flex-wrap gap-3">
            <label
              >Jugadores<input
                #jugadores
                class="input mt-1"
                type="number"
                min="1"
                placeholder="Ejemplo: 4"
            /></label>
            <label
              >Minutos<input
                #minutos
                class="input mt-1"
                type="number"
                min="1"
                placeholder="Ejemplo: 60"
            /></label>
            <label
              >Edad mínima<input
                #edad
                class="input mt-1"
                type="number"
                min="1"
                placeholder="Opcional"
            /></label>
            <button
              class="primary self-end"
              (click)="
                cargarNoche(+jugadores.value, +minutos.value, +edad.value)
              "
            >
              Filtrar
            </button>
            <button
              class="chip self-end"
              (click)="limpiarNoche(jugadores, minutos, edad)"
            >
              Limpiar
            </button>
          </div>
          @if (noche()) {
            <div class="table-legend">
              <span class="ideal-marker">Ideal: resplandor dorado</span
              ><span>Funciona: color normal</span
              ><span class="dimmed-marker">No cumple: oscurecido</span>
            </div>
          }
        </section>
        @if (modo() === "estantes") {
          <section class="panel rollo">
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
              <button class="chip self-end" (click)="alternarVistaEstantes()">
                Vista: {{ vistaCompactaActiva() ? "compacta" : "cómoda" }}
              </button>
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
          <div
            class="bookcase-grid mt-7"
            [class.compact-bookcases]="vistaCompactaActiva()"
          >
            @for (grupo of grupos(); track grupo.nombre) {
              <section
                class="bookcase"
                [class.bookcase-wide]="grupo.juegos.length > 6"
              >
                <h3 class="shelf-plaque">
                  {{ placa(grupo.nombre) }} · {{ grupo.juegos.length }}
                </h3>
                <div class="shelf-games">
                  @for (juego of grupo.juegos; track juego.id) {
                    <button
                      class="game-card"
                      [class.dimmed]="
                        noche() && !recomendadoEstaNoche(juego.id)
                      "
                      [class.highlighted]="
                        ajusteEstaNoche(juego.id) === 'ideal'
                      "
                      (click)="verDetalle(juego.id)"
                      (mouseenter)="mostrarTooltip($event, juego)"
                      (mouseleave)="tooltip.set(null)"
                    >
                      <span class="game-cover">
                        @if (juego.imagen_url) {
                          <img [src]="juego.imagen_url" [alt]="juego.nombre" />
                        }</span
                      ><span class="game-card-info"
                        ><b>{{ juego.nombre }}</b
                        ><span>{{ rango(juego) }} jugadores</span></span
                      >
                    </button>
                  }
                </div>
              </section>
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
              <div class="table-legend">
                <span class="ideal-marker">Ideal: resplandor dorado</span>
                <span>Funciona: color normal</span>
                <span class="dimmed-marker">No cumple: oscurecido</span>
              </div>
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
                        [class.highlighted]="
                          ajusteEstaNoche(juego.id) === 'ideal'
                        "
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
        <p class="screen-intro">
          Mira qué experiencias ya cubre tu ludoteca y encuentra los huecos que
          aún vale la pena explorar.
        </p>
        <details class="how-it-works">
          <summary>¿Cómo funciona?</summary>
          <p>El radar resume los seis ejes de experiencia de la colección.</p>
          <p>Faltante significa que no hay juegos; débil, que solo hay uno.</p>
          <p>
            El plan prioriza juegos que cubren más variedad sin repetir
            opciones.
          </p>
        </details>
        <div class="bento mt-6">
          <section class="panel bento-resumen">
            <h3 class="font-serif text-xl">Resumen</h3>
            @if (cobertura()) {
              <ul class="meter-list">
                @for (eje of ejes(); track eje.nombre) {
                  <li>
                    <span class="meter-label"
                      ><span>{{ eje.nombre }}</span
                      ><b>{{ eje.valor.porcentaje }}%</b></span
                    >
                    <span class="meter" aria-hidden="true"
                      ><i [style.width.%]="eje.valor.porcentaje"></i
                    ></span>
                  </li>
                }
              </ul>
            }
          </section>
          <section class="panel bento-radar coverage-summary">
            <h3 class="font-serif text-xl">Radar</h3>
            <div class="coverage-radar coverage-radar-small">
              <canvas
                id="radar-cobertura"
                aria-label="Radar de cobertura"
              ></canvas>
            </div>
          </section>
          <section class="panel bento-controles">
            <h3 class="font-serif text-xl">Plan de compra</h3>
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
          </section>
          @if (cobertura()) {
            <section class="panel bento-deficits">
              <h3 class="font-serif text-xl">Déficits por eje</h3>
              <div class="deficit-grid mt-3">
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
            </section>
          }
          @if (plan()) {
            <div class="bento-leyenda chip-legend">
              <span class="level-chip missing-chip">Nivel faltante</span
              ><span class="level-chip weak-chip">Nivel débil</span>
            </div>
            @for (opcion of plan()!.opciones; track opcion.etiqueta) {
              <section
                class="panel bento-plan"
                [attr.data-opcion]="opcion.etiqueta"
              >
                <div class="plan-summary">
                  <h3 class="plan-titulo font-serif">
                    Opción {{ opcion.etiqueta }}
                  </h3>
                  <span
                    >{{ opcion.juegos.length }} juegos · valor cubierto
                    {{ opcion.valor_cubierto | number: "1.2-2" }} · pendiente
                    {{ opcion.valor_pendiente | number: "1.2-2" }}</span
                  >
                </div>
                <p class="transiciones">
                  {{ transiciones(opcion.impacto) }}
                </p>
                <div class="plan-juegos mt-3">
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
                              {{ formatoPrecio(juego.precio_usd) }} EE. UU.
                            } @else {
                              Precio no disponible
                            }
                          </p>
                          @if (juego.fecha_precio) {
                            <small
                              >Actualizado
                              {{ fechaCorta(juego.fecha_precio) }}</small
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
                                [class.weak-chip]="nivel.estado === 'debil'"
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
              </section>
            }
          }
          <section class="panel bento-detalle">
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
                <canvas
                  id="barras-peso"
                  aria-label="Cobertura de peso"
                ></canvas>
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
        </div>
      </section>
    }

    @if (vista() === "chat") {
      <section class="chat-screen mx-auto max-w-[860px] px-4 py-7">
        <p class="eyebrow">Asistente de ludoteca · {{ etiquetaPerfil() }}</p>
        <h2 class="font-serif text-4xl">Pregunta a Wise Dice</h2>
        <article class="chat-card mt-6">
          @for (mensaje of mensajesChat(); track $index) {
            @if (mensaje.role === "user") {
              <p class="bubble user">{{ mensaje.texto }}</p>
            } @else {
              <div class="assistant-message">
                <img class="chat-avatar" src="/wise-dice.svg" alt="Wise Dice" />
                <div class="bubble answer">
                  <div
                    class="markdown"
                    [innerHTML]="markdown(mensaje.texto)"
                  ></div>
                  @if (mensaje.bienvenida) {
                    <div class="suggested-questions">
                      @for (
                        preguntaSugerida of preguntasSugeridas();
                        track preguntaSugerida
                      ) {
                        <button
                          class="chip"
                          (click)="enviarChat(preguntaSugerida)"
                        >
                          {{ preguntaSugerida }}
                        </button>
                      }
                    </div>
                  }
                  @if (mensaje.respuesta; as respuesta) {
                    <div class="mt-3 flex flex-wrap gap-1">
                      @for (paso of respuesta.plan; track paso.id) {
                        <span class="level-chip"
                          >{{ etiquetaTool(paso.tool) }} ·
                          {{ paso.estado }}</span
                        >
                      }
                    </div>
                    @for (tarjeta of respuesta.tarjetas; track $index) {
                      @if (tarjetaJuego(tarjeta); as juego) {
                        <article class="recommendation game-summary-card mt-3">
                          @if (tarjetaImagen(tarjeta); as imagen) {
                            <img
                              class="chat-card-cover"
                              [src]="imagen"
                              [alt]="juego.nombre"
                            />
                          }
                          <b>{{ juego.nombre }}</b>
                          @if (tarjetaFicha(tarjeta); as ficha) {
                            <p>{{ ficha }}</p>
                          }
                          @if (tarjetaVeredicto(tarjeta); as veredicto) {
                            <p>
                              <span
                                class="sello"
                                [attr.data-veredicto]="veredicto"
                                >{{ etiqueta(veredicto) }}</span
                              >
                            </p>
                          }
                          @if (tarjetaPrecio(tarjeta); as precio) {
                            <p>{{ precio }}</p>
                          }
                          @if (tarjetaEnlace(tarjeta); as enlace) {
                            <a [href]="enlace" target="_blank" rel="noopener"
                              >Ver en BoardGamePrices</a
                            >
                          }
                        </article>
                      }
                    }
                    @if (
                      (respuesta.candidatos ?? []).length ||
                      respuesta.sugerir_nombre_ingles
                    ) {
                      <div class="mt-3 flex flex-wrap gap-2">
                        @for (
                          candidato of respuesta.candidatos ?? [];
                          track candidato.id
                        ) {
                          <button
                            class="chip"
                            (click)="enviarChat(candidato.nombre, candidato.id)"
                          >
                            ¿Te refieres a {{ candidato.nombre }}?
                          </button>
                        }
                        <button class="chip" (click)="escribirNombreIngles()">
                          Escribir el nombre en inglés
                        </button>
                      </div>
                    }
                  }
                </div>
              </div>
            }
          }
          @if (chatEsperando()) {
            <div class="assistant-message">
              <img class="chat-avatar" src="/wise-dice.svg" alt="Wise Dice" />
              <p class="bubble answer thinking">
                <span class="thinking-die">🎲</span> Tirando los dados…
              </p>
            </div>
          }
          @if (chatError()) {
            <p class="chat-error">
              No pude responder ahora. Inténtalo de nuevo en unos momentos.
            </p>
          }
          <div class="chat-input">
            <input
              id="chat-input"
              #pregunta
              class="input w-full"
              [disabled]="chatEsperando()"
              placeholder="Ejemplo: ¿Qué le falta a mi colección?"
              (keyup.enter)="enviarChat(pregunta.value); pregunta.value = ''"
            />
            <button
              class="primary"
              [disabled]="chatEsperando()"
              (click)="enviarChat(pregunta.value); pregunta.value = ''"
            >
              Enviar
            </button>
          </div>
        </article>
      </section>
    }

    @if (seleccionado()) {
      <div
        class="fixed inset-0 z-10 grid place-items-center bg-stone-950/60 p-4"
        (click)="seleccionado.set(null)"
      >
        <article
          class="ficha-modal max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl p-5"
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
                  <b
                    class="sello"
                    [attr.data-veredicto]="evaluacionDetalle()!.veredicto"
                    >{{ etiqueta(evaluacionDetalle()!.veredicto) }}</b
                  >
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
                  {{ formatoPrecio(seleccionado()!.precio.precio_usd) }} EE. UU.
                }
                @if (seleccionado()!.precio.precio_confiable) {
                  <span class="text-amber-800"
                    >Precio con ofertas suficientes</span
                  >
                } @else {
                  <span class="text-amber-800">Precio con pocas ofertas</span>
                }
                @if (seleccionado()!.precio.fecha_precio) {
                  · Actualizado
                  {{ fechaCorta(seleccionado()!.precio.fecha_precio) }}
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
  protected readonly vistaCompacta = signal<boolean | null>(null);
  protected readonly juegos = signal<JuegoDetalle[]>([]);
  protected readonly resultados = signal<JuegoListado[]>([]);
  protected readonly agrupacion = signal("familia");
  protected readonly seleccionado = signal<JuegoDetalle | null>(null);
  protected readonly error = signal("");
  protected readonly cobertura = signal<CoberturaRespuesta | null>(null);
  protected readonly plan = signal<PlanCompraRespuesta | null>(null);
  protected readonly noche = signal<EstaNocheRespuesta | null>(null);
  protected readonly preguntasSugeridas = signal(
    this.elegirPreguntasSugeridas(),
  );
  protected readonly mensajesChat = signal<
    {
      role: "user" | "assistant";
      texto: string;
      bienvenida?: boolean;
      respuesta?: ChatRespuesta;
    }[]
  >([
    {
      role: "assistant",
      texto:
        "Hola, soy Wise Dice. Puedo ayudarte a descubrir huecos, evaluar compras y elegir qué jugar hoy.",
      bienvenida: true,
    },
  ]);
  protected readonly chatEsperando = signal(false);
  protected readonly chatError = signal(false);
  private chatSessionId: string | undefined;
  protected readonly evaluacionDetalle = signal<EvaluarRespuesta | null>(null);
  protected readonly ventaDetalle = signal<VentaImpactoRespuesta | null>(null);
  protected readonly tooltip = signal<{
    nombre: string;
    rango: string;
    x: number;
    y: number;
  } | null>(null);

  constructor() {
    const perfilGuardado = localStorage.getItem("wise-dice-perfil");
    if (perfilGuardado === "cafe" || perfilGuardado === "coleccionista") {
      this.perfilActivo.set(perfilGuardado);
    }
    void this.cargarPerfiles();
    void this.cargarColeccion();
  }

  protected async cambiarPerfil(perfil: string): Promise<void> {
    if (perfil === this.perfilActivo()) return;
    this.perfilActivo.set(perfil);
    localStorage.setItem("wise-dice-perfil", perfil);
    this.plan.set(null);
    this.noche.set(null);
    this.evaluacionDetalle.set(null);
    await this.cargarColeccion();
    if (this.vista() === "cobertura") await this.cargarCobertura();
  }

  protected async abrirLudoteca(perfil: string): Promise<void> {
    await this.cambiarPerfil(perfil);
    this.vista.set("ludoteca");
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
    edadMinima?: number,
  ): Promise<void> {
    if (jugadores > 0 && minutos > 0)
      this.noche.set(
        await firstValueFrom(
          this.api.estaNoche(
            { jugadores, minutos, edad_minima: edadMinima || undefined },
            this.perfilActivo(),
          ),
        ),
      );
  }

  protected limpiarNoche(
    jugadores: HTMLInputElement,
    minutos: HTMLInputElement,
    edad: HTMLInputElement,
  ): void {
    jugadores.value = "";
    minutos.value = "";
    edad.value = "";
    this.noche.set(null);
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

  protected async enviarChat(mensaje: string, gameId?: string): Promise<void> {
    if (!mensaje.trim()) return;
    this.chatError.set(false);
    this.chatEsperando.set(true);
    this.mensajesChat.update((mensajes) => [
      ...mensajes,
      { role: "user", texto: mensaje },
    ]);
    try {
      const respuesta = await firstValueFrom(
        this.api.chat(mensaje, this.perfilActivo(), this.chatSessionId, gameId),
      );
      this.chatSessionId = respuesta.session_id;
      this.mensajesChat.update((mensajes) => [
        ...mensajes,
        { role: "assistant", texto: respuesta.answer, respuesta },
      ]);
    } catch {
      this.chatError.set(true);
    } finally {
      this.chatEsperando.set(false);
    }
  }
  protected escribirNombreIngles(): void {
    const campo = document.getElementById(
      "chat-input",
    ) as HTMLInputElement | null;
    if (campo) {
      campo.value = "El nombre en inglés es: ";
      campo.focus();
    }
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
  protected tarjetaJuego(
    tarjeta: NonNullable<ChatRespuesta["tarjetas"]>[number],
  ): { nombre: string } | null {
    const juego = tarjeta.datos["juego"];
    return juego &&
      typeof juego === "object" &&
      "nombre" in juego &&
      typeof juego.nombre === "string"
      ? { nombre: juego.nombre }
      : null;
  }
  protected tarjetaVeredicto(
    tarjeta: NonNullable<ChatRespuesta["tarjetas"]>[number],
  ): string | null {
    const veredicto = tarjeta.datos["veredicto"];
    return typeof veredicto === "string" ? veredicto : null;
  }
  protected tarjetaImagen(
    tarjeta: NonNullable<ChatRespuesta["tarjetas"]>[number],
  ): string | null {
    const juego = tarjeta.datos["juego"] as Record<string, unknown> | undefined;
    return typeof juego?.["imagen_url"] === "string"
      ? juego["imagen_url"]
      : null;
  }
  protected tarjetaPrecio(
    tarjeta: NonNullable<ChatRespuesta["tarjetas"]>[number],
  ): string | null {
    const juego = tarjeta.datos["juego"] as Record<string, unknown> | undefined;
    if (juego?.["precio_usd"] == null) return null;
    const precio = Number(juego["precio_usd"]);
    const fecha =
      typeof juego["fecha_precio"] === "string"
        ? ` · ${this.fechaCorta(juego["fecha_precio"])}`
        : "";
    return `${this.formatoPrecio(precio)}${fecha}`;
  }
  protected tarjetaAnio(
    tarjeta: NonNullable<ChatRespuesta["tarjetas"]>[number],
  ): string | null {
    const juego = tarjeta.datos["juego"] as Record<string, unknown> | undefined;
    return typeof juego?.["anio"] === "number" ? String(juego["anio"]) : null;
  }
  protected tarjetaFicha(
    tarjeta: NonNullable<ChatRespuesta["tarjetas"]>[number],
  ): string | null {
    const juego = tarjeta.datos["juego"] as Record<string, unknown> | undefined;
    if (!juego) return null;
    const jugadores =
      juego["jugadores_minimos"] != null && juego["jugadores_maximos"] != null
        ? `${juego["jugadores_minimos"]}-${juego["jugadores_maximos"]} jugadores`
        : "";
    const duracion =
      juego["duracion_maxima"] != null ? `${juego["duracion_maxima"]} min` : "";
    const peso =
      typeof juego["peso"] === "number"
        ? `${juego["peso"].toFixed(1)} · ${juego["nivel_peso"] ?? "peso desconocido"}${juego["peso_estimado"] ? " estimado" : ""}`
        : "";
    const anio = typeof juego["anio"] === "number" ? String(juego["anio"]) : "";
    return (
      [anio, jugadores, duracion, peso].filter(Boolean).join(" · ") || null
    );
  }
  protected fechaCorta(valor: string | null | undefined): string {
    if (!valor) return "";
    const fecha = new Date(valor);
    return Number.isNaN(fecha.getTime())
      ? valor
      : new Intl.DateTimeFormat("es", {
          day: "numeric",
          month: "short",
          year: "numeric",
        })
          .format(fecha)
          .replace(".", "");
  }
  protected formatoPrecio(valor: number | string | null | undefined): string {
    if (valor == null) return "";
    return `USD ${Number(valor).toFixed(2)}`;
  }
  protected tarjetaEnlace(
    tarjeta: NonNullable<ChatRespuesta["tarjetas"]>[number],
  ): string | null {
    const juego = tarjeta.datos["juego"] as Record<string, unknown> | undefined;
    return typeof juego?.["bgp_url"] === "string" ? juego["bgp_url"] : null;
  }
  protected markdown(texto: string): string {
    return renderMarkdown(texto);
  }
  protected etiquetaTool(tool: string): string {
    return (
      {
        detalle_juego: "Ficha del juego",
        evaluar_compra: "Evaluación de compra",
        que_me_falta: "Huecos de la colección",
        que_compro: "Plan de compra",
        que_saco_hoy: "Modo mesa",
        ver_coleccion: "Tu colección",
      }[tool] ?? tool
    );
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
    return primeraMayuscula(valor);
  }
  protected etiquetaPerfil(): string {
    return this.perfilActivo() === "cafe" ? "Café demo" : "colección personal";
  }
  protected tituloLudoteca(): string {
    return this.perfilActivo() === "cafe"
      ? "Disponibilidad para tu mesa"
      : "Tu librero de experiencias";
  }
  protected explicacionLudoteca(): string {
    return this.perfilActivo() === "cafe"
      ? "Dinos cuántos son y cuánto tiempo tienen: iluminamos los juegos ideales para su mesa."
      : "Recorre tu colección, agrúpala por experiencia y descubre qué historias ya viven en tu librero.";
  }
  protected vistaCompactaActiva(): boolean {
    return this.vistaCompacta() ?? this.juegos().length > 24;
  }
  protected alternarVistaEstantes(): void {
    this.vistaCompacta.set(!this.vistaCompactaActiva());
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
            ? juego.nivel_jugadores
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
    const maximo =
      window.innerWidth < 640 ? 3 : window.innerWidth < 1024 ? 5 : 7;
    return Array.from(
      { length: Math.ceil(juegos.length / maximo) },
      (_, indice) => juegos.slice(indice * maximo, (indice + 1) * maximo),
    );
  }

  private elegirPreguntasSugeridas(): string[] {
    const banco = [
      "¿Qué tal entraría SETI en la colección?",
      "Tengo ganas de comprar Wyrmspan, ¿vale la pena?",
      "¿Qué le falta a mi colección?",
      "Quiero un plan de 3 juegos para cubrir huecos",
      "Somos 6 y tenemos 45 minutos, ¿qué saco?",
      "¿Me conviene SETI?",
    ];
    return [...banco].sort(() => Math.random() - 0.5).slice(0, 3);
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
            backgroundColor: "rgba(201,160,63,.28)",
            borderColor: "#86641f",
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
                backgroundColor: "#1f6a52",
              },
              {
                label: "Débiles",
                data: Object.values(ejes).map(
                  (eje) => Object.keys(eje.debiles).length,
                ),
                backgroundColor: "#a47e2c",
              },
              {
                label: "Faltantes",
                data: Object.values(ejes).map((eje) => eje.faltantes.length),
                backgroundColor: "#7d1f2e",
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
              borderColor: "#86641f",
              backgroundColor: "rgba(201,160,63,.22)",
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
    return conteo === 0 ? "#7d1f2e" : conteo === 1 ? "#a47e2c" : "#1f6a52";
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
