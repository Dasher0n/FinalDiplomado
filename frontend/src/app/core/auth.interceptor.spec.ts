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

  it("agrega ngrok-skip-browser-warning a todas las llamadas al API, también sin sesión", () => {
    http.get("/api/v1/games").subscribe();
    controlador.expectOne("/api/v1/games").flush({});
    sesion.cerrar();
    http.post("/api/v1/auth/login", {}).subscribe();

    const login = controlador.expectOne("/api/v1/auth/login");

    expect(login.request.headers.get("ngrok-skip-browser-warning")).toBe("1");
    expect(login.request.headers.has("Authorization")).toBe(false);
    login.flush({});
  });

  it("también manda el encabezado de ngrok con el token", () => {
    http.get("/api/v1/games").subscribe();

    const solicitud = controlador.expectOne("/api/v1/games");

    expect(solicitud.request.headers.get("ngrok-skip-browser-warning")).toBe(
      "1",
    );
    expect(solicitud.request.headers.get("Authorization")).toBe("Bearer abc");
    solicitud.flush({});
  });

  it("no manda el token ni el encabezado de ngrok a otros orígenes", () => {
    http.get("https://otro.example/datos").subscribe();

    const solicitud = controlador.expectOne("https://otro.example/datos");
    expect(solicitud.request.headers.has("Authorization")).toBe(false);
    expect(solicitud.request.headers.has("ngrok-skip-browser-warning")).toBe(
      false,
    );
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
