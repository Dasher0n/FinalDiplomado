import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { ComponentFixture, TestBed } from "@angular/core/testing";

import { App } from "./app";

describe("App", () => {
  let fixture: ComponentFixture<App>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(App);
    fixture.detectChanges();
  });

  it("muestra la marca de la aplicacion", () => {
    expect(fixture.nativeElement.textContent).toContain("Wise Dice");
  });

  it("empieza una conversación limpia y pide sugerencias nuevas", async () => {
    const raiz = fixture.nativeElement as HTMLElement;
    const app = fixture.componentInstance as unknown as {
      mensajesChat: { set(valor: unknown[]): void; (): unknown[] };
      chatSessionId?: string;
      vista: { set(valor: string): void };
    };
    app.vista.set("chat");
    fixture.detectChanges();
    app.mensajesChat.set([
      { role: "assistant", texto: "Hola", bienvenida: true },
      { role: "user", texto: "¿Vale la pena SETI?" },
    ]);
    app.chatSessionId = "sesion-vieja";
    fixture.detectChanges();
    expect(raiz.textContent).toContain("¿Vale la pena SETI?");

    const boton = Array.from(raiz.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Nueva conversación"),
    ) as HTMLButtonElement;
    boton.click();
    const solicitud = http
      .match((r) => r.url === "/api/v1/chat/suggestions")
      .pop();
    solicitud?.flush({
      preguntas: ["Pregunta uno", "Pregunta dos", "Pregunta tres"],
    });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(raiz.textContent).not.toContain("¿Vale la pena SETI?");
    expect(raiz.textContent).toContain("Pregunta dos");
    expect(app.chatSessionId).toBeUndefined();
    expect(app.mensajesChat()).toHaveLength(1);
  });
});
