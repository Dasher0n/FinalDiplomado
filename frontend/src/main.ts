import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { bootstrapApplication } from "@angular/platform-browser";
import { provideRouter } from "@angular/router";

import { routes } from "./app/app.routes";
import { authInterceptor } from "./app/core/auth.interceptor";
import { Raiz } from "./app/raiz";

bootstrapApplication(Raiz, {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
  ],
}).catch((error: unknown) => console.error(error));
