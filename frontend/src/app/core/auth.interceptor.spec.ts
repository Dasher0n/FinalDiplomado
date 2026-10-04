import {
  HttpClient,
  provideHttpClient,
  withInterceptors,
} from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { Router, provideRouter } from "@angular/router";

import { authInterceptor } from "./auth.interceptor";
import { CLAVE_SESION, SesionService } from "./sesion.service";

describe("authInterceptor", () => {
  let http: HttpClient;
  let controlador: HttpTestingController;
  let sesion: SesionService;
  let navegar: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.removeItem(CLAVE_SESION);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    controlador = TestBed.inject(HttpTestingController);
    sesion = TestBed.inject(SesionService);
    navegar = vi
      .spyOn(TestBed.inject(Router), "navigateByUrl")
      .mockResolvedValue(true);
    sesion.guardar({ token: "abc", nombre: "Café demo", perfil: "cafe" });
  });

  it("agrega el encabezado Authorization a las llamadas al API", () => {
    http.get("/api/v1/collection").subscribe();

    const solicitud = controlador.expectOne("/api/v1/collection");
    expect(solicitud.request.headers.get("Authorization")).toBe("Bearer abc");
    solicitud.flush({});
  });

  it("no manda el token a otros orígenes", () => {
    http.get("https://otro.example/datos").subscribe();

    const solicitud = controlador.expectOne("https://otro.example/datos");
    expect(solicitud.request.headers.has("Authorization")).toBe(false);
    solicitud.flush({});
  });

  it("ante un 401 borra la sesión y redirige a /login", () => {
    http.get("/api/v1/collection").subscribe({ error: () => undefined });

    controlador
      .expectOne("/api/v1/collection")
      .flush({}, { status: 401, statusText: "Unauthorized" });

    expect(sesion.activa()).toBe(false);
    expect(localStorage.getItem(CLAVE_SESION)).toBeNull();
    expect(navegar).toHaveBeenCalledWith("/login");
  });

  it("un 401 del propio login no cierra nada ni redirige", () => {
    http.post("/api/v1/auth/login", {}).subscribe({ error: () => undefined });

    controlador
      .expectOne("/api/v1/auth/login")
      .flush({}, { status: 401, statusText: "Unauthorized" });

    expect(sesion.activa()).toBe(true);
    expect(navegar).not.toHaveBeenCalled();
  });
});
