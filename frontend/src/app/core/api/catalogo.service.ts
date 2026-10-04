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
export type VentaImpactoRespuesta =
  components["schemas"]["VentaImpactoRespuesta"];
export type ChatRespuesta = components["schemas"]["ChatRespuesta"];
export type SugerenciasRespuesta =
  components["schemas"]["SugerenciasRespuesta"];

export interface Perfil {
  id: string;
  nombre: string;
  tipo: string;
  descripcion: string;
  version_configuracion: number;
  metas: Record<string, Record<string, number>>;
}

@Injectable({ providedIn: "root" })
export class CatalogoService {
  constructor(private readonly http: HttpClient) {}

  perfiles() {
    return this.http.get<{ perfiles: Perfil[] }>("/api/v1/profiles");
  }

  coleccion(perfil: string) {
    return this.http.get<ColeccionRespuesta>("/api/v1/collection", {
      params: { perfil },
    });
  }

  buscar(query: string) {
    return this.http.get<{ juegos: JuegoListado[] }>("/api/v1/games", {
      params: { q: query, limit: 8 },
    });
  }

  detalle(gameId: string) {
    return this.http.get<JuegoDetalle>(`/api/v1/games/${gameId}`);
  }

  agregar(gameId: string, perfil: string) {
    return this.http.post(
      "/api/v1/collection",
      { game_id: gameId },
      { params: { perfil } },
    );
  }

  quitar(gameId: string, perfil: string) {
    return this.http.delete(`/api/v1/collection/${gameId}`, {
      params: { perfil },
    });
  }

  cobertura(perfil: string) {
    return this.http.get<CoberturaRespuesta>("/api/v1/engine/coverage", {
      params: { perfil },
    });
  }

  evaluar(gameId: string, perfil: string) {
    return this.http.post<EvaluarRespuesta>(
      "/api/v1/engine/evaluate",
      {
        game_id: gameId,
      },
      { params: { perfil } },
    );
  }

  impactoVenta(gameId: string, perfil: string) {
    return this.http.post<VentaImpactoRespuesta>(
      "/api/v1/engine/sell-impact",
      {
        game_id: gameId,
      },
      { params: { perfil } },
    );
  }

  plan(
    datos: {
      n: number;
      average_min: number;
      users_rated_min: number;
      orden: string;
    },
    perfil: string,
  ) {
    return this.http.post<PlanCompraRespuesta>(
      "/api/v1/engine/buy-plan",
      { ...datos, modo: "juego" },
      { params: { perfil } },
    );
  }

  estaNoche(
    datos: { jugadores: number; minutos: number; edad_minima?: number },
    perfil: string,
  ) {
    return this.http.post<EstaNocheRespuesta>("/api/v1/engine/tonight", datos, {
      params: { perfil },
    });
  }

  chat(mensaje: string, perfil: string, sessionId?: string, gameId?: string) {
    return this.http.post<ChatRespuesta>(
      "/api/v1/chat",
      { mensaje, session_id: sessionId, game_id: gameId },
      { params: { perfil } },
    );
  }

  sugerencias(perfil: string) {
    return this.http.get<SugerenciasRespuesta>("/api/v1/chat/suggestions", {
      params: { perfil },
    });
  }
}
