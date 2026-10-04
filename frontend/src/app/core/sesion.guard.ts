import { inject } from "@angular/core";
import { CanActivateFn, Router } from "@angular/router";

import { SesionService } from "./sesion.service";

/** Protege Ludoteca, Cobertura y Chat: sin sesión se va a /login. */
export const sesionGuard: CanActivateFn = () => {
  const sesion = inject(SesionService);
  return sesion.activa() ? true : inject(Router).createUrlTree(["/login"]);
};

/** Quien ya inició sesión no necesita ver /login. */
export const invitadoGuard: CanActivateFn = () => {
  const sesion = inject(SesionService);
  return sesion.activa() ? inject(Router).createUrlTree(["/"]) : true;
};
