import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";

import { environment } from "../../../environments/environment";
import type { components } from "./schema";

export type ColeccionRespuesta = components["schemas"]["ColeccionRespuesta"];
export type JuegoListado = components["schemas"]["JuegoListado"];
export type JuegoDetalle = components["schemas"]["JuegoDetalle"];
export type CoberturaRespuesta = components["schemas"]["CoberturaRespuesta"];
export type EvaluarRespuesta = components["schemas"]["EvaluarRespuesta"];
export type PlanCompraRespuesta = components["schemas"]["PlanCompraRespuesta"];
export type EstaNocheRespuesta = components["schemas"]["EstaNocheRespuesta"];
export type VentaImpactoRespuesta =
  components["schemas"]["VentaImpactoRespuesta"];
export type ChatRespuesta = components["schemas"]["ChatRespuesta"];
export type SugerenciasRespuesta =
  components["schemas"]["SugerenciasRespuesta"];

const API = environment.apiBase;

/** El perfil lo decide el backend a partir del token: ningún método lo envía. */
@Injectable({ providedIn: "root" })
export class CatalogoService {
  constructor(private readonly http: HttpClient) {}

  coleccion() {
    return this.http.get<ColeccionRespuesta>(`${API}/collection`);
  }

  buscar(query: string) {
    return this.http.get<{ juegos: JuegoListado[] }>(`${API}/games`, {
      params: { q: query, limit: 8 },
    });
  }

  detalle(gameId: string) {
    return this.http.get<JuegoDetalle>(`${API}/games/${gameId}`);
  }

  agregar(gameId: string) {
    return this.http.post(`${API}/collection`, { game_id: gameId });
  }

  quitar(gameId: string) {
    return this.http.delete(`${API}/collection/${gameId}`);
  }

  cobertura() {
    return this.http.get<CoberturaRespuesta>(`${API}/engine/coverage`);
  }

  evaluar(gameId: string) {
    return this.http.post<EvaluarRespuesta>(`${API}/engine/evaluate`, {
      game_id: gameId,
    });
  }

  impactoVenta(gameId: string) {
    return this.http.post<VentaImpactoRespuesta>(`${API}/engine/sell-impact`, {
      game_id: gameId,
    });
  }

  plan(datos: {
    n: number;
    average_min: number;
    users_rated_min: number;
    orden: string;
  }) {
    return this.http.post<PlanCompraRespuesta>(`${API}/engine/buy-plan`, {
      ...datos,
      modo: "juego",
    });
  }

  estaNoche(datos: {
    jugadores: number;
    minutos: number;
    edad_minima?: number;
  }) {
    return this.http.post<EstaNocheRespuesta>(`${API}/engine/tonight`, datos);
  }

  chat(mensaje: string, sessionId?: string, gameId?: string) {
    return this.http.post<ChatRespuesta>(`${API}/chat`, {
      mensaje,
      session_id: sessionId,
      game_id: gameId,
    });
  }

  sugerencias() {
    return this.http.get<SugerenciasRespuesta>(`${API}/chat/suggestions`);
  }
}
