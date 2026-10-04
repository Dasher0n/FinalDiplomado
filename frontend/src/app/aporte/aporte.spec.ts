import { construirAporte, construirVenta } from "./aporte";

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

describe("construirVenta", () => {
  const ejes: [string, string[]][] = [
    ["Jugadores", ["3 a 4", "5"]],
    ["Peso", ["ligero"]],
    ["Temática", ["Party y comunicación"]],
  ];
  const metas = {
    Jugadores: { "3 a 4": 2, "5": 2 },
    Peso: { ligero: 2 },
    Temática: { "Party y comunicación": 2 },
  };

  it("sin pérdidas: todo sigue cubierto y lo dice con el conteo de juegos", () => {
    const venta = construirVenta(
      ejes,
      [
        { eje: "Jugadores", nivel: "3 a 4", antes: 9, despues: 8 },
        { eje: "Jugadores", nivel: "5", antes: 5, despues: 4 },
        { eje: "Peso", nivel: "ligero", antes: 12, despues: 11 },
        {
          eje: "Temática",
          nivel: "Party y comunicación",
          antes: 26,
          despues: 25,
        },
      ],
      metas,
    );

    expect(venta.perdidas).toBe(0);
    expect(venta.debilitados).toBe(0);
    expect(venta.sello).toBe("venta-ok");
    expect(venta.conclusion).toBe(
      "Puedes venderlo sin dejar huecos: lo que aporta lo cubren otros juegos.",
    );
    expect(venta.aporte.conCambio).toEqual([]);
    expect(venta.aporte.sinCambio).toEqual(["Jugadores", "Peso", "Temática"]);
  });

  it("con un hueco y un nivel que queda débil: los ejes con pérdidas van primero", () => {
    const venta = construirVenta(
      ejes,
      [
        { eje: "Jugadores", nivel: "3 a 4", antes: 9, despues: 8 },
        { eje: "Jugadores", nivel: "5", antes: 2, despues: 1 },
        { eje: "Peso", nivel: "ligero", antes: 1, despues: 0 },
        {
          eje: "Temática",
          nivel: "Party y comunicación",
          antes: 26,
          despues: 25,
        },
      ],
      metas,
    );

    expect(venta.perdidas).toBe(1);
    expect(venta.debilitados).toBe(1);
    expect(venta.sello).toBe("venta-perdida");
    expect(venta.conclusion).toBe(
      "Venderlo dejaría 1 hueco y debilitaría 1 nivel.",
    );
    expect(venta.aporte.conCambio.map((eje) => eje.eje)).toEqual([
      "Peso",
      "Jugadores",
    ]);
    expect(venta.aporte.conCambio[0].niveles[0].clase).toBe("nivel-perdida");
    expect(venta.aporte.conCambio[1].niveles.map((n) => n.clase)).toEqual([
      "nivel-previo",
      "nivel-debil",
    ]);
    expect(venta.aporte.conCambio[1].niveles[0].texto).toBe("3 a 4 · 8 juegos");
    expect(venta.aporte.sinCambio).toEqual(["Temática"]);
  });

  it("ignora los niveles sin meta en el perfil", () => {
    const venta = construirVenta(
      [["Peso", ["pesado"]]],
      [{ eje: "Peso", nivel: "pesado", antes: 1, despues: 0 }],
      { Peso: {} },
    );

    expect(venta.perdidas).toBe(0);
    expect(venta.aporte.conCambio).toEqual([]);
  });
});
