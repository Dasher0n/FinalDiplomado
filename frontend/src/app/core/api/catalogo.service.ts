import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";

import type { components } from "./schema";

export type ColeccionRespuesta = components["schemas"]["ColeccionRespuesta"];
export type JuegoListado = components["schemas"]["JuegoListado"];
export type JuegoDetalle = components["schemas"]["JuegoDetalle"];
export type CoberturaRespuesta = components["schemas"]["CoberturaRespuesta"];
export type EvaluarRespuesta = components["schemas"]["EvaluarRespuesta"];
export type PlanCompraRespuesta = components["schemas"]["PlanCompraRespuesta"];
export type EstaNocheRespuesta = components["schemas"]["EstaNocheRespuesta"];
export type VentaImpactoRespuesta = components["schemas"]["VentaImpactoRespuesta"];

@Injectable({ providedIn: "root" })
export class CatalogoService {
  constructor(private readonly http: HttpClient) {}

  coleccion() {
    return this.http.get<ColeccionRespuesta>("/api/v1/collection");
  }

  buscar(query: string) {
    return this.http.get<{ juegos: JuegoListado[] }>("/api/v1/games", {
      params: { q: query, limit: 8 },
    });
  }

  detalle(gameId: string) {
    return this.http.get<JuegoDetalle>(`/api/v1/games/${gameId}`);
  }

  agregar(gameId: string) {
    return this.http.post("/api/v1/collection", { game_id: gameId });
  }

  quitar(gameId: string) {
    return this.http.delete(`/api/v1/collection/${gameId}`);
  }

  cobertura() {
    return this.http.get<CoberturaRespuesta>("/api/v1/engine/coverage");
  }

  evaluar(gameId: string) {
    return this.http.post<EvaluarRespuesta>("/api/v1/engine/evaluate", {
      game_id: gameId,
    });
  }

  impactoVenta(gameId: string) {
    return this.http.post<VentaImpactoRespuesta>("/api/v1/engine/sell-impact", {
      game_id: gameId,
    });
  }

  plan(datos: {
    n: number;
    modo: string;
    presupuesto?: number;
    average_min: number;
    users_rated_min: number;
    orden: string;
  }) {
    return this.http.post<PlanCompraRespuesta>(
      "/api/v1/engine/buy-plan",
      datos,
    );
  }

  estaNoche(datos: { jugadores: number; minutos: number }) {
    return this.http.post<EstaNocheRespuesta>("/api/v1/engine/tonight", datos);
  }
}
