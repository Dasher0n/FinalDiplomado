import { TestBed } from "@angular/core/testing";
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  UrlTree,
  provideRouter,
} from "@angular/router";

import { CLAVE_SESION, SesionService } from "./sesion.service";
import { invitadoGuard, sesionGuard } from "./sesion.guard";

function ejecutar(guard: typeof sesionGuard): boolean | UrlTree {
  return TestBed.runInInjectionContext(() =>
    guard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  ) as boolean | UrlTree;
}

describe("guards de sesión", () => {
  beforeEach(() => {
    localStorage.removeItem(CLAVE_SESION);
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
  });

  it("sin sesión, el guard del estudio redirige a /login", () => {
    const resultado = ejecutar(sesionGuard);

    expect(resultado).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(resultado as UrlTree)).toBe(
      "/login",
    );
  });

  it("con sesión, deja pasar al estudio y saca a la persona de /login", () => {
    TestBed.inject(SesionService).guardar({
      token: "t",
      nombre: "Café demo",
      perfil: "cafe",
    });

    expect(ejecutar(sesionGuard)).toBe(true);
    const desvio = ejecutar(invitadoGuard) as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(desvio)).toBe("/");
  });
});
