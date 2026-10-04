import { construirAporte } from "./aporte";

describe("construirAporte", () => {
  it("pone primero los ejes con algo nuevo y agrupa los demás en una línea", () => {
    const aporte = construirAporte([
      { eje: "Jugadores", texto: "3 a 4", estado: "previo" },
      { eje: "Peso", texto: "pesado", estado: "hueco" },
      { eje: "Mecánicas", texto: "Control de área", estado: "refuerzo" },
      { eje: "Interacción", texto: "directa", estado: "previo" },
      { eje: "Duración", texto: "más de 120 min", estado: "hueco" },
    ]);

    expect(aporte.conCambio.map((eje) => eje.eje)).toEqual([
      "Duración",
      "Peso",
      "Mecánicas",
    ]);
    expect(aporte.sinCambio).toEqual(["Jugadores", "Interacción"]);
    expect(aporte.conCambio[0].niveles[0].clase).toBe("nivel-hueco");
    expect(aporte.conCambio[2].niveles[0].clase).toBe("nivel-refuerzo");
  });

  it("conserva los niveles que ya tenía dentro de un eje con cambios", () => {
    const aporte = construirAporte([
      { eje: "Jugadores", texto: "2", estado: "previo" },
      { eje: "Jugadores", texto: "5", estado: "hueco" },
    ]);

    expect(aporte.conCambio).toHaveLength(1);
    expect(aporte.conCambio[0].niveles.map((nivel) => nivel.clase)).toEqual([
      "nivel-previo",
      "nivel-hueco",
    ]);
    expect(aporte.sinCambio).toEqual([]);
  });
});
