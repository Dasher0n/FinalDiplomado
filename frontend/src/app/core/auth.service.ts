import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { tap } from "rxjs";

import { environment } from "../../environments/environment";
import { Sesion, SesionService } from "./sesion.service";

@Injectable({ providedIn: "root" })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly sesion = inject(SesionService);

  login(usuario: string, clave: string) {
    return this.http
      .post<Sesion>(`${environment.apiBase}/auth/login`, { usuario, clave })
      .pipe(tap((respuesta) => this.sesion.guardar(respuesta)));
  }
}
