import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { CatalogoService, JuegoDetalle, JuegoListado } from './core/api/catalogo.service';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="min-h-screen text-stone-900">
      <header class="wise-header px-6 py-4 text-[#f8f1e5]">
        <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <img class="h-12 w-12" src="/wise-dice.svg" alt="Dado sabio de Wise Dice">
            <div><h1 class="font-serif text-3xl">Wise Dice</h1><p class="text-sm text-amber-200">Tu asesor de ludoteca</p></div>
          </div>
          <nav class="flex flex-wrap items-center justify-end gap-x-4 gap-y-2 text-sm">
            <a class="border-b-2 border-amber-300 pb-1" href="#ludoteca">Ludoteca</a>
            <span class="text-stone-400">Cobertura, próximamente</span>
            <span class="text-stone-400">Chat, próximamente</span>
            <button class="add-game" (click)="panelBusqueda.set(!panelBusqueda())">Agregar juego</button>
          </nav>
        </div>
      </header>

      <section id="ludoteca" class="mx-auto max-w-7xl px-6 py-9">
        <div class="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <p class="text-sm font-semibold uppercase tracking-[0.2em] text-amber-800">12 juegos, una colección</p>
            <h2 class="mt-1 font-serif text-4xl">Tu librero de experiencias</h2>
          </div>
          <label class="text-sm font-semibold">Agrupar estantes por
            <select #selector class="mt-2 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2" (change)="cambiarAgrupacion(selector.value)">
              <option value="familia">Familia de mecánica</option>
              <option value="jugadores">Jugadores</option>
              <option value="duracion">Duración</option>
              <option value="peso">Peso</option>
              <option value="interaccion">Interacción</option>
            </select>
          </label>
        </div>

        @if (panelBusqueda()) {
        <section class="mb-10 rounded-2xl border border-amber-200 bg-amber-100/60 p-5">
          <label class="block text-sm font-semibold" for="buscar">Busca en el catálogo para agregar juegos</label>
          <input #query id="buscar" class="mt-2 w-full rounded-lg border border-amber-300 bg-white px-4 py-3" placeholder="Ejemplo: Ark Nova" (input)="buscar(query.value)">
          @if (resultados().length) {
            <div class="mt-3 grid gap-2 md:grid-cols-2">
              @for (juego of resultados(); track juego.id) {
                <button class="flex items-center gap-3 rounded-lg bg-white p-2 text-left hover:bg-amber-50" (click)="verDetalle(juego.id)">
                  @if (juego.miniatura_url) { <img class="h-12 w-10 object-cover" [src]="juego.miniatura_url" [alt]="juego.nombre"> }
                  <span><b>{{ juego.nombre }}</b><br><small>{{ juego.anio ?? 'Año no disponible' }}</small></span>
                </button>
              }
            </div>
          }
          @if (consultaActiva() && !resultados().length) { <p class="mt-3 text-sm text-stone-600">Sin coincidencias en el catálogo.</p> }
        </section>
        }

        @if (cargando()) { <p class="py-12 text-center text-stone-600">Cargando tu colección...</p> }
        @if (error()) { <p class="rounded-xl bg-red-100 p-4 text-red-900">{{ error() }}</p> }

        <div class="bookcase">
        @for (grupo of grupos(); track grupo.nombre) {
          <section class="case-shelf">
            <h3 class="shelf-plaque">{{ grupo.etiqueta }} · {{ grupo.juegos.length }}</h3>
            <div class="shelf-rail"><div class="shelf-games">
              @for (juego of grupo.juegos; track juego.id) {
                <button class="game-card" (click)="verDetalle(juego.id)">
                  <span class="game-cover">
                    @if (juego.imagen_url) { <img [src]="juego.imagen_url" [alt]="juego.nombre"> }
                    @else { <span class="flex h-full items-end bg-stone-700 p-3 text-white">{{ juego.nombre }}</span> }
                  </span>
                  <span class="game-card-info"><b>{{ juego.nombre }}</b><span>{{ juego.anio ?? 'Año no disponible' }}</span><span>{{ rangoJugadores(juego) }} jugadores</span><span>{{ juego.duracion_maxima ?? 'n/d' }} min · peso {{ juego.peso ?? 'n/d' }}</span><span>{{ juego.precio.precio_usd ? 'USD ' + juego.precio.precio_usd : 'Precio no disponible' }}</span></span>
                </button>
              }
            </div></div>
          </section>
        }
        </div>
      </section>

      @if (seleccionado()) {
        <div class="fixed inset-0 z-10 grid place-items-center bg-stone-950/60 p-5" (click)="cerrarDetalle()">
          <article class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-[#fffaf2] p-6 shadow-2xl" (click)="$event.stopPropagation()">
            <button class="float-right text-2xl" (click)="cerrarDetalle()" aria-label="Cerrar">×</button>
            <div class="grid gap-6 sm:grid-cols-[180px_1fr]">
              @if (seleccionado()!.imagen_url) { <img class="w-full rounded-lg shadow-md" [src]="seleccionado()!.imagen_url" [alt]="seleccionado()!.nombre"> }
              <div>
                <p class="text-sm font-bold uppercase tracking-wider text-amber-800">{{ seleccionado()!.anio ?? 'Año no disponible' }}</p>
                <h2 class="font-serif text-3xl">{{ seleccionado()!.nombre }}</h2>
                <dl class="mt-5 grid grid-cols-2 gap-3 text-sm"><dt>Jugadores</dt><dd>{{ rangoJugadores(seleccionado()!) }}</dd><dt>Duración</dt><dd>{{ seleccionado()!.duracion_maxima ?? 'n/d' }} min</dd><dt>Peso</dt><dd>{{ seleccionado()!.peso ?? 'n/d' }}</dd><dt>Promedio</dt><dd>{{ seleccionado()!.promedio ?? 'n/d' }}</dd></dl>
                @if (seleccionado()!.precio.precio_usd) {
                  <p class="mt-5 text-lg font-semibold">USD {{ seleccionado()!.precio.precio_usd }} <span class="text-sm font-normal">EE. UU.</span></p>
                  @if (seleccionado()!.precio.url_bgp) { <a class="text-sm font-semibold text-amber-800 underline" [href]="seleccionado()!.precio.url_bgp" target="_blank" rel="noopener">Ver en BoardGamePrices</a> }
                }
              </div>
            </div>
          </article>
        </div>
      }
    </main>
  `,
})
export class App {
  private readonly catalogo = inject(CatalogoService);

  protected readonly cargando = signal(true);
  protected readonly error = signal('');
  protected readonly juegos = signal<JuegoDetalle[]>([]);
  protected readonly resultados = signal<JuegoListado[]>([]);
  protected readonly consultaActiva = signal(false);
  protected readonly panelBusqueda = signal(false);
  protected readonly agrupacion = signal('familia');
  protected readonly seleccionado = signal<JuegoDetalle | null>(null);
  protected readonly grupos = computed(() => this.agrupar(this.juegos(), this.agrupacion()));

  constructor() {
    void this.cargarColeccion();
  }

  protected cambiarAgrupacion(valor: string): void { this.agrupacion.set(valor); }

  protected async buscar(query: string): Promise<void> {
    const texto = query.trim();
    this.consultaActiva.set(texto.length > 1);
    this.resultados.set(texto.length > 1 ? (await firstValueFrom(this.catalogo.buscar(texto))).juegos : []);
  }

  protected async verDetalle(gameId: string): Promise<void> {
    const existente = this.juegos().find((juego) => juego.id === gameId);
    this.seleccionado.set(existente ?? await firstValueFrom(this.catalogo.detalle(gameId)));
  }

  protected cerrarDetalle(): void { this.seleccionado.set(null); }
  protected rangoJugadores(juego: JuegoDetalle): string { return `${juego.jugadores_minimos ?? 'n/d'} a ${juego.jugadores_maximos ?? 'n/d'}`; }

  private async cargarColeccion(): Promise<void> {
    try {
      const coleccion = await firstValueFrom(this.catalogo.coleccion());
      this.juegos.set(await Promise.all(coleccion.juegos.map((juego) => firstValueFrom(this.catalogo.detalle(juego.id)))));
    } catch {
      this.error.set('No fue posible cargar la colección demo.');
    } finally {
      this.cargando.set(false);
    }
  }

  private agrupar(juegos: JuegoDetalle[], criterio: string): { nombre: string; etiqueta: string; juegos: JuegoDetalle[] }[] {
    const estantes = new Map<string, JuegoDetalle[]>();
    for (const juego of juegos) {
      const nombre = criterio === 'jugadores' ? this.rangoJugadores(juego)
        : criterio === 'duracion' ? juego.nivel_duracion ?? 'Duración sin clasificar'
        : criterio === 'peso' ? juego.nivel_peso ?? 'Peso sin clasificar'
        : criterio === 'interaccion' ? juego.nivel_interaccion ?? 'Interacción sin clasificar'
        : this.texto(juego.familias_mecanicas?.[0]) ?? 'Sin familia de mecánica';
      estantes.set(nombre, [...(estantes.get(nombre) ?? []), juego]);
    }
    return [...estantes].map(([nombre, juegosDelEstante]) => ({
      nombre,
      etiqueta: this.etiquetaEstante(nombre, criterio),
      juegos: juegosDelEstante,
    }));
  }

  private etiquetaEstante(valor: string, criterio: string): string {
    if (criterio === 'interaccion') {
      return { directa: 'Interacción directa', indirecta: 'Interacción indirecta', cooperativo: 'Cooperativo', ninguna: 'Sin interacción' }[valor] ?? 'Interacción sin clasificar';
    }
    if (criterio === 'jugadores') { return `${valor} jugadores`; }
    if (criterio === 'duracion') { return `Duración: ${valor} minutos`; }
    if (criterio === 'peso') { return `Peso: ${valor}`; }
    return `Mecánica: ${valor}`;
  }

  private texto(valor: unknown): string | null { return typeof valor === 'string' ? valor : null; }
}
