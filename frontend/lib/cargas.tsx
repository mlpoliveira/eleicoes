"use client";

import { useEffect, useState } from "react";
import { api } from "./api";

export interface InfoCarga {
  carga_id: number;
  geracao_tse: string;
  carregada_em: string;
  arquivos: string;
}

/** Lista de cargas (versões da base), da mais recente para a mais antiga. */
export function useCargas() {
  const [cargas, setCargas] = useState<InfoCarga[]>([]);
  useEffect(() => {
    api<{ itens: InfoCarga[] }>("/cargas").then((r) => setCargas(r.itens)).catch(() => setCargas([]));
  }, []);
  return cargas;
}

export function SeletorCarga({ cargas, valor, onChange }: {
  cargas: InfoCarga[]; valor: string; onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col text-xs text-texto-2">
      Carga (geração do TSE)
      <select value={valor} onChange={(e) => onChange(e.target.value)}
        className="mt-0.5 rounded border border-borda bg-superficie px-2 py-1 text-sm text-texto">
        {cargas.map((c, i) => (
          <option key={c.carga_id} value={i === 0 ? "" : String(c.carga_id)}>
            nº {c.carga_id} — geração {c.geracao_tse}{i === 0 ? " (atual)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
