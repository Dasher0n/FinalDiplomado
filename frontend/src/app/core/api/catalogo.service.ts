import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

import type { components } from './schema';

export type ColeccionRespuesta = components['schemas']['ColeccionRespuesta'];
export type JuegoListado = components['schemas']['JuegoListado'];
export type JuegoDetalle = components['schemas']['JuegoDetalle'];

@Injectable({ providedIn: 'root' })
export class CatalogoService {
  constructor(private readonly http: HttpClient) {}

  coleccion() {
    return this.http.get<ColeccionRespuesta>('/api/v1/collection');
  }

  buscar(query: string) {
    return this.http.get<{ juegos: JuegoListado[] }>('/api/v1/games', {
      params: { q: query, limit: 8 },
    });
  }

  detalle(gameId: string) {
    return this.http.get<JuegoDetalle>(`/api/v1/games/${gameId}`);
  }
}
