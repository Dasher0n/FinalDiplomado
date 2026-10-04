import { Component } from "@angular/core";
import { RouterOutlet } from "@angular/router";

/** Componente raíz: solo aloja la ruta activa (login o el estudio). */
@Component({
  selector: "app-root",
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class Raiz {}
