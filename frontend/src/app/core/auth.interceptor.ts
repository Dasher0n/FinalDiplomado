import { HttpErrorResponse, HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { Router } from "@angular/router";
import { catchError, throwError } from "rxjs";

import { environment } from "../../environments/environment";
import { SesionService } from "./sesion.service";

/**
 * Agrega Authorization a las llamadas al API y, ante un 401, cierra la sesión y va a /login.
 * También manda ngrok-skip-browser-warning para que ngrok no responda con su página de aviso.
 */
export const authInterceptor: HttpInterceptorFn = (peticion, siguiente) => {
  const sesion = inject(SesionService);
  const router = inject(Router);
  const esApi = peticion.url.startsWith(environment.apiBase);
  const token = sesion.token();
  const encabezados: Record<string, string> = {};
  if (esApi) encabezados["ngrok-skip-browser-warning"] = "1";
  if (esApi && token) encabezados["Authorization"] = `Bearer ${token}`;
  const conToken = esApi
    ? peticion.clone({ setHeaders: encabezados })
    : peticion;
  return siguiente(conToken).pipe(
    catchError((error: unknown) => {
      const esLogin = peticion.url.endsWith("/auth/login");
      if (
        esApi &&
        !esLogin &&
        error instanceof HttpErrorResponse &&
        error.status === 401
      ) {
        sesion.cerrar();
        void router.navigateByUrl("/login");
      }
      return throwError(() => error);
    }),
  );
};
