import { TestBed } from "@angular/core/testing";

import { CLAVE_SESION, SesionService } from "./sesion.service";

describe("SesionService", () => {
  beforeEach(() => localStorage.removeItem(CLAVE_SESION));

  it("guarda la sesión y la recupera al crear el servicio de nuevo", () => {
    TestBed.inject(SesionService).guardar({
      token: "t",
      nombre: "Colección personal",
      perfil: "coleccionista",
    });
    TestBed.resetTestingModule();

    const nuevo = TestBed.inject(SesionService);

    expect(nuevo.perfil()).toBe("coleccionista");
    expect(nuevo.token()).toBe("t");
  });

  it("cerrar sesión limpia el estado y el almacenamiento, incluido el perfil heredado", () => {
    localStorage.setItem("wise-dice-perfil", "cafe");
    const servicio = TestBed.inject(SesionService);
    servicio.guardar({ token: "t", nombre: "Café demo", perfil: "cafe" });

    servicio.cerrar();

    expect(servicio.activa()).toBe(false);
    expect(servicio.token()).toBeNull();
    expect(servicio.perfil()).toBe("");
    expect(localStorage.getItem(CLAVE_SESION)).toBeNull();
    expect(localStorage.getItem("wise-dice-perfil")).toBeNull();
  });
});
