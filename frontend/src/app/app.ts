import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="min-h-screen bg-amber-50 px-6 py-12 text-stone-800">
      <section class="mx-auto max-w-3xl rounded-3xl border border-amber-200 bg-white p-10 shadow-sm">
        <p class="text-sm font-semibold uppercase tracking-[0.2em] text-amber-700">Sommelier</p>
        <h1 class="mt-3 font-serif text-4xl font-semibold">Tu ludoteca, con intención</h1>
        <p class="mt-4 text-lg text-stone-600">
          El andamiaje está listo. La vitrina de tu colección llegará en la siguiente fase.
        </p>
      </section>
    </main>
  `,
})
export class App {}
