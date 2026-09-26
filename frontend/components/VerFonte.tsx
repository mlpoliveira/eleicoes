"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Fonte } from "@/lib/api";

interface RespostaFonte {
  natureza: string;
  observacao: string | null;
  dataset: string;
  arquivo: string;
  campo_tse: string | null;
  geracao_tse: string;
  registros: { arquivo: string; linha: number; valores_originais: Record<string, string | null> }[];
  mensagem: string | null;
}

interface Props {
  /** consulta a /api/fonte (valor original do CSV) */
  consulta?: { tabela: string; sq: number; campo: string; nr_ordem?: number; linha?: number };
  /** ou apenas o bloco de fonte já recebido */
  fonte?: Fonte;
  geracao?: string | null;
  observacao?: string;
}

// Botão "Ver fonte" (regra 5): dataset, arquivo, linha, campo, geração e o texto original do TSE.
export function VerFonte({ consulta, fonte, geracao, observacao }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [dados, setDados] = useState<RespostaFonte | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aberto, setAberto] = useState(false);

  useEffect(() => {
    if (!aberto || !consulta || dados) return;
    api<RespostaFonte>("/fonte", { ...consulta })
      .then(setDados)
      .catch((e: Error) => setErro(e.message));
  }, [aberto, consulta, dados]);

  const abrir = () => {
    setAberto(true);
    dialogo.current?.showModal();
  };

  return (
    <>
      <button
        type="button"
        onClick={abrir}
        className="text-[11px] text-destaque underline decoration-dotted underline-offset-2 hover:decoration-solid"
      >
        Ver fonte
      </button>
      <dialog
        ref={dialogo}
        onClose={() => setAberto(false)}
        className="m-auto w-[min(92vw,560px)] rounded-lg border border-borda bg-superficie p-0 text-texto backdrop:bg-black/40"
      >
        <div className="p-5 text-sm">
          <h2 className="mb-3 text-base font-semibold">Fonte da informação</h2>
          {erro && <p className="text-aviso-texto">{erro}</p>}
          {consulta && !dados && !erro && <p className="text-texto-2">Carregando…</p>}
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
            <dt className="text-texto-3">Dataset</dt>
            <dd>{dados?.dataset ?? fonte?.dataset ?? "TSE — candidatos-2026"}</dd>
            <dt className="text-texto-3">Arquivo</dt>
            <dd className="break-all font-mono text-xs">{dados?.arquivo ?? fonte?.arquivo ?? "—"}</dd>
            <dt className="text-texto-3">Campo</dt>
            <dd className="break-all font-mono text-xs">{dados?.campo_tse ?? fonte?.campo ?? "—"}</dd>
            {!dados && fonte?.linha != null && (
              <>
                <dt className="text-texto-3">Linha</dt>
                <dd>{fonte.linha}</dd>
              </>
            )}
            <dt className="text-texto-3">Geração TSE</dt>
            <dd>{dados?.geracao_tse ?? geracao ?? "—"}</dd>
          </dl>
          {(dados?.observacao || observacao || fonte?.observacao) && (
            <p className="mt-3 text-texto-2">{dados?.observacao ?? observacao ?? fonte?.observacao}</p>
          )}
          {dados && dados.registros.length > 0 && (
            <div className="mt-4">
              <h3 className="mb-1 font-medium">Texto original no arquivo do TSE</h3>
              <div className="max-h-56 overflow-auto rounded border border-borda">
                <table className="w-full text-xs">
                  <thead className="bg-superficie-2 text-left text-texto-2">
                    <tr>
                      <th className="px-2 py-1">Linha</th>
                      <th className="px-2 py-1">Campo</th>
                      <th className="px-2 py-1">Valor original</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dados.registros.flatMap((r) =>
                      Object.entries(r.valores_originais).map(([campo, v]) => (
                        <tr key={`${r.linha}-${campo}`} className="border-t border-borda">
                          <td className="px-2 py-1">{r.linha}</td>
                          <td className="px-2 py-1 font-mono">{campo}</td>
                          <td className="px-2 py-1 font-mono">{v ?? "(vazio)"}</td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {dados?.mensagem && <p className="mt-3 ausente">{dados.mensagem}</p>}
          <form method="dialog" className="mt-5 text-right">
            <button className="rounded border border-borda px-3 py-1 hover:bg-superficie-2">Fechar</button>
          </form>
        </div>
      </dialog>
    </>
  );
}
