/** Mayúscula solo en la primera letra real del texto, compatible con Unicode. */
export function primeraMayuscula(valor: string): string {
  return valor.replace(
    /^[^\p{L}]*\p{L}/u,
    (inicio) => inicio.slice(0, -1) + inicio.slice(-1).toLocaleUpperCase("es"),
  );
}
