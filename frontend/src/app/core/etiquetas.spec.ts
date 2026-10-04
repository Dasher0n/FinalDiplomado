import { primeraMayuscula } from "./etiquetas";

describe("primeraMayuscula", () => {
  it("pone mayúscula solo en la primera letra y respeta los acentos", () => {
    expect(primeraMayuscula("cartas clásicas y bazas")).toBe(
      "Cartas clásicas y bazas",
    );
    expect(primeraMayuscula("colección y contratos")).toBe(
      "Colección y contratos",
    );
    expect(primeraMayuscula("control de área")).toBe("Control de área");
  });

  it("usa la primera letra real cuando hay símbolos al inicio y no altera el resto", () => {
    expect(primeraMayuscula("¿área abierta?")).toBe("¿Área abierta?");
    expect(primeraMayuscula("Ya Escrita")).toBe("Ya Escrita");
    expect(primeraMayuscula("")).toBe("");
  });
});
