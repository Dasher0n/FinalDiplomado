import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from "@angular/core";
import { Router } from "@angular/router";
import { firstValueFrom } from "rxjs";

import { AuthService } from "../core/auth.service";
import { LogoComponent } from "../logo/logo";

@Component({
  selector: "app-login",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LogoComponent],
  template: `<main class="login-pantalla">
    <section class="login-hoja panel rollo">
      <app-logo class="login-logo" />
      <h1 class="login-titulo">Wise Dice</h1>
      <p class="login-subtitulo">Tu asesor de ludoteca</p>
      <form
        class="login-formulario"
        (submit)="entrar($event, usuario.value, clave.value)"
      >
        <label
          >Usuario<input
            #usuario
            class="input"
            name="usuario"
            autocomplete="username"
            autocapitalize="none"
            spellcheck="false"
            required
        /></label>
        <label
          >Contraseña<input
            #clave
            class="input"
            name="clave"
            type="password"
            autocomplete="current-password"
            required
        /></label>
        <button class="primary" type="submit" [disabled]="enviando()">
          Entrar
        </button>
        @if (error()) {
          <p class="login-error" role="alert">{{ error() }}</p>
        }
      </form>
    </section>
  </main>`,
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  protected readonly enviando = signal(false);
  protected readonly error = signal("");

  protected async entrar(
    evento: Event,
    usuario: string,
    clave: string,
  ): Promise<void> {
    evento.preventDefault();
    if (!usuario.trim() || !clave) return;
    this.enviando.set(true);
    this.error.set("");
    try {
      await firstValueFrom(this.auth.login(usuario.trim(), clave));
      await this.router.navigateByUrl("/");
    } catch {
      this.error.set("Usuario o contraseña incorrectos");
    } finally {
      this.enviando.set(false);
    }
  }
}
