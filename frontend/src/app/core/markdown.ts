// Renderizador mínimo: escapa la entrada antes de aplicar el formato permitido.
function inline(text: string): string {
  return text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
}

export function renderMarkdown(source: string): string {
  const escaped = source.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped.split("\n").filter((line) => line.trim()).map((line) => `<p>${inline(line)}</p>`).join("\n");
}
