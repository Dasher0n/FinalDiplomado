import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("escapa HTML y permite el formato restringido", () => {
    const html = renderMarkdown("# Título\n- **uno**\n- [enlace](https://ejemplo.test)\n<script>");

    expect(html).toContain("<h1>Título</h1>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<strong>uno</strong>");
    expect(html).toContain('target="_blank" rel="noopener"');
    expect(html).toContain("&lt;script&gt;");
  });
});
