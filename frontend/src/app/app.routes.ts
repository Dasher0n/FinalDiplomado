import { Routes } from "@angular/router";

import { App } from "./app";
import { invitadoGuard, sesionGuard } from "./core/sesion.guard";
import { LoginComponent } from "./login/login";

export const routes: Routes = [
  { path: "login", component: LoginComponent, canActivate: [invitadoGuard] },
  { path: "", component: App, canActivate: [sesionGuard] },
  { path: "**", redirectTo: "" },
];
