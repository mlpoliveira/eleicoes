"use client";

import { useEffect, useState } from "react";
import { api, type Carga } from "@/lib/api";

// Rodapé fixo: data/hora da geração TSE da carga atual (T7).
export function Rodape() {
  const [carga, setCarga] = useState<Carga | null>(null);
  const [erro, setErro] = useState(false);
  useEffect(() => {
    api<Carga>("/carga").then(setCarga).catch(() => setErro(true));
  }, []);
  return (
    <footer className="fixed inset-x-0 bottom-0 z-10 border-t border-borda bg-superficie/95 px-4 py-1.5 text-xs text-texto-2 backdrop-blur">
      {erro ? (
        "Base de dados indisponível — verifique se a API está rodando."
      ) : carga?.geracao_tse ? (
        <>
          Dados: TSE — Dados Abertos, candidatos 2026 · geração TSE <b>{carga.geracao_tse}</b> · carga nº {carga.carga_id}
          {" · "}O TSE atualiza os arquivos várias vezes ao dia até a eleição; situações podem mudar.
        </>
      ) : (
        "Carregando informações da base…"
      )}
    </footer>
  );
}
