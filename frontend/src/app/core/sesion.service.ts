import { Injectable, computed, signal } from "@angular/core";

export interface Sesion {
  token: string;
  nombre: string;
  perfil: string;
}

export const CLAVE_SESION = "wise-dice-sesion";

/** Sesión de la persona: el token y su perfil viven aquí y en localStorage. */
@Injectable({ providedIn: "root" })
export class SesionService {
  private readonly actual = signal<Sesion | null>(this.leer());
  readonly sesion = this.actual.asReadonly();
  readonly activa = computed(() => this.actual() !== null);
  readonly perfil = computed(() => this.actual()?.perfil ?? "");
  readonly nombre = computed(() => this.actual()?.nombre ?? "");

  token(): string | null {
    return this.actual()?.token ?? null;
  }

  guardar(sesion: Sesion): void {
    try {
      localStorage.setItem(CLAVE_SESION, JSON.stringify(sesion));
    } catch {
      // Sin almacenamiento la sesión dura lo que dure la pestaña.
    }
    this.actual.set(sesion);
  }

  /** Borra todo rastro de la sesión: nada de la persona anterior debe sobrevivir. */
  cerrar(): void {
    try {
      localStorage.removeItem(CLAVE_SESION);
      localStorage.removeItem("wise-dice-perfil");
    } catch {
      // Nada que limpiar si el almacenamiento no está disponible.
    }
    this.actual.set(null);
  }

  private leer(): Sesion | null {
    try {
      const guardada = JSON.parse(localStorage.getItem(CLAVE_SESION) ?? "null");
      return guardada?.token && guardada?.perfil ? (guardada as Sesion) : null;
    } catch {
      return null;
    }
  }
}
