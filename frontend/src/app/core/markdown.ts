function escapar(texto: string): string {
  return texto.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;");
}

function enLinea(texto: string): string {
  return texto
    .replace(/\[([^\]]+)]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*(.+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
}

export function renderMarkdown(source: string): string {
  const salida: string[] = [];
  let lista: "ul" | "ol" | null = null;
  const cerrarLista = () => {
    if (lista) salida.push(`</${lista}>`);
    lista = null;
  };

  for (const linea of source.split("\n")) {
    const texto = escapar(linea.trim());
    const encabezado = texto.match(/^(#{1,3})\s+(.+)$/);
    const elemento = texto.match(/^[-*]\s+(.+)$/);
    const numero = texto.match(/^\d+\.\s+(.+)$/);
    if (encabezado) {
      cerrarLista();
      salida.push(`<h${encabezado[1].length}>${enLinea(encabezado[2])}</h${encabezado[1].length}>`);
    } else if (elemento || numero) {
      const tipo = numero ? "ol" : "ul";
      if (lista !== tipo) {
        cerrarLista();
        salida.push(`<${tipo}>`);
        lista = tipo;
      }
      salida.push(`<li>${enLinea((elemento ?? numero)![1])}</li>`);
    } else if (texto) {
      cerrarLista();
      salida.push(`<p>${enLinea(texto)}</p>`);
    } else {
      cerrarLista();
    }
  }
  cerrarLista();
  return salida.join("\n");
}
