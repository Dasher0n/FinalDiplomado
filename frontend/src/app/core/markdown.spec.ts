import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("escapa HTML y permite el formato restringido", () => {
    const html = renderMarkdown(
      "# Título\n- **uno**\n- [enlace](https://ejemplo.test)\n<script>",
    );

    expect(html).toContain("<h1>Título</h1>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<strong>uno</strong>");
    expect(html).toContain('target="_blank" rel="noopener"');
    expect(html).toContain("&lt;script&gt;");
  });

  it("permite cursiva y emojis dentro de negritas", () => {
    expect(renderMarkdown("**🎲 *Wingspan***")).toContain(
      "<strong>🎲 <em>Wingspan</em></strong>",
    );
  });

  it("permite negrita al inicio de una línea", () => {
    expect(renderMarkdown("**Veredicto** claro")).toContain(
      "<strong>Veredicto</strong> claro",
    );
  });
});
